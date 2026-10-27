"""
Single-ticker analysis pipeline shared by the API, the Streamlit app and
the weekly snapshot job.

Before this module existed, the indicator list was copied in three places
(the analyze and compare routers and the Streamlit app). Keeping it here
means every consumer computes exactly the same indicators.

    add_indicators(df)                        price history -> + indicator columns
    analyse(ticker, df, info, risk_free_rate) -> CompositeResult
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pandas_ta as _ta  # noqa: F401  (activates the DataFrame .ta accessor)

from analysis.fundamentals import compute_fundamental_score
from analysis.scoring import CompositeResult, ScoringStrategy, run_scoring
from analysis.technical import compute_technical_score


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of *df* with every indicator the technical score reads.

    Args:
        df: OHLCV DataFrame as returned by MarketDataFetcher.get_ohlcv().

    Returns:
        New DataFrame: the original columns plus RSI, MACD, Bollinger Bands,
        SMA 20/50/200, EMA 20, OBV and ADX (pandas-ta column names).
    """
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
    return df_ind


def analyse(
    ticker: str,
    df: pd.DataFrame,
    info: dict[str, Any],
    risk_free_rate: float,
    strategy: ScoringStrategy | None = None,
) -> CompositeResult:
    """Run the full Shiller + Murphy analysis for one ticker.

    Same steps as POST /v1/analyze, without the HTTP layer.

    Args:
        ticker: Symbol, used for labelling the result.
        df: OHLCV price history.
        info: Fundamental fields from MarketDataFetcher.get_fundamental_info().
        risk_free_rate: Decimal rate (e.g. 0.045).
        strategy: Scoring strategy; defaults to the weighted average.

    Raises:
        InsufficientDataError: If the price history is too short.
    """
    current_price = info.get("regularMarketPrice") or float(df["Close"].iloc[-1])
    fundamental = compute_fundamental_score(
        current_price=current_price,
        beta=info.get("beta"),
        trailing_pe=info.get("trailingPE"),
        forward_pe=info.get("forwardPE"),
        dividend_rate=info.get("dividendRate"),
        dividend_yield=info.get("dividendYield"),
        earnings_growth=info.get("earningsGrowth"),
        risk_free_rate=risk_free_rate,
    )
    technical = compute_technical_score(add_indicators(df))
    return run_scoring(ticker, fundamental, technical, strategy=strategy)
