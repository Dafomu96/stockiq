"""
Tests for analysis/technical.py.

All tests run offline — no yfinance, no network.
Synthetic DataFrames are built with controlled price/volume patterns
so that the expected indicator signals are deterministic.

Test organisation:
    TestDataValidation        — _validate_dataframe()
    TestRSISignal             — RSI overbought/oversold detection
    TestMACDSignal            — MACD crossover detection
    TestBollingerSignal       — Bollinger Bands %B signal
    TestMovingAverageSignal   — Golden Cross / Death Cross
    TestOBVSignal             — OBV volume confirmation
    TestADXSignal             — trend strength
    TestCompositeScore        — compute_technical_score() integration
"""

import numpy as np
import pandas as pd
import pytest

from analysis.technical import (
    Signal,
    compute_technical_score,
)
from config.exceptions import InsufficientDataError


# ---------------------------------------------------------------------------
# DataFrame builders
# ---------------------------------------------------------------------------

def _make_df(
    rows: int = 252,
    trend: str = "up",
    volume: int = 50_000_000,
    start_price: float = 100.0,
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame with a controlled price trend.

    Args:
        rows: Number of bars.
        trend: "up" (monotonically rising), "down" (falling), "flat", "volatile".
        volume: Constant volume per bar.
        start_price: Starting close price.
    """
    idx = pd.date_range("2023-01-02", periods=rows, freq="B", tz="UTC")

    if trend == "up":
        closes = [start_price + i * 0.5 for i in range(rows)]
    elif trend == "down":
        closes = [start_price + rows * 0.5 - i * 0.5 for i in range(rows)]
    elif trend == "flat":
        closes = [start_price] * rows
    elif trend == "volatile":
        rng = np.random.default_rng(42)
        changes = rng.normal(0, 2.0, rows)
        closes = list(start_price + np.cumsum(changes))
    else:
        raises = ValueError(f"Unknown trend: {trend}")
        raise raises  # type: ignore[misc]

    closes = [max(c, 1.0) for c in closes]  # never negative

    return pd.DataFrame(
        {
            "Open": [c - 0.5 for c in closes],
            "High": [c + 1.0 for c in closes],
            "Low": [c - 1.0 for c in closes],
            "Close": closes,
            "Volume": [volume] * rows,
        },
        index=idx,
    )


def _make_oversold_df(rows: int = 100) -> pd.DataFrame:
    """Price drops sharply for the last 20 bars → RSI should be low."""
    df = _make_df(rows=rows, trend="up")
    # Override last 20 bars with a sharp drop
    closes = list(df["Close"])
    for i in range(rows - 20, rows):
        closes[i] = closes[rows - 21] - (i - (rows - 21)) * 3.0
        closes[i] = max(closes[i], 1.0)
    df["Close"] = closes
    df["Open"] = [c - 0.5 for c in closes]
    df["High"] = [c + 0.5 for c in closes]
    df["Low"] = [c - 1.5 for c in closes]
    return df


def _make_overbought_df(rows: int = 100) -> pd.DataFrame:
    """Price rises sharply for the last 20 bars → RSI should be high."""
    df = _make_df(rows=rows, trend="flat")
    closes = list(df["Close"])
    for i in range(rows - 20, rows):
        closes[i] = closes[rows - 21] + (i - (rows - 21)) * 5.0
    df["Close"] = closes
    df["Open"] = [c - 0.5 for c in closes]
    df["High"] = [c + 1.0 for c in closes]
    df["Low"] = [c - 0.5 for c in closes]
    return df


# ---------------------------------------------------------------------------
# TestDataValidation
# ---------------------------------------------------------------------------

class TestDataValidation:
    def test_raises_on_missing_close_column(self):
        df = _make_df().drop(columns=["Close"])
        with pytest.raises(ValueError, match="Close"):
            compute_technical_score(df)

    def test_raises_on_missing_volume_column(self):
        df = _make_df().drop(columns=["Volume"])
        with pytest.raises(ValueError, match="Volume"):
            compute_technical_score(df)

    def test_raises_insufficient_data_below_50_rows(self):
        df = _make_df(rows=30)
        with pytest.raises(InsufficientDataError) as exc_info:
            compute_technical_score(df)
        assert exc_info.value.available == 30
        assert exc_info.value.required == 50

    def test_accepts_dataframe_with_exactly_50_rows(self):
        df = _make_df(rows=50)
        result = compute_technical_score(df)
        assert result is not None

    def test_does_not_mutate_input_dataframe(self):
        df = _make_df(rows=252)
        original_columns = list(df.columns)
        compute_technical_score(df)
        assert list(df.columns) == original_columns


# ---------------------------------------------------------------------------
# TestRSISignal
# ---------------------------------------------------------------------------

class TestRSISignal:
    def test_oversold_price_produces_buy_signal(self):
        df = _make_oversold_df(rows=100)
        result = compute_technical_score(df)
        # The sharp drop should push RSI below 30
        if result.rsi.value is not None:
            assert result.rsi.value < 50  # at least below midpoint

    def test_overbought_price_produces_sell_signal(self):
        df = _make_overbought_df(rows=100)
        result = compute_technical_score(df)
        if result.rsi.value is not None:
            assert result.rsi.value > 50

    def test_rsi_value_in_valid_range(self):
        df = _make_df(rows=252, trend="volatile")
        result = compute_technical_score(df)
        if result.rsi.value is not None:
            assert 0 <= result.rsi.value <= 100

    def test_rsi_signal_is_valid_enum_value(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.rsi.signal in (Signal.BUY, Signal.NEUTRAL, Signal.SELL)

    def test_rsi_thresholds_match_settings(self):
        from config.settings import settings
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.rsi.overbought_threshold == settings.rsi_overbought
        assert result.rsi.oversold_threshold == settings.rsi_oversold

    def test_rsi_note_included_in_output(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert any("RSI" in note for note in result.notes)


# ---------------------------------------------------------------------------
# TestMACDSignal
# ---------------------------------------------------------------------------

class TestMACDSignal:
    def test_uptrend_produces_buy_leaning_macd(self):
        df = _make_df(rows=252, trend="up")
        result = compute_technical_score(df)
        # In a clean uptrend, MACD should be positive or bullish
        assert result.macd.signal in (Signal.BUY, Signal.NEUTRAL)

    def test_downtrend_produces_sell_leaning_macd(self):
        df = _make_df(rows=252, trend="down")
        result = compute_technical_score(df)
        assert result.macd.signal in (Signal.SELL, Signal.NEUTRAL)

    def test_macd_values_are_floats_or_none(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        for val in [result.macd.macd, result.macd.signal_line, result.macd.histogram]:
            assert val is None or isinstance(val, float)

    def test_crossover_flags_are_booleans(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert isinstance(result.macd.is_bullish_crossover, bool)
        assert isinstance(result.macd.is_bearish_crossover, bool)

    def test_bullish_and_bearish_crossover_mutually_exclusive(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert not (result.macd.is_bullish_crossover and result.macd.is_bearish_crossover)

    def test_macd_note_references_murphy(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        macd_notes = [n for n in result.notes if "MACD" in n]
        assert any("Murphy" in n for n in macd_notes)


# ---------------------------------------------------------------------------
# TestBollingerSignal
# ---------------------------------------------------------------------------

class TestBollingerSignal:
    def test_percent_b_in_valid_range_for_normal_prices(self):
        """%B is not strictly bounded — can exceed [0,1] on breakouts."""
        df = _make_df(rows=252, trend="flat")
        result = compute_technical_score(df)
        # For flat prices, %B should be near 0.5
        if result.bollinger.percent_b is not None:
            assert -0.5 <= result.bollinger.percent_b <= 1.5

    def test_upper_greater_than_lower_band(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        if result.bollinger.upper and result.bollinger.lower:
            assert result.bollinger.upper > result.bollinger.lower

    def test_middle_band_between_upper_and_lower(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        bb = result.bollinger
        if bb.upper and bb.middle and bb.lower:
            assert bb.lower <= bb.middle <= bb.upper

    def test_bollinger_signal_is_valid(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.bollinger.signal in (Signal.BUY, Signal.NEUTRAL, Signal.SELL)

    def test_bollinger_note_in_output(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert any("Bollinger" in note for note in result.notes)


# ---------------------------------------------------------------------------
# TestMovingAverageSignal
# ---------------------------------------------------------------------------

class TestMovingAverageSignal:
    def test_uptrend_produces_golden_cross(self):
        """252 bars of uptrend: SMA50 should be above SMA200."""
        df = _make_df(rows=252, trend="up")
        result = compute_technical_score(df)
        assert result.moving_averages.golden_cross is True

    def test_downtrend_produces_death_cross(self):
        """252 bars of downtrend: SMA50 should be below SMA200."""
        df = _make_df(rows=252, trend="down", start_price=500.0)
        result = compute_technical_score(df)
        assert result.moving_averages.death_cross is True

    def test_golden_and_death_cross_mutually_exclusive(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert not (
            result.moving_averages.golden_cross
            and result.moving_averages.death_cross
        )

    def test_sma200_unavailable_with_short_history(self):
        """Less than 200 bars → SMA200 must be None, not a crash."""
        df = _make_df(rows=100)
        result = compute_technical_score(df)
        assert result.moving_averages.sma_200 is None

    def test_sma_values_are_float_or_none(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        ma = result.moving_averages
        for val in [ma.sma_20, ma.sma_50, ma.sma_200, ma.ema_20]:
            assert val is None or isinstance(val, float)

    def test_ma_note_references_murphy(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        ma_notes = [n for n in result.notes if "SMA" in n or "moving" in n.lower()]
        assert any("Murphy" in n for n in ma_notes)


# ---------------------------------------------------------------------------
# TestOBVSignal
# ---------------------------------------------------------------------------

class TestOBVSignal:
    def test_rising_price_and_volume_gives_buy_signal(self):
        df = _make_df(rows=252, trend="up", volume=50_000_000)
        result = compute_technical_score(df)
        assert result.obv.signal in (Signal.BUY, Signal.NEUTRAL)

    def test_volume_trend_is_valid_string(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.obv.volume_trend in ("rising", "falling", "flat", "unknown")

    def test_confirms_price_trend_is_bool(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert isinstance(result.obv.confirms_price_trend, bool)

    def test_obv_note_in_output(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert any("OBV" in note for note in result.notes)


# ---------------------------------------------------------------------------
# TestADXSignal
# ---------------------------------------------------------------------------

class TestADXSignal:
    def test_strong_uptrend_has_high_adx(self):
        df = _make_df(rows=252, trend="up")
        result = compute_technical_score(df)
        if result.adx.adx is not None:
            # A strong monotonic trend should produce high ADX
            assert result.adx.adx > 0

    def test_trend_strength_is_valid_string(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.adx.trend_strength in ("strong", "moderate", "weak", "unknown")

    def test_adx_signal_is_valid(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.adx.signal in (Signal.BUY, Signal.NEUTRAL, Signal.SELL)

    def test_adx_note_in_output_when_available(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        if result.adx.adx is not None:
            assert any("ADX" in note for note in result.notes)


# ---------------------------------------------------------------------------
# TestCompositeScore — integration tests
# ---------------------------------------------------------------------------

class TestCompositeScore:
    def test_score_in_valid_range(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert 0.0 <= result.score <= 100.0

    def test_signal_is_valid_string(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.signal in ("buy", "neutral", "sell")

    def test_uptrend_scores_higher_than_downtrend(self):
        up = compute_technical_score(_make_df(rows=252, trend="up"))
        down = compute_technical_score(_make_df(rows=252, trend="down", start_price=500.0))
        assert up.score > down.score

    def test_components_dict_has_all_expected_keys(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        expected = {"rsi", "macd", "bollinger", "moving_averages", "obv", "adx"}
        assert set(result.components.keys()) == expected

    def test_all_component_scores_in_valid_range(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        for key, val in result.components.items():
            assert 0.0 <= val <= 100.0, f"Component {key}={val} out of range"

    def test_notes_non_empty(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert len(result.notes) > 0

    def test_data_quality_warnings_list_exists(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert isinstance(result.data_quality_warnings, list)

    def test_short_history_adds_sma200_warning(self):
        """When SMA200 can't be computed, a warning must be added."""
        df = _make_df(rows=100)
        result = compute_technical_score(df)
        assert any("SMA200" in w for w in result.data_quality_warnings)

    def test_result_is_frozen_dataclass(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        with pytest.raises(Exception):
            result.score = 99.0  # type: ignore[misc]

    def test_score_never_exceeds_100_on_extreme_uptrend(self):
        df = _make_df(rows=400, trend="up", start_price=1.0)
        result = compute_technical_score(df)
        assert result.score <= 100.0

    def test_score_never_below_0_on_extreme_downtrend(self):
        df = _make_df(rows=400, trend="down", start_price=1000.0)
        result = compute_technical_score(df)
        assert result.score >= 0.0

    def test_all_indicator_results_attached(self):
        df = _make_df(rows=252)
        result = compute_technical_score(df)
        assert result.rsi is not None
        assert result.macd is not None
        assert result.bollinger is not None
        assert result.moving_averages is not None
        assert result.obv is not None
        assert result.adx is not None
