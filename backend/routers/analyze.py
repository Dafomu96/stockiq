"""
POST /v1/analyze — full stock analysis endpoint.

Orchestrates: fetch → fundamentals → technical → scoring → response.
The core analysis modules are imported directly — no duplication.
"""

from __future__ import annotations

import logging

import pandas_ta as _ta  # noqa: F401 — activates DataFrame .ta accessor
from fastapi import APIRouter, Depends, HTTPException, status

from analysis.fundamentals import compute_fundamental_score
from analysis.scoring import FundamentalOnlyStrategy, WeightedAverageStrategy, run_scoring
from analysis.technical import compute_technical_score
from backend.dependencies import get_fetcher, log_request
from backend.mappers import to_analyze_response
from backend.schemas import AnalyzeRequest, AnalyzeResponse
from config.exceptions import DataFetchError, InsufficientDataError, InvalidTickerError
from data.fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["analysis"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Run full stock analysis",
    description=(
        "Fetches price history and fundamental data for a ticker, "
        "then runs Shiller fundamental analysis (CAPM, Gordon Growth Model, "
        "P/E ratio), Murphy technical analysis (RSI, MACD, Bollinger Bands, "
        "moving averages, OBV, ADX), and returns a composite score and signal. "
        "\n\nData is End-of-Day (EOD). Not suitable for intraday trading."
    ),
    responses={
        400: {"description": "Invalid ticker or period"},
        404: {"description": "Ticker not found"},
        422: {"description": "Validation error in request body"},
        503: {"description": "Data source unavailable"},
    },
)
async def analyze(
    body: AnalyzeRequest,
    fetcher: MarketDataFetcher = Depends(get_fetcher),
    _log: None = Depends(log_request),
) -> AnalyzeResponse:
    """Full analysis pipeline for a single ticker.

    Steps:
        1. Fetch OHLCV price history (1y default, cached 24h).
        2. Fetch fundamental info (P/E, beta, dividends — cached 24h).
        3. Fetch risk-free rate from FRED (cached 7 days).
        4. Compute all technical indicators via pandas-ta.
        5. Compute fundamental score (Shiller framework).
        6. Compute technical score (Murphy framework).
        7. Run composite scoring (Strategy Pattern).
        8. Map domain result → Pydantic response schema.
    """
    logger.info("analyze_start ticker=%s period=%s", body.ticker, body.period)

    # ── 1–3: Data fetching ────────────────────────────────────────────────
    try:
        df = fetcher.get_ohlcv(body.ticker, period=body.period)
        info = fetcher.get_fundamental_info(body.ticker)
        rf = fetcher.get_risk_free_rate()
    except InvalidTickerError as exc:
        logger.warning("analyze_invalid_ticker ticker=%s", body.ticker)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DataFetchError as exc:
        logger.error("analyze_fetch_error ticker=%s error=%s", body.ticker, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Data source error: {exc.reason}",
        ) from exc

    # ── 4: Technical indicators ───────────────────────────────────────────
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

    # ── 5: Fundamental score ──────────────────────────────────────────────
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

    # ── 6: Technical score ────────────────────────────────────────────────
    try:
        technical = compute_technical_score(df_ind)
    except InsufficientDataError as exc:
        logger.warning(
            "analyze_insufficient_data ticker=%s available=%d",
            body.ticker, exc.available,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient price history for technical analysis: "
                f"need {exc.required} bars, got {exc.available}. "
                "Try a longer period (e.g. '1y') or a different ticker."
            ),
        ) from exc

    # ── 7: Composite scoring ──────────────────────────────────────────────
    strategy_map = {
        "weighted_average": WeightedAverageStrategy(),
        "fundamental_only": FundamentalOnlyStrategy(),
    }
    strategy = strategy_map.get(body.strategy, WeightedAverageStrategy())
    result = run_scoring(body.ticker, fundamental, technical, strategy=strategy)

    logger.info(
        "analyze_complete ticker=%s score=%.1f signal=%s confidence=%s",
        body.ticker, result.composite_score, result.signal, result.confidence,
    )

    # ── 8: Map to response schema ─────────────────────────────────────────
    return to_analyze_response(result)
