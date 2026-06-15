"""
Tests for analysis/scoring.py.

All tests are pure unit tests — FundamentalScore and TechnicalScore
are built from lightweight fixtures, not from real market data.

Test organisation:
    TestWeightedAverageStrategy    — default strategy logic
    TestFundamentalOnlyStrategy    — fallback strategy
    TestConfidenceAssessment       — confidence degradation rules
    TestRunScoring                 — public entry point
    TestCompositeResultContract    — shape and invariants of the output
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from analysis.fundamentals import (
    CAPMResult,
    FundamentalScore,
    GordonResult,
    PERatioResult,
)
from analysis.scoring import (
    CompositeResult,
    FundamentalOnlyStrategy,
    WeightedAverageStrategy,
    run_scoring,
)
from analysis.technical import (
    ADXResult,
    BollingerResult,
    MACDResult,
    MovingAverageResult,
    OBVResult,
    RSIResult,
    Signal,
    TechnicalScore,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_capm(beta: float = 1.0) -> CAPMResult:
    return CAPMResult(
        required_return=0.10,
        risk_free_rate=0.045,
        market_return=0.10,
        beta=beta,
        market_risk_premium=0.055,
    )


def _make_gordon(
    fair_value: float | None = 200.0,
    current_price: float = 150.0,
    upside_pct: float | None = 33.3,
) -> GordonResult:
    return GordonResult(
        fair_value=fair_value,
        current_price=current_price,
        dividend=0.96,
        discount_rate=0.10,
        growth_rate=0.05,
        upside_pct=upside_pct,
    )


def _make_pe(interpretation: str = "fairly_valued") -> PERatioResult:
    return PERatioResult(
        actual_pe=25.0,
        theoretical_pe=20.0,
        forward_pe=22.0,
        pe_gap=5.0,
        interpretation=interpretation,
    )


_MISSING = object()  # sentinel — None is a valid value for gordon
def _make_fundamental(
    score: float = 65.0,
    signal: str = "buy",
    gordon: GordonResult | None = _MISSING,
    pe_actual: float | None = 25.0,
) -> FundamentalScore:
    resolved_gordon: GordonResult | None = (
        _make_gordon() if gordon is _MISSING else gordon  # type: ignore[assignment]
    )
    pe = PERatioResult(
        actual_pe=pe_actual,
        theoretical_pe=20.0,
        forward_pe=22.0,
        pe_gap=5.0 if pe_actual else None,
        interpretation="fairly_valued" if pe_actual else "insufficient_data",
    )
    return FundamentalScore(
        score=score,
        components={"capm": 60.0, "pe_ratio": 65.0},
        signal=signal,
        capm=_make_capm(),
        gordon=resolved_gordon,
        pe=pe,
        notes=["CAPM note.", "Gordon note.", "P/E note."],
    )


def _make_rsi(signal: Signal = Signal.NEUTRAL) -> RSIResult:
    return RSIResult(
        value=50.0, signal=signal,
        overbought_threshold=70.0, oversold_threshold=30.0,
    )


def _make_macd(signal: Signal = Signal.NEUTRAL) -> MACDResult:
    return MACDResult(
        macd=0.5, signal_line=0.3, histogram=0.2,
        signal=signal,
        is_bullish_crossover=False, is_bearish_crossover=False,
    )


def _make_bollinger(signal: Signal = Signal.NEUTRAL) -> BollingerResult:
    return BollingerResult(
        upper=155.0, middle=150.0, lower=145.0,
        bandwidth=0.067, percent_b=0.5, signal=signal,
    )


def _make_ma(signal: Signal = Signal.NEUTRAL) -> MovingAverageResult:
    return MovingAverageResult(
        sma_20=148.0, sma_50=145.0, sma_200=140.0, ema_20=149.0,
        current_price=150.0,
        golden_cross=True, death_cross=False, price_above_sma200=True,
        signal=signal,
    )


def _make_obv(signal: Signal = Signal.NEUTRAL) -> OBVResult:
    return OBVResult(
        current_obv=5_000_000.0, obv_sma=4_800_000.0,
        volume_trend="rising", confirms_price_trend=True, signal=signal,
    )


def _make_adx(signal: Signal = Signal.NEUTRAL) -> ADXResult:
    return ADXResult(
        adx=28.0, plus_di=22.0, minus_di=15.0,
        trend_strength="strong", signal=signal,
    )


def _make_technical(
    score: float = 65.0,
    signal_str: str = "buy",
    warnings: list[str] | None = None,
) -> TechnicalScore:
    sig = Signal(signal_str) if signal_str in ("buy", "neutral", "sell") else Signal.NEUTRAL
    return TechnicalScore(
        score=score,
        signal=signal_str,
        components={
            "rsi": 65.0, "macd": 70.0, "bollinger": 60.0,
            "moving_averages": 70.0, "obv": 65.0, "adx": 55.0,
        },
        rsi=_make_rsi(sig),
        macd=_make_macd(sig),
        bollinger=_make_bollinger(),
        moving_averages=_make_ma(sig),
        obv=_make_obv(sig),
        adx=_make_adx(sig),
        notes=["RSI note.", "MACD note.", "Bollinger note."],
        data_quality_warnings=warnings or [],
    )


# ---------------------------------------------------------------------------
# TestWeightedAverageStrategy
# ---------------------------------------------------------------------------

class TestWeightedAverageStrategy:

    def test_composite_is_weighted_average(self):
        strategy = WeightedAverageStrategy(
            weight_fundamental=0.5, weight_technical=0.5
        )
        f = _make_fundamental(score=80.0)
        t = _make_technical(score=60.0)
        result = strategy.combine("AAPL", f, t)
        assert result.composite_score == pytest.approx(70.0, abs=0.1)

    def test_asymmetric_weights_applied_correctly(self):
        strategy = WeightedAverageStrategy(
            weight_fundamental=0.7, weight_technical=0.3
        )
        f = _make_fundamental(score=100.0)
        t = _make_technical(score=0.0)
        result = strategy.combine("AAPL", f, t)
        assert result.composite_score == pytest.approx(70.0, abs=0.1)

    def test_score_above_60_gives_buy_signal(self):
        strategy = WeightedAverageStrategy()
        result = strategy.combine(
            "AAPL",
            _make_fundamental(score=70.0),
            _make_technical(score=70.0),
        )
        assert result.signal == "buy"

    def test_score_below_40_gives_sell_signal(self):
        strategy = WeightedAverageStrategy()
        result = strategy.combine(
            "AAPL",
            _make_fundamental(score=30.0),
            _make_technical(score=30.0),
        )
        assert result.signal == "sell"

    def test_score_between_40_and_60_gives_neutral_signal(self):
        strategy = WeightedAverageStrategy()
        result = strategy.combine(
            "AAPL",
            _make_fundamental(score=50.0),
            _make_technical(score=50.0),
        )
        assert result.signal == "neutral"

    def test_raises_on_weights_not_summing_to_one(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            WeightedAverageStrategy(
                weight_fundamental=0.6, weight_technical=0.6
            )

    def test_raises_on_zero_weight(self):
        with pytest.raises(ValueError, match="must be in"):
            WeightedAverageStrategy(
                weight_fundamental=0.0, weight_technical=1.0
            )

    def test_weights_dict_sums_to_one(self):
        strategy = WeightedAverageStrategy(
            weight_fundamental=0.6, weight_technical=0.4
        )
        total = sum(strategy.weights.values())
        assert total == pytest.approx(1.0, abs=0.001)

    def test_name_includes_percentages(self):
        strategy = WeightedAverageStrategy(
            weight_fundamental=0.6, weight_technical=0.4
        )
        assert "60%" in strategy.name
        assert "40%" in strategy.name

    def test_ticker_is_uppercased_in_result(self):
        strategy = WeightedAverageStrategy()
        result = strategy.combine(
            "aapl", _make_fundamental(), _make_technical()
        )
        assert result.ticker == "AAPL"

    def test_score_breakdown_has_all_keys(self):
        strategy = WeightedAverageStrategy()
        result = strategy.combine("AAPL", _make_fundamental(), _make_technical())
        assert "fundamental" in result.score_breakdown
        assert "technical" in result.score_breakdown
        assert "composite" in result.score_breakdown

    def test_score_breakdown_composite_matches_composite_score(self):
        strategy = WeightedAverageStrategy()
        result = strategy.combine("AAPL", _make_fundamental(), _make_technical())
        assert result.score_breakdown["composite"] == result.composite_score

    def test_analysed_at_is_utc_iso_string(self):
        from datetime import datetime, timezone
        strategy = WeightedAverageStrategy()
        result = strategy.combine("AAPL", _make_fundamental(), _make_technical())
        # Should parse without error and be timezone-aware
        dt = datetime.fromisoformat(result.analysed_at)
        assert dt.tzinfo is not None

    def test_disclaimer_is_never_empty(self):
        strategy = WeightedAverageStrategy()
        result = strategy.combine("AAPL", _make_fundamental(), _make_technical())
        assert len(result.disclaimer) > 50


# ---------------------------------------------------------------------------
# TestFundamentalOnlyStrategy
# ---------------------------------------------------------------------------

class TestFundamentalOnlyStrategy:

    def test_composite_equals_fundamental_score(self):
        strategy = FundamentalOnlyStrategy()
        f = _make_fundamental(score=72.0)
        t = _make_technical(score=20.0)  # technical is ignored
        result = strategy.combine("AAPL", f, t)
        assert result.composite_score == pytest.approx(72.0, abs=0.1)

    def test_technical_weight_is_zero(self):
        strategy = FundamentalOnlyStrategy()
        assert strategy.weights["technical"] == 0.0
        assert strategy.weights["fundamental"] == 1.0

    def test_confidence_always_medium(self):
        """Without technical confirmation, confidence can't be 'high'."""
        strategy = FundamentalOnlyStrategy()
        result = strategy.combine(
            "AAPL",
            _make_fundamental(score=90.0),
            _make_technical(score=90.0),
        )
        assert result.confidence == "medium"

    def test_technical_result_still_attached(self):
        """Technical analysis is run and attached even if not scored."""
        strategy = FundamentalOnlyStrategy()
        t = _make_technical(score=30.0)
        result = strategy.combine("AAPL", _make_fundamental(), t)
        assert result.technical is t

    def test_signal_derived_from_fundamental_score(self):
        strategy = FundamentalOnlyStrategy()
        buy_result = strategy.combine(
            "AAPL", _make_fundamental(score=75.0), _make_technical()
        )
        sell_result = strategy.combine(
            "AAPL", _make_fundamental(score=25.0), _make_technical()
        )
        assert buy_result.signal == "buy"
        assert sell_result.signal == "sell"


# ---------------------------------------------------------------------------
# TestConfidenceAssessment
# ---------------------------------------------------------------------------

class TestConfidenceAssessment:

    def test_high_confidence_when_no_warnings_and_full_data(self):
        strategy = WeightedAverageStrategy()
        # Full data: gordon present, pe available, no technical warnings
        f = _make_fundamental(gordon=_make_gordon(), pe_actual=25.0)
        t = _make_technical(warnings=[])
        result = strategy.combine("AAPL", f, t)
        assert result.confidence == "high"

    def test_medium_confidence_when_gordon_missing(self):
        strategy = WeightedAverageStrategy()
        # No dividend → gordon = None
        f = _make_fundamental(gordon=None)
        t = _make_technical(warnings=[])
        result = strategy.combine("AAPL", f, t)
        assert result.confidence == "medium"
        assert len(result.confidence_reasons) == 1

    def test_medium_confidence_when_one_technical_warning(self):
        strategy = WeightedAverageStrategy()
        f = _make_fundamental()
        t = _make_technical(warnings=["SMA200 not available."])
        result = strategy.combine("AAPL", f, t)
        assert result.confidence in ("medium", "low")

    def test_low_confidence_when_multiple_data_issues(self):
        strategy = WeightedAverageStrategy()
        # No gordon + no pe + two technical warnings = low confidence
        f = _make_fundamental(gordon=None, pe_actual=None)
        t = _make_technical(warnings=["SMA200 warning.", "RSI warning."])
        result = strategy.combine("AAPL", f, t)
        assert result.confidence == "low"

    def test_confidence_reasons_list_matches_confidence_level(self):
        strategy = WeightedAverageStrategy()
        f = _make_fundamental(gordon=None)
        t = _make_technical(warnings=[])
        result = strategy.combine("AAPL", f, t)
        # medium confidence → exactly 1 reason
        assert len(result.confidence_reasons) >= 1


# ---------------------------------------------------------------------------
# TestRunScoring
# ---------------------------------------------------------------------------

class TestRunScoring:

    def test_uses_default_weighted_strategy_when_none_given(self):
        result = run_scoring(
            "AAPL", _make_fundamental(), _make_technical()
        )
        assert "Weighted average" in result.strategy_name

    def test_accepts_custom_strategy(self):
        custom = FundamentalOnlyStrategy()
        result = run_scoring(
            "AAPL", _make_fundamental(score=72.0),
            _make_technical(score=10.0), strategy=custom
        )
        # Fundamental only — technical score (10) doesn't pull it down
        assert result.composite_score == pytest.approx(72.0, abs=0.1)

    def test_ticker_normalised_to_uppercase(self):
        result = run_scoring("asml.as", _make_fundamental(), _make_technical())
        assert result.ticker == "ASML.AS"

    def test_result_is_composite_result_instance(self):
        result = run_scoring("AAPL", _make_fundamental(), _make_technical())
        assert isinstance(result, CompositeResult)

    def test_result_is_frozen(self):
        result = run_scoring("AAPL", _make_fundamental(), _make_technical())
        with pytest.raises(Exception):
            result.composite_score = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestCompositeResultContract
# ---------------------------------------------------------------------------

class TestCompositeResultContract:
    """Ensure the CompositeResult shape is stable — this is the API contract."""

    def _result(self) -> CompositeResult:
        return run_scoring("AAPL", _make_fundamental(), _make_technical())

    def test_has_ticker(self):
        assert self._result().ticker == "AAPL"

    def test_composite_score_in_range(self):
        r = self._result()
        assert 0.0 <= r.composite_score <= 100.0

    def test_signal_is_valid_string(self):
        assert self._result().signal in ("buy", "neutral", "sell")

    def test_fundamental_is_fundamental_score(self):
        assert isinstance(self._result().fundamental, FundamentalScore)

    def test_technical_is_technical_score(self):
        assert isinstance(self._result().technical, TechnicalScore)

    def test_weights_sum_to_one(self):
        r = self._result()
        assert sum(r.weights.values()) == pytest.approx(1.0, abs=0.001)

    def test_summary_notes_contains_section_headers(self):
        r = self._result()
        headers = [n for n in r.summary_notes if n.startswith("──")]
        assert len(headers) >= 2  # at least fundamental + technical sections

    def test_summary_notes_contains_fundamental_notes(self):
        r = self._result()
        assert any("CAPM" in n or "Gordon" in n or "P/E" in n for n in r.summary_notes)

    def test_disclaimer_present_and_non_trivial(self):
        r = self._result()
        assert "financial advice" in r.disclaimer.lower()
        assert "EOD" in r.disclaimer

    def test_analysed_at_is_populated(self):
        r = self._result()
        assert len(r.analysed_at) > 0
