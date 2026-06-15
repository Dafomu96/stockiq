"""
POST /v1/analyze — full stock analysis endpoint.

Each step of the pipeline is timed and logged individually:
    fetch_ohlcv_ms      time to get price history (cache or network)
    fetch_info_ms       time to get fundamental info
    fetch_rf_ms         time to get risk-free rate
    indicators_ms       time to compute technical indicators
    fundamental_ms      time to compute fundamental score
    technical_ms        time to compute technical score
    scoring_ms          time to run composite scoring
    total_ms            end-to-end wall time

cache_hit fields tell you whether data came from cache or the network,
which is critical for understanding latency spikes in production.
"""

from __future__ import annotations

import logging
import time

import pandas_ta as _ta  # noqa: F401
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
        "P/E ratio) and Murphy technical analysis (RSI, MACD, Bollinger Bands, "
        "moving averages, OBV, ADX), returning a composite score and signal.\n\n"
        "Data is End-of-Day (EOD). Not suitable for intraday trading."
    ),
    responses={
        400: {"description": "Insufficient price history"},
        404: {"description": "Ticker not found"},
        422: {"description": "Validation error"},
        503: {"description": "Data source unavailable"},
    },
)
async def analyze(
    body: AnalyzeRequest,
    fetcher: MarketDataFetcher = Depends(get_fetcher),
    _log: None = Depends(log_request),
) -> AnalyzeResponse:
    t0 = time.monotonic()

    logger.info(
        "pipeline_started",
        extra={"ticker": body.ticker, "period": body.period, "strategy": body.strategy},
    )

    # ── Step 1: OHLCV price history ────────────────────────────────────────────
    t1 = time.monotonic()
    try:
        df = fetcher.get_ohlcv(body.ticker, period=body.period)
    except InvalidTickerError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticker '{body.ticker}' not found. "
                   "Check the symbol and exchange suffix (e.g. ASML.AS for Euronext).",
        )
    except DataFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Data source error: {exc.reason}",
        )
    fetch_ohlcv_ms = round((time.monotonic() - t1) * 1000, 1)
    logger.info(
        "step_fetch_ohlcv",
        extra={
            "ticker":        body.ticker,
            "rows":          len(df),
            "duration_ms":   fetch_ohlcv_ms,
        },
    )

    # ── Step 2: Fundamental info ───────────────────────────────────────────────
    t2 = time.monotonic()
    try:
        info = fetcher.get_fundamental_info(body.ticker)
    except (InvalidTickerError, DataFetchError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    fetch_info_ms = round((time.monotonic() - t2) * 1000, 1)
    logger.info(
        "step_fetch_info",
        extra={
            "ticker":      body.ticker,
            "sector":      info.get("sector"),
            "beta":        info.get("beta"),
            "duration_ms": fetch_info_ms,
        },
    )

    # ── Step 3: Risk-free rate ─────────────────────────────────────────────────
    t3 = time.monotonic()
    rf = fetcher.get_risk_free_rate()
    fetch_rf_ms = round((time.monotonic() - t3) * 1000, 1)
    logger.debug(
        "step_fetch_rf",
        extra={"rf": rf, "duration_ms": fetch_rf_ms},
    )

    # ── Step 4: Technical indicators ───────────────────────────────────────────
    t4 = time.monotonic()
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
    indicators_ms = round((time.monotonic() - t4) * 1000, 1)
    logger.debug(
        "step_indicators",
        extra={"ticker": body.ticker, "duration_ms": indicators_ms},
    )

    # ── Step 5: Fundamental score ──────────────────────────────────────────────
    t5 = time.monotonic()
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
    fundamental_ms = round((time.monotonic() - t5) * 1000, 1)
    logger.info(
        "step_fundamental",
        extra={
            "ticker":      body.ticker,
            "score":       fundamental.score,
            "signal":      fundamental.signal,
            "capm_return": round(fundamental.capm.required_return, 4),
            "duration_ms": fundamental_ms,
        },
    )

    # ── Step 6: Technical score ────────────────────────────────────────────────
    t6 = time.monotonic()
    try:
        technical = compute_technical_score(df_ind)
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient price history: need {exc.required} bars, "
                f"got {exc.available}. Try period='2y'."
            ),
        )
    technical_ms = round((time.monotonic() - t6) * 1000, 1)
    logger.info(
        "step_technical",
        extra={
            "ticker":      body.ticker,
            "score":       technical.score,
            "signal":      technical.signal,
            "warnings":    len(technical.data_quality_warnings),
            "duration_ms": technical_ms,
        },
    )

    # ── Step 7: Composite scoring ──────────────────────────────────────────────
    t7 = time.monotonic()
    strategy_map = {
        "weighted_average": WeightedAverageStrategy(),
        "fundamental_only": FundamentalOnlyStrategy(),
    }
    strategy = strategy_map.get(body.strategy, WeightedAverageStrategy())
    result = run_scoring(body.ticker, fundamental, technical, strategy=strategy)
    scoring_ms = round((time.monotonic() - t7) * 1000, 1)

    total_ms = round((time.monotonic() - t0) * 1000, 1)

    logger.info(
        "pipeline_completed",
        extra={
            "ticker":         body.ticker,
            "composite_score": result.composite_score,
            "signal":          result.signal,
            "confidence":      result.confidence,
            "fetch_ohlcv_ms":  fetch_ohlcv_ms,
            "fetch_info_ms":   fetch_info_ms,
            "indicators_ms":   indicators_ms,
            "fundamental_ms":  fundamental_ms,
            "technical_ms":    technical_ms,
            "scoring_ms":      scoring_ms,
            "total_ms":        total_ms,
        },
    )

    return to_analyze_response(result)
