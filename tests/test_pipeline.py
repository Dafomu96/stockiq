"""Tests for analysis/pipeline.py — the shared single-ticker pipeline."""

from __future__ import annotations

import pandas as pd
import pytest

from analysis.pipeline import add_indicators, analyse
from analysis.scoring import CompositeResult, FundamentalOnlyStrategy
from config.exceptions import InsufficientDataError


class TestAddIndicators:
    def test_adds_every_indicator_the_technical_score_reads(self, mock_ohlcv_df):
        df_ind = add_indicators(mock_ohlcv_df)
        for prefix in ("RSI_14", "MACD_", "BBU_20", "SMA_20", "SMA_50", "SMA_200"):
            assert any(c.startswith(prefix) for c in df_ind.columns), prefix
        for col in ("EMA_20", "OBV", "ADX_14"):
            assert col in df_ind.columns

    def test_does_not_modify_the_input(self, mock_ohlcv_df):
        before = list(mock_ohlcv_df.columns)
        add_indicators(mock_ohlcv_df)
        assert list(mock_ohlcv_df.columns) == before


class TestAnalyse:
    def test_returns_composite_result_in_range(
        self, mock_ohlcv_df, mock_fundamental_info, mock_risk_free_rate
    ):
        result = analyse(
            "AAPL", mock_ohlcv_df, mock_fundamental_info, mock_risk_free_rate
        )
        assert isinstance(result, CompositeResult)
        assert result.ticker == "AAPL"
        assert 0.0 <= result.composite_score <= 100.0
        assert result.signal in {"buy", "neutral", "sell"}

    def test_uses_the_given_strategy(
        self, mock_ohlcv_df, mock_fundamental_info, mock_risk_free_rate
    ):
        result = analyse(
            "AAPL",
            mock_ohlcv_df,
            mock_fundamental_info,
            mock_risk_free_rate,
            strategy=FundamentalOnlyStrategy(),
        )
        assert result.weights.get("technical", 0.0) == 0.0

    def test_falls_back_to_last_close_without_market_price(
        self, mock_ohlcv_df, mock_fundamental_info, mock_risk_free_rate
    ):
        info = {**mock_fundamental_info, "regularMarketPrice": None}
        result = analyse("AAPL", mock_ohlcv_df, info, mock_risk_free_rate)
        assert result.fundamental.capm is not None

    def test_short_history_raises(self, mock_fundamental_info, mock_risk_free_rate):
        idx = pd.date_range("2024-01-02", periods=20, freq="B", tz="UTC")
        df = pd.DataFrame(
            {
                "Open": 100.0,
                "High": 101.0,
                "Low": 99.0,
                "Close": 100.0,
                "Volume": 1_000_000,
            },
            index=idx,
        )
        with pytest.raises(InsufficientDataError):
            analyse("AAPL", df, mock_fundamental_info, mock_risk_free_rate)
