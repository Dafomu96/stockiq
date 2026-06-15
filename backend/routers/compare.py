"""
POST /v1/compare — side-by-side analysis of two tickers.

Runs the full analysis pipeline for both tickers concurrently using
asyncio.gather, then produces a head-to-head verdict.

Both tickers share:
    - The same risk-free rate (fetched once, reused for both)
    - The same scoring strategy

Concurrency design:
    asyncio.gather runs both analysis pipelines concurrently in the
    same event loop. Since the bottleneck is I/O (yfinance HTTP calls),
    this roughly halves the wall time vs running them sequentially.
    If one ticker fails, the other result is discarded and the error
    is surfaced normally.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

import pandas_ta as _ta  # noqa: F401
from fastapi import APIRouter, Depends, HTTPException, status

from analysis.fundamentals import compute_fundamental_score
from analysis.scoring import (
    FundamentalOnlyStrategy,
    WeightedAverageStrategy,
    run_scoring,
)
from analysis.technical import compute_technical_score
from backend.dependencies import get_fetcher, log_request
from backend.schemas_compare import (
    CompareRequest,
    CompareResponse,
    ScoreSummary,
    WinnerVerdict,
)
from config.exceptions import DataFetchError, InsufficientDataError, InvalidTickerError
from data.fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["analysis"])


# ---------------------------------------------------------------------------
# Single-ticker analysis helper (reused for both tickers)
# ---------------------------------------------------------------------------

def _analyse_ticker(
    ticker: str,
    fetcher: MarketDataFetcher,
    period: str,
    rf: float,
    strategy,
) -> ScoreSummary:
    """Run full analysis for one ticker and return a compact ScoreSummary.

    Raises HTTPException on data or insufficient-data errors so the
    caller (the compare endpoint) can surface them cleanly.
    """
    try:
        df = fetcher.get_ohlcv(ticker, period=period)
        info = fetcher.get_fundamental_info(ticker)
    except InvalidTickerError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DataFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Data source error for {ticker}: {exc.reason}",
        ) from exc

    # Compute indicators
    df_ind = df.copy()
    df_ind.ta.rsi(length=14, append=True)
    df_ind.ta.macd(fast=12, slow=26, signal=9, append=True)
    df_ind.ta.bbands(length=20, std=2, append=True)
    df_ind.ta.sma(length=20, append=True)
    df_ind.ta.sma(length=50, append=True)
    df_ind.ta.sma(length=200, append=True)
    df_ind.ta.ema(length=20, append=True)
    df_ind.ta.obv(append=True)
    df_ind.ta.adx(length=14, append=True)

    current_price = info.get("regularMarketPrice") or float(df["Close"].iloc[-1])

    fundamental = compute_fundamental_score(
        current_price=current_price,
        beta=info.get("beta"),
        trailing_pe=info.get("trailingPE"),
        forward_pe=info.get("forwardPE"),
        dividend_rate=info.get("dividendRate"),
        dividend_yield=info.get("dividendYield"),
        earnings_growth=info.get("earningsGrowth"),
        risk_free_rate=rf,
    )

    try:
        technical = compute_technical_score(df_ind)
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient price history for {ticker}: "
                f"need {exc.required} bars, got {exc.available}."
            ),
        ) from exc

    result = run_scoring(ticker, fundamental, technical, strategy=strategy)

    ma = technical.moving_averages
    return ScoreSummary(
        ticker=ticker,
        composite_score=result.composite_score,
        signal=result.signal,
        fundamental_score=result.score_breakdown["fundamental"],
        technical_score=result.score_breakdown["technical"],
        confidence=result.confidence,
        # Fundamental metrics
        capm_return=fundamental.capm.required_return,
        beta=fundamental.capm.beta,
        fair_value=fundamental.gordon.fair_value if fundamental.gordon else None,
        current_price=current_price,
        upside_pct=fundamental.gordon.upside_pct if fundamental.gordon else None,
        pe_actual=fundamental.pe.actual_pe,
        pe_interpretation=fundamental.pe.interpretation,
        # Technical signals
        rsi_value=technical.rsi.value,
        rsi_signal=technical.rsi.signal.value,
        macd_signal=technical.macd.signal.value,
        ma_signal=technical.moving_averages.signal.value,
        golden_cross=ma.golden_cross,
        price_above_sma200=ma.price_above_sma200,
        # Notes
        notes=result.summary_notes[:6],  # top 6 to keep response compact
        data_quality_warnings=technical.data_quality_warnings,
    )


def _build_verdict(a: ScoreSummary, b: ScoreSummary) -> WinnerVerdict:
    """Derive the head-to-head verdict from two ScoreSummary objects."""
    margin = round(a.composite_score - b.composite_score, 1)
    is_tied = abs(margin) < 2.0

    if is_tied:
        winner = None
        reason = (
            f"Both {a.ticker} and {b.ticker} score within 2 points of each other "
            f"({a.composite_score:.0f} vs {b.composite_score:.0f}). "
            "No clear winner — consider other factors such as sector, "
            "dividend policy, and your investment horizon."
        )
    elif margin > 0:
        winner = a.ticker
        reason = _explain_winner(a, b)
    else:
        winner = b.ticker
        reason = _explain_winner(b, a)

    fund_winner = (
        a.ticker if a.fundamental_score > b.fundamental_score
        else b.ticker if b.fundamental_score > a.fundamental_score
        else None
    )
    tech_winner = (
        a.ticker if a.technical_score > b.technical_score
        else b.ticker if b.technical_score > a.technical_score
        else None
    )

    return WinnerVerdict(
        winner=winner,
        margin=abs(margin),
        reason=reason,
        is_tied=is_tied,
        fundamental_winner=fund_winner,
        technical_winner=tech_winner,
    )


def _explain_winner(winner: ScoreSummary, loser: ScoreSummary) -> str:
    """Build a human-readable explanation for why winner scored higher."""
    reasons: list[str] = []

    fund_diff = winner.fundamental_score - loser.fundamental_score
    tech_diff = winner.technical_score - loser.technical_score

    if fund_diff > 5:
        reasons.append(
            f"stronger fundamental score ({winner.fundamental_score:.0f} vs "
            f"{loser.fundamental_score:.0f})"
        )
    if tech_diff > 5:
        reasons.append(
            f"stronger technical score ({winner.technical_score:.0f} vs "
            f"{loser.technical_score:.0f})"
        )

    if winner.golden_cross and not loser.golden_cross:
        reasons.append("Golden Cross active (long-term bullish trend)")

    if winner.upside_pct is not None and (loser.upside_pct is None or winner.upside_pct > loser.upside_pct):
        reasons.append(
            f"higher Gordon upside ({winner.upside_pct:.1f}% vs "
            f"{loser.upside_pct:.1f}%)" if loser.upside_pct is not None
            else f"positive Gordon upside ({winner.upside_pct:.1f}%)"
        )

    if not reasons:
        reasons.append(
            f"composite score of {winner.composite_score:.0f} vs "
            f"{loser.composite_score:.0f}"
        )

    return (
        f"{winner.ticker} scores higher ({winner.composite_score:.0f} vs "
        f"{loser.composite_score:.0f}) due to: {'; '.join(reasons)}."
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/compare",
    response_model=CompareResponse,
    summary="Compare two tickers side by side",
    description=(
        "Runs the full Shiller + Murphy analysis for two tickers concurrently "
        "and returns a side-by-side comparison with a head-to-head verdict.\n\n"
        "Both analyses use the same risk-free rate and scoring strategy. "
        "Wall time is roughly half of two sequential /analyze calls because "
        "data fetching runs concurrently.\n\n"
        "Data is End-of-Day (EOD). Not financial advice."
    ),
    responses={
        400: {"description": "Insufficient price history"},
        404: {"description": "One or both tickers not found"},
        422: {"description": "Validation error (e.g. same ticker twice)"},
        503: {"description": "Data source unavailable"},
    },
)
async def compare(
    body: CompareRequest,
    fetcher: MarketDataFetcher = Depends(get_fetcher),
    _log: None = Depends(log_request),
) -> CompareResponse:
    """Compare two tickers with concurrent data fetching."""
    t0 = time.monotonic()

    logger.info(
        "compare_started",
        extra={"ticker_a": body.ticker_a, "ticker_b": body.ticker_b},
    )

    # Fetch risk-free rate once — reused for both analyses
    rf = fetcher.get_risk_free_rate()

    strategy_map = {
        "weighted_average": WeightedAverageStrategy(),
        "fundamental_only": FundamentalOnlyStrategy(),
    }
    strategy = strategy_map.get(body.strategy, WeightedAverageStrategy())

    # Run both analyses concurrently in the event loop
    loop = asyncio.get_event_loop()

    summary_a, summary_b = await asyncio.gather(
        loop.run_in_executor(
            None,
            _analyse_ticker,
            body.ticker_a, fetcher, body.period, rf, strategy,
        ),
        loop.run_in_executor(
            None,
            _analyse_ticker,
            body.ticker_b, fetcher, body.period, rf, strategy,
        ),
    )

    verdict = _build_verdict(summary_a, summary_b)
    total_ms = round((time.monotonic() - t0) * 1000, 1)

    logger.info(
        "compare_completed",
        extra={
            "ticker_a":  body.ticker_a,
            "score_a":   summary_a.composite_score,
            "ticker_b":  body.ticker_b,
            "score_b":   summary_b.composite_score,
            "winner":    verdict.winner,
            "margin":    verdict.margin,
            "total_ms":  total_ms,
        },
    )

    return CompareResponse(
        ticker_a=summary_a,
        ticker_b=summary_b,
        verdict=verdict,
        analysed_at=datetime.now(timezone.utc).isoformat(),
    )
