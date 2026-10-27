"""Tests for scripts/snapshot.py — the weekly score snapshot job.

Offline like the rest of the suite: the fetcher is the shared mock_fetcher.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from config.exceptions import DataFetchError, InvalidTickerError
from scripts import snapshot
from scripts.snapshot import (
    COLUMNS,
    RunSummary,
    _num,
    format_summary,
    load_watchlist,
    run_snapshot,
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture()
def fetcher(mock_fetcher):
    mock_fetcher.rf_source = "fred"
    return mock_fetcher


def _fail_for(fetcher, bad: str, exc: Exception) -> None:
    """Make get_ohlcv raise *exc* for ticker *bad* and work for the rest."""
    df = fetcher.get_ohlcv.return_value

    def side_effect(ticker, period=None, interval=None):
        if ticker == bad:
            raise exc
        return df

    fetcher.get_ohlcv.side_effect = side_effect


# ---------------------------------------------------------------------------
# load_watchlist
# ---------------------------------------------------------------------------


class TestLoadWatchlist:
    def test_skips_comments_and_blanks_and_dedupes(self, tmp_path):
        path = tmp_path / "watchlist.txt"
        path.write_text(
            "# header\n\naapl\nMSFT  # inline comment\n  san.mc \nAAPL\n",
            encoding="utf-8",
        )
        assert load_watchlist(path) == ["AAPL", "MSFT", "SAN.MC"]

    def test_repo_watchlist_is_valid(self):
        repo_root = Path(__file__).resolve().parent.parent
        tickers = load_watchlist(repo_root / "snapshots" / "watchlist.txt")
        assert 10 <= len(tickers) <= 40
        assert all(" " not in t for t in tickers)


# ---------------------------------------------------------------------------
# run_snapshot
# ---------------------------------------------------------------------------


class TestRunSnapshot:
    def test_writes_header_and_one_ok_row_per_ticker(
        self, fetcher, mock_ohlcv_df, tmp_path
    ):
        out = tmp_path / "scores.csv"
        summary = run_snapshot(
            ["AAPL", "MSFT"],
            fetcher,
            out,
            run_date="2026-10-31",
            code_version="abc1234",
        )

        assert summary.ok == ["AAPL", "MSFT"]
        assert summary.failed == []
        assert out.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUMNS)

        rows = _rows(out)
        assert [r["ticker"] for r in rows] == ["AAPL", "MSFT"]
        row = rows[0]
        assert row["status"] == "ok"
        assert row["run_date"] == "2026-10-31"
        assert row["price_date"] == mock_ohlcv_df.index[-1].date().isoformat()
        assert float(row["close"]) == pytest.approx(mock_ohlcv_df["Close"].iloc[-1])
        assert 0.0 <= float(row["composite_score"]) <= 100.0
        assert row["signal"] in {"buy", "neutral", "sell"}
        assert float(row["beta"]) == pytest.approx(1.24)
        assert float(row["risk_free_rate"]) == pytest.approx(0.045)
        assert row["rf_source"] == "fred"
        assert row["benchmark"] == "SPY"
        assert row["benchmark_close"] != ""
        assert row["sector"] == "Technology"
        assert row["code_version"] == "abc1234"

    def test_failing_ticker_is_recorded_and_the_rest_continue(self, fetcher, tmp_path):
        _fail_for(fetcher, "BAD", InvalidTickerError("BAD"))
        out = tmp_path / "scores.csv"

        summary = run_snapshot(
            ["AAPL", "BAD", "MSFT"], fetcher, out, run_date="2026-10-31"
        )

        assert summary.ok == ["AAPL", "MSFT"]
        assert summary.failed == ["BAD"]
        bad = next(r for r in _rows(out) if r["ticker"] == "BAD")
        assert bad["status"] == "error"
        assert bad["error"].startswith("InvalidTickerError")
        assert bad["composite_score"] == ""

    def test_rerun_same_day_skips_ok_rows_and_retries_failures(self, fetcher, tmp_path):
        out = tmp_path / "scores.csv"
        _fail_for(fetcher, "BAD", DataFetchError("BAD", "rate limited"))
        run_snapshot(["AAPL", "BAD"], fetcher, out, run_date="2026-10-31")

        fetcher.get_ohlcv.side_effect = None  # Yahoo is back
        summary = run_snapshot(["AAPL", "BAD"], fetcher, out, run_date="2026-10-31")

        assert summary.skipped == ["AAPL"]
        assert summary.ok == ["BAD"]
        statuses = [(r["ticker"], r["status"]) for r in _rows(out)]
        assert statuses == [("AAPL", "ok"), ("BAD", "error"), ("BAD", "ok")]

    def test_next_week_appends_without_a_second_header(self, fetcher, tmp_path):
        out = tmp_path / "scores.csv"
        run_snapshot(["AAPL"], fetcher, out, run_date="2026-10-31")
        run_snapshot(["AAPL"], fetcher, out, run_date="2026-11-07")

        rows = _rows(out)
        assert [r["run_date"] for r in rows] == ["2026-10-31", "2026-11-07"]

    def test_different_header_is_refused(self, fetcher, tmp_path):
        out = tmp_path / "scores.csv"
        out.write_text("run_date,ticker,score\n2026-10-24,AAPL,55\n", encoding="utf-8")

        with pytest.raises(ValueError, match="expected"):
            run_snapshot(["AAPL"], fetcher, out)

    def test_benchmark_failure_leaves_it_empty(self, fetcher, tmp_path):
        _fail_for(fetcher, "SPY", DataFetchError("SPY", "timeout"))
        out = tmp_path / "scores.csv"

        summary = run_snapshot(["AAPL"], fetcher, out, run_date="2026-10-31")

        assert summary.benchmark_close is None
        assert summary.ok == ["AAPL"]
        assert _rows(out)[0]["benchmark_close"] == ""

    def test_fallback_rate_is_flagged(self, fetcher, tmp_path):
        fetcher.rf_source = "fallback"
        out = tmp_path / "scores.csv"
        run_snapshot(["AAPL"], fetcher, out, run_date="2026-10-31")
        assert _rows(out)[0]["rf_source"] == "fallback"

    def test_pauses_between_tickers_only(self, fetcher, tmp_path):
        waits: list[float] = []
        run_snapshot(
            ["AAPL", "MSFT", "KO"],
            fetcher,
            tmp_path / "scores.csv",
            pause_seconds=1.5,
            sleep=waits.append,
        )
        assert waits == [1.5, 1.5]

    def test_creates_the_output_folder(self, fetcher, tmp_path):
        out = tmp_path / "new" / "scores.csv"
        run_snapshot(["AAPL"], fetcher, out)
        assert out.exists()


# ---------------------------------------------------------------------------
# Helpers and CLI
# ---------------------------------------------------------------------------


class TestNum:
    @pytest.mark.parametrize("value", [None, float("nan"), float("inf"), "n/a", True])
    def test_missing_or_bad_values_become_empty(self, value):
        assert _num(value) == ""

    def test_rounds_numbers(self):
        assert _num(1.23456789, 4) == 1.2346
        assert _num("2.5") == 2.5


class TestFormatSummary:
    def test_lists_failures_and_rate_source(self):
        text = format_summary(
            RunSummary(
                "2026-10-31",
                ok=["AAPL"],
                failed=["BAD"],
                rf_source="fallback",
                benchmark_close=None,
            )
        )
        assert "Failed: 1 (BAD)" in text
        assert "fallback" in text
        assert "Benchmark close: missing" in text


class TestMain:
    @pytest.fixture()
    def watchlist(self, tmp_path):
        path = tmp_path / "watchlist.txt"
        path.write_text("AAPL\nMSFT\n", encoding="utf-8")
        return path

    def test_success_writes_csv_and_step_summary(
        self, fetcher, watchlist, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(snapshot, "MarketDataFetcher", lambda: fetcher)
        step_summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(step_summary))
        monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef")
        out = tmp_path / "scores.csv"

        code = snapshot.main(
            ["--watchlist", str(watchlist), "--out", str(out), "--pause", "0"]
        )

        assert code == 0
        rows = _rows(out)
        assert [r["ticker"] for r in rows] == ["AAPL", "MSFT"]
        assert rows[0]["code_version"] == "0123456"
        assert "OK: 2" in step_summary.read_text(encoding="utf-8")

    def test_all_failed_returns_1(self, fetcher, watchlist, tmp_path, monkeypatch):
        fetcher.get_ohlcv.side_effect = DataFetchError("X", "blocked")
        monkeypatch.setattr(snapshot, "MarketDataFetcher", lambda: fetcher)
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

        code = snapshot.main(
            [
                "--watchlist",
                str(watchlist),
                "--out",
                str(tmp_path / "scores.csv"),
                "--pause",
                "0",
            ]
        )
        assert code == 1

    def test_empty_watchlist_returns_2(self, tmp_path):
        empty = tmp_path / "empty.txt"
        empty.write_text("# nothing yet\n", encoding="utf-8")
        assert snapshot.main(["--watchlist", str(empty)]) == 2
