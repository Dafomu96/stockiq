"""
Weekly score snapshots.

Runs the StockIQ analysis for every ticker in a watchlist and appends one
row per ticker to a CSV, one file per year (snapshots/scores_2026.csv,
snapshots/scores_2027.csv, ...), plus an Excel copy of that year's file
(scores_2026.xlsx) that opens with numbers and dates in any Excel locale.
Run on a schedule (.github/workflows/snapshot.yml)
it builds a point-in-time history: the fundamentals yfinance returns today
are stored with today's date, which yfinance cannot give you afterwards.
Months later the stored scores can be checked against what prices did.

Each row also keeps the raw inputs (beta, P/E, dividend, risk-free rate),
so the scores can be recomputed if the model changes.

Usage:
    python -m scripts.snapshot
    python -m scripts.snapshot --watchlist snapshots/watchlist.txt \\
        --out "snapshots/scores_{year}.csv" --benchmark SPY --pause 2
    python -m scripts.snapshot --no-excel      # CSV only
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from analysis.pipeline import analyse
from data.fetcher import MarketDataFetcher

logger = logging.getLogger("stockiq.snapshot")

DEFAULT_WATCHLIST = Path("snapshots/watchlist.txt")
# "{year}" is replaced by the year of the run: one file per year.
DEFAULT_OUT = "snapshots/scores_{year}.csv"
DEFAULT_BENCHMARK = "SPY"
PRICE_PERIOD = "1y"  # same history the app uses by default

COLUMNS = [
    "run_date",
    "ticker",
    "status",
    "error",
    "price_date",
    "close",
    "benchmark",
    "benchmark_close",
    "composite_score",
    "signal",
    "confidence",
    "fundamental_score",
    "technical_score",
    "market_price",
    "beta",
    "trailing_pe",
    "forward_pe",
    "dividend_rate",
    "dividend_yield",
    "earnings_growth",
    "sector",
    "currency",
    "risk_free_rate",
    "rf_source",
    "code_version",
]


class Fetcher(Protocol):
    """The part of MarketDataFetcher this job uses."""

    rf_source: str | None

    def get_ohlcv(
        self, ticker: str, period: str | None = None, interval: str | None = None
    ) -> pd.DataFrame: ...

    def get_fundamental_info(self, ticker: str) -> dict[str, Any]: ...

    def get_risk_free_rate(self) -> float: ...


@dataclass
class RunSummary:
    """What happened in one run, ticker by ticker."""

    run_date: str
    ok: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    rf_source: str = ""
    benchmark_close: float | None = None
    csv_path: str = ""
    excel_path: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_watchlist(path: Path) -> list[str]:
    """Read tickers, one per line. Blank lines and ``#`` comments are ignored.

    Tickers are upper-cased and de-duplicated, keeping the file order.
    """
    tickers: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        ticker = raw.split("#", 1)[0].strip().upper()
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


def resolve_out_path(template: str | Path, run_date: str) -> Path:
    """Replace ``{year}`` in *template* with the year of *run_date*."""
    return Path(str(template).replace("{year}", run_date[:4]))


def export_excel(csv_path: Path) -> Path:
    """Write an Excel copy of *csv_path* next to it (same name, .xlsx).

    The CSV stays the source of truth (small, readable diffs in git); the
    .xlsx is rebuilt from it on every run so it always matches. Dates are
    real Excel dates and numbers real numbers, so a Spanish-locale Excel
    reads them correctly.
    """
    date_columns = ["run_date", "price_date"]
    df = pd.read_csv(csv_path, parse_dates=date_columns)
    for col in date_columns:
        df[col] = df[col].dt.date  # dates, not midnight datetimes
    xlsx_path = csv_path.with_suffix(".xlsx")
    year = csv_path.stem[-4:]
    sheet = year if year.isdigit() else "scores"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet)
        ws = writer.sheets[sheet]
        ws.freeze_panes = "C2"  # keep the header and date/ticker visible
        ws.auto_filter.ref = ws.dimensions
        for idx, column in enumerate(ws.columns):
            if df.columns[idx] in date_columns:
                for cell in column[1:]:
                    cell.number_format = "yyyy-mm-dd"
                width = 10
            else:
                width = max(len(str(c.value)) for c in column if c.value is not None)
            width = max(width, len(str(column[0].value)))
            ws.column_dimensions[column[0].column_letter].width = min(width + 2, 40)
    return xlsx_path


def _num(value: Any, digits: int = 6) -> float | str:
    """Number for the CSV; empty string for None, NaN or non-numeric values."""
    if value is None or isinstance(value, bool):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(number) or math.isinf(number):
        return ""
    return round(number, digits)


def _read_existing(path: Path) -> set[tuple[str, str]]:
    """(run_date, ticker) pairs already stored with status "ok".

    Raises ValueError if the file has a different header, so a schema change
    never writes misaligned rows.
    """
    if not path.exists() or path.stat().st_size == 0:
        return set()
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            raise ValueError(
                f"{path} has columns {reader.fieldnames}, expected {COLUMNS}. "
                "Move the old file aside or migrate it before running."
            )
        return {(r["run_date"], r["ticker"]) for r in reader if r["status"] == "ok"}


def _benchmark_close(fetcher: Fetcher, benchmark: str) -> float | None:
    try:
        df = fetcher.get_ohlcv(benchmark, period="5d")
        return float(df["Close"].iloc[-1])
    except Exception as exc:  # the benchmark is useful, not essential
        logger.warning("benchmark_failed ticker=%s error=%s", benchmark, exc)
        return None


def snapshot_ticker(
    ticker: str,
    fetcher: Fetcher,
    *,
    run_date: str,
    risk_free_rate: float,
    rf_source: str,
    benchmark: str,
    benchmark_close: float | None,
    code_version: str,
) -> dict[str, Any]:
    """Analyse one ticker and return its CSV row (status "ok" or "error")."""
    row: dict[str, Any] = dict.fromkeys(COLUMNS, "")
    row.update(
        run_date=run_date,
        ticker=ticker,
        benchmark=benchmark,
        benchmark_close=_num(benchmark_close, 4),
        risk_free_rate=_num(risk_free_rate),
        rf_source=rf_source,
        code_version=code_version,
    )
    try:
        df = fetcher.get_ohlcv(ticker, period=PRICE_PERIOD)
        info = fetcher.get_fundamental_info(ticker)
        result = analyse(ticker, df, info, risk_free_rate)
    except Exception as exc:  # one bad ticker must not stop the run
        logger.warning("ticker_failed ticker=%s error=%s", ticker, exc)
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return row

    row.update(
        status="ok",
        price_date=pd.Timestamp(df.index[-1]).date().isoformat(),
        close=_num(df["Close"].iloc[-1], 4),
        composite_score=_num(result.composite_score, 2),
        signal=result.signal,
        confidence=result.confidence,
        fundamental_score=_num(result.score_breakdown.get("fundamental"), 2),
        technical_score=_num(result.score_breakdown.get("technical"), 2),
        market_price=_num(info.get("regularMarketPrice"), 4),
        beta=_num(info.get("beta")),
        trailing_pe=_num(info.get("trailingPE")),
        forward_pe=_num(info.get("forwardPE")),
        dividend_rate=_num(info.get("dividendRate")),
        dividend_yield=_num(info.get("dividendYield")),
        earnings_growth=_num(info.get("earningsGrowth")),
        sector=info.get("sector") or "",
        currency=info.get("currency") or "",
    )
    return row


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_snapshot(
    tickers: Sequence[str],
    fetcher: Fetcher,
    out_path: str | Path,
    *,
    benchmark: str = DEFAULT_BENCHMARK,
    run_date: str | None = None,
    code_version: str = "local",
    pause_seconds: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
    excel: bool = False,
) -> RunSummary:
    """Analyse every ticker and append the rows to the CSV.

    *out_path* may contain ``{year}``; it is replaced by the year of the
    run, so each year gets its own file. With ``excel=True`` an .xlsx copy
    of that file is written next to it.

    Re-running on the same day skips tickers that already have an "ok" row
    for that date and retries the ones that failed.
    """
    run_date = run_date or datetime.now(UTC).date().isoformat()
    out_path = resolve_out_path(out_path, run_date)
    done = _read_existing(out_path)

    risk_free_rate = fetcher.get_risk_free_rate()
    rf_source = str(getattr(fetcher, "rf_source", None) or "unknown")
    bench_close = _benchmark_close(fetcher, benchmark)
    summary = RunSummary(
        run_date,
        rf_source=rf_source,
        benchmark_close=bench_close,
        csv_path=str(out_path),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_path.exists() or out_path.stat().st_size == 0
    with out_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        if write_header:
            writer.writeheader()
        first = True
        for ticker in tickers:
            if (run_date, ticker) in done:
                summary.skipped.append(ticker)
                continue
            if not first and pause_seconds > 0:
                sleep(pause_seconds)  # be gentle with Yahoo
            first = False
            row = snapshot_ticker(
                ticker,
                fetcher,
                run_date=run_date,
                risk_free_rate=risk_free_rate,
                rf_source=rf_source,
                benchmark=benchmark,
                benchmark_close=bench_close,
                code_version=code_version,
            )
            writer.writerow(row)
            fh.flush()
            (summary.ok if row["status"] == "ok" else summary.failed).append(ticker)

    if excel:
        summary.excel_path = str(export_excel(out_path))
    return summary


def format_summary(summary: RunSummary) -> str:
    """Markdown summary, shown in the GitHub Actions run page."""
    lines = [
        f"## StockIQ snapshot {summary.run_date}",
        "",
        f"- OK: {len(summary.ok)}",
        f"- Failed: {len(summary.failed)}"
        + (f" ({', '.join(summary.failed)})" if summary.failed else ""),
        f"- Already stored today: {len(summary.skipped)}",
        f"- Risk-free rate source: {summary.rf_source}",
        f"- File: {summary.csv_path}"
        + (f" (+ {Path(summary.excel_path).name})" if summary.excel_path else ""),
        "- Benchmark close: "
        + (
            "missing"
            if summary.benchmark_close is None
            else f"{summary.benchmark_close:.2f}"
        ),
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append StockIQ score snapshots for a watchlist to a CSV."
    )
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help='CSV path; "{year}" becomes the year of the run (default: %(default)s)',
    )
    parser.add_argument(
        "--no-excel", action="store_true", help="do not write the .xlsx copy"
    )
    parser.add_argument("--benchmark", default=DEFAULT_BENCHMARK)
    parser.add_argument(
        "--pause", type=float, default=2.0, help="seconds to wait between tickers"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    tickers = load_watchlist(args.watchlist)
    if not tickers:
        logger.error("watchlist_empty path=%s", args.watchlist)
        return 2

    summary = run_snapshot(
        tickers,
        MarketDataFetcher(),
        args.out,
        benchmark=args.benchmark,
        code_version=os.environ.get("GITHUB_SHA", "local")[:7],
        pause_seconds=args.pause,
        excel=not args.no_excel,
    )

    text = format_summary(summary)
    print(text)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(text)

    # Fail the run (so GitHub notifies you) only when nothing new was stored.
    if summary.failed and not summary.ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
