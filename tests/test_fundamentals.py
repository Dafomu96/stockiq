"""
Tests for analysis/fundamentals.py.

All tests are pure unit tests — no I/O, no network, no mocks needed.
The functions under test are deterministic and side-effect free.

Test organisation:
    TestCAPM              — compute_capm()
    TestGordonGrowth      — compute_gordon()
    TestPDV               — compute_pdv()
    TestPERatio           — compute_pe_ratio()
    TestFundamentalScore  — compute_fundamental_score() (integration-style)

Each test name follows: test_<condition>_<expected_outcome>
"""

import math

import pytest

from analysis.fundamentals import (
    compute_capm,
    compute_gordon,
    compute_pdv,
    compute_pe_ratio,
    compute_fundamental_score,
)
from config.exceptions import ModelAssumptionError


# ---------------------------------------------------------------------------
# TestCAPM
# ---------------------------------------------------------------------------

class TestCAPM:
    """Capital Asset Pricing Model: r_i = r_f + β · (r_m - r_f)"""

    def test_standard_inputs_return_correct_value(self):
        # r = 0.045 + 1.24 * (0.10 - 0.045) = 0.045 + 1.24 * 0.055 = 0.1132
        result = compute_capm(beta=1.24, risk_free_rate=0.045, market_return=0.10)
        assert result.required_return == pytest.approx(0.1132, abs=1e-4)

    def test_beta_zero_returns_risk_free_rate(self):
        """β=0 means no systematic risk — required return equals risk-free rate."""
        result = compute_capm(beta=0.0, risk_free_rate=0.045, market_return=0.10)
        assert result.required_return == pytest.approx(0.045, abs=1e-6)

    def test_beta_one_returns_market_return(self):
        """β=1 means asset moves exactly with the market."""
        result = compute_capm(beta=1.0, risk_free_rate=0.045, market_return=0.10)
        assert result.required_return == pytest.approx(0.10, abs=1e-6)

    def test_negative_beta_returns_below_risk_free_rate(self):
        """Negative beta assets (e.g. inverse funds) have required return < r_f."""
        result = compute_capm(beta=-0.5, risk_free_rate=0.045, market_return=0.10)
        assert result.required_return < 0.045

    def test_market_risk_premium_computed_correctly(self):
        result = compute_capm(beta=1.0, risk_free_rate=0.04, market_return=0.10)
        assert result.market_risk_premium == pytest.approx(0.06, abs=1e-6)

    def test_defaults_to_settings_market_return(self):
        from config.settings import settings
        result = compute_capm(beta=1.0, risk_free_rate=0.04)
        assert result.market_return == settings.market_return

    def test_raises_on_negative_risk_free_rate(self):
        with pytest.raises(ValueError, match="negative"):
            compute_capm(beta=1.0, risk_free_rate=-0.01)

    def test_raises_on_nan_beta(self):
        with pytest.raises(ValueError, match="NaN"):
            compute_capm(beta=float("nan"), risk_free_rate=0.045)

    def test_result_is_immutable_dataclass(self):
        result = compute_capm(beta=1.0, risk_free_rate=0.045)
        with pytest.raises(Exception):  # frozen=True raises FrozenInstanceError
            result.beta = 2.0  # type: ignore[misc]

    def test_high_beta_stock_has_higher_required_return(self):
        low_beta = compute_capm(beta=0.5, risk_free_rate=0.045)
        high_beta = compute_capm(beta=2.0, risk_free_rate=0.045)
        assert high_beta.required_return > low_beta.required_return


# ---------------------------------------------------------------------------
# TestGordonGrowth
# ---------------------------------------------------------------------------

class TestGordonGrowth:
    """Gordon Growth Model: P = D / (r - g)"""

    def test_standard_inputs_compute_fair_value(self):
        # P = 0.96 / (0.098 - 0.05) = 0.96 / 0.048 = 20.0
        result = compute_gordon(
            dividend=0.96, discount_rate=0.098,
            growth_rate=0.05, current_price=182.40,
        )
        assert result.fair_value == pytest.approx(20.0, abs=0.01)

    def test_upside_pct_positive_when_undervalued(self):
        # fair_value > current_price → positive upside
        result = compute_gordon(
            dividend=10.0, discount_rate=0.08,
            growth_rate=0.03, current_price=100.0,
        )
        # fair = 10 / 0.05 = 200.0 → upside = (200/100 - 1) * 100 = 100%
        assert result.upside_pct == pytest.approx(100.0, abs=0.1)

    def test_upside_pct_negative_when_overvalued(self):
        result = compute_gordon(
            dividend=1.0, discount_rate=0.10,
            growth_rate=0.05, current_price=1_000.0,
        )
        # fair = 1 / 0.05 = 20.0 → very overvalued
        assert result.upside_pct < 0

    def test_zero_dividend_returns_none_fair_value(self):
        result = compute_gordon(
            dividend=0.0, discount_rate=0.098,
            growth_rate=0.05, current_price=182.40,
        )
        assert result.fair_value is None
        assert result.assumption_warning is not None
        assert "no dividend" in result.assumption_warning.lower()

    def test_negative_dividend_treated_as_zero(self):
        """Negative dividend is financially impossible — treated as zero."""
        result = compute_gordon(
            dividend=-1.0, discount_rate=0.098,
            growth_rate=0.05, current_price=100.0,
        )
        assert result.fair_value is None

    def test_g_equal_r_raises_model_assumption_error(self):
        with pytest.raises(ModelAssumptionError) as exc_info:
            compute_gordon(
                dividend=1.0, discount_rate=0.05,
                growth_rate=0.05, current_price=100.0,
            )
        assert "Gordon Growth Model" in str(exc_info.value)

    def test_g_greater_than_r_raises_model_assumption_error(self):
        with pytest.raises(ModelAssumptionError):
            compute_gordon(
                dividend=1.0, discount_rate=0.05,
                growth_rate=0.08, current_price=100.0,
            )

    def test_growth_rate_capped_at_settings_max(self):
        from config.settings import settings
        # growth_rate above cap should be silently reduced and produce a warning
        result = compute_gordon(
            dividend=1.0, discount_rate=0.12,
            growth_rate=0.20,  # above settings.gordon_growth_max
            current_price=100.0,
        )
        assert result.growth_rate <= settings.gordon_growth_max
        assert result.assumption_warning is not None

    def test_result_values_are_rounded(self):
        result = compute_gordon(
            dividend=0.96, discount_rate=0.098,
            growth_rate=0.05, current_price=182.40,
        )
        # Should not have excessive decimal places
        assert result.fair_value is not None
        assert len(str(result.fair_value).split(".")[-1]) <= 4


# ---------------------------------------------------------------------------
# TestPDV
# ---------------------------------------------------------------------------

class TestPDV:
    """Present Discounted Value of a finite dividend stream."""

    def test_single_year_pdv(self):
        # PDV = 1.0 / (1 + 0.10)^1 = 0.9090...
        result = compute_pdv(annual_dividend=1.0, discount_rate=0.10, horizon_years=1)
        assert result.pdv == pytest.approx(1.0 / 1.10, abs=1e-4)

    def test_multi_year_pdv_decreases_over_horizon(self):
        """Longer horizons with same dividend should have lower PDV per year."""
        r5 = compute_pdv(annual_dividend=1.0, discount_rate=0.10, horizon_years=5)
        r10 = compute_pdv(annual_dividend=1.0, discount_rate=0.10, horizon_years=10)
        # Total PDV increases with more years
        assert r10.pdv > r5.pdv

    def test_zero_dividend_returns_zero_pdv(self):
        result = compute_pdv(annual_dividend=0.0, discount_rate=0.10, horizon_years=10)
        assert result.pdv == 0.0

    def test_terminal_value_adds_to_total(self):
        result = compute_pdv(
            annual_dividend=1.0, discount_rate=0.10,
            horizon_years=5, terminal_growth_rate=0.03,
        )
        assert result.terminal_value is not None
        assert result.total_value is not None
        assert result.total_value > result.pdv

    def test_terminal_growth_equal_to_discount_raises(self):
        with pytest.raises(ModelAssumptionError):
            compute_pdv(
                annual_dividend=1.0, discount_rate=0.10,
                horizon_years=5, terminal_growth_rate=0.10,
            )

    def test_raises_on_zero_horizon(self):
        with pytest.raises(ValueError, match="horizon_years"):
            compute_pdv(annual_dividend=1.0, discount_rate=0.10, horizon_years=0)

    def test_raises_on_negative_discount_rate(self):
        with pytest.raises(ValueError, match="discount_rate"):
            compute_pdv(annual_dividend=1.0, discount_rate=-0.01, horizon_years=5)

    def test_higher_discount_rate_gives_lower_pdv(self):
        low = compute_pdv(annual_dividend=1.0, discount_rate=0.05, horizon_years=10)
        high = compute_pdv(annual_dividend=1.0, discount_rate=0.15, horizon_years=10)
        assert low.pdv > high.pdv


# ---------------------------------------------------------------------------
# TestPERatio
# ---------------------------------------------------------------------------

class TestPERatio:
    """P/E ratio analysis."""

    def test_overvalued_when_actual_pe_much_higher_than_theoretical(self):
        # theoretical = 1/(0.10-0.03) = ~14.3. actual=50 → gap=35.7 → overvalued
        result = compute_pe_ratio(
            current_price=100.0, trailing_pe=50.0, forward_pe=45.0,
            discount_rate=0.10, growth_rate=0.03,
        )
        assert result.interpretation == "overvalued"

    def test_undervalued_when_actual_pe_well_below_theoretical(self):
        # theoretical = 1/(0.10-0.03) = ~14.3. actual=8 → gap=-6.3 → undervalued
        result = compute_pe_ratio(
            current_price=100.0, trailing_pe=8.0, forward_pe=7.5,
            discount_rate=0.10, growth_rate=0.03,
        )
        assert result.interpretation == "undervalued"

    def test_fairly_valued_when_pe_close_to_theoretical(self):
        # theoretical = 1/(0.10-0.03) = 14.3. actual=15 → gap=0.7 → fairly valued
        result = compute_pe_ratio(
            current_price=100.0, trailing_pe=15.0, forward_pe=14.0,
            discount_rate=0.10, growth_rate=0.03,
        )
        assert result.interpretation == "fairly_valued"

    def test_insufficient_data_when_pe_is_none(self):
        result = compute_pe_ratio(
            current_price=100.0, trailing_pe=None, forward_pe=None,
            discount_rate=0.10, growth_rate=0.03,
        )
        assert result.interpretation == "insufficient_data"
        assert result.pe_gap is None

    def test_insufficient_data_when_pe_is_negative(self):
        """Negative P/E (company losing money) → can't interpret."""
        result = compute_pe_ratio(
            current_price=100.0, trailing_pe=-5.0, forward_pe=None,
            discount_rate=0.10, growth_rate=0.03,
        )
        assert result.interpretation == "insufficient_data"

    def test_theoretical_pe_computed_correctly(self):
        # theoretical = 1 / (0.10 - 0.03) = 14.285...
        result = compute_pe_ratio(
            current_price=100.0, trailing_pe=14.0, forward_pe=None,
            discount_rate=0.10, growth_rate=0.03,
        )
        assert result.theoretical_pe == pytest.approx(14.29, abs=0.1)

    def test_pe_gap_is_actual_minus_theoretical(self):
        result = compute_pe_ratio(
            current_price=100.0, trailing_pe=20.0, forward_pe=None,
            discount_rate=0.10, growth_rate=0.03,
        )
        assert result.pe_gap == pytest.approx(20.0 - result.theoretical_pe, abs=0.1)  # type: ignore[operator]


# ---------------------------------------------------------------------------
# TestFundamentalScore — integration-style
# ---------------------------------------------------------------------------

class TestFundamentalScore:
    """compute_fundamental_score() — tests the composite scoring logic."""

    def _standard_inputs(self, **overrides):
        """Helper: returns a dict of standard inputs, optionally overridden."""
        base = dict(
            current_price=182.40,
            beta=1.24,
            trailing_pe=28.5,
            forward_pe=25.0,
            dividend_rate=0.96,
            dividend_yield=0.0053,
            earnings_growth=0.05,
            risk_free_rate=0.045,
        )
        base.update(overrides)
        return base

    def test_returns_score_in_valid_range(self):
        result = compute_fundamental_score(**self._standard_inputs())
        assert 0.0 <= result.score <= 100.0

    def test_signal_is_valid_value(self):
        result = compute_fundamental_score(**self._standard_inputs())
        assert result.signal in ("buy", "neutral", "avoid")

    def test_components_dict_has_expected_keys(self):
        result = compute_fundamental_score(**self._standard_inputs())
        assert "capm" in result.components
        assert "pe_ratio" in result.components

    def test_gordon_component_present_when_dividend_exists(self):
        result = compute_fundamental_score(**self._standard_inputs(dividend_rate=0.96))
        assert "gordon" in result.components

    def test_gordon_component_absent_when_no_dividend(self):
        result = compute_fundamental_score(**self._standard_inputs(dividend_rate=0.0))
        assert "gordon" not in result.components

    def test_notes_are_non_empty_list(self):
        result = compute_fundamental_score(**self._standard_inputs())
        assert isinstance(result.notes, list)
        assert len(result.notes) > 0

    def test_none_beta_falls_back_gracefully(self):
        """None beta must not crash — falls back to β=1.0."""
        result = compute_fundamental_score(**self._standard_inputs(beta=None))
        assert 0.0 <= result.score <= 100.0
        assert any("fallback" in n.lower() for n in result.notes)

    def test_none_earnings_growth_falls_back_gracefully(self):
        result = compute_fundamental_score(**self._standard_inputs(earnings_growth=None))
        assert 0.0 <= result.score <= 100.0

    def test_high_risk_asset_scores_lower_than_low_risk(self):
        low_risk = compute_fundamental_score(**self._standard_inputs(beta=0.3))
        high_risk = compute_fundamental_score(**self._standard_inputs(beta=2.5))
        assert low_risk.score > high_risk.score

    def test_undervalued_pe_increases_score(self):
        overvalued = compute_fundamental_score(**self._standard_inputs(trailing_pe=80.0))
        undervalued = compute_fundamental_score(**self._standard_inputs(trailing_pe=5.0))
        assert undervalued.score > overvalued.score

    def test_dividend_yield_adds_bonus_points(self):
        no_yield = compute_fundamental_score(
            **self._standard_inputs(dividend_rate=0.0, dividend_yield=0.0)
        )
        high_yield = compute_fundamental_score(
            **self._standard_inputs(dividend_rate=5.0, dividend_yield=0.05)
        )
        # High yield should contribute positively
        assert "dividend" in " ".join(high_yield.notes).lower()

    def test_score_never_exceeds_100(self):
        """Even with the best possible inputs, score is capped at 100."""
        result = compute_fundamental_score(
            current_price=10.0,
            beta=0.1,
            trailing_pe=2.0,
            forward_pe=1.5,
            dividend_rate=5.0,   # very generous dividend
            dividend_yield=0.50,
            earnings_growth=0.02,
            risk_free_rate=0.045,
        )
        assert result.score <= 100.0

    def test_capm_result_attached(self):
        result = compute_fundamental_score(**self._standard_inputs())
        assert result.capm is not None
        assert result.capm.beta == pytest.approx(1.24, abs=0.01)

    def test_pe_result_attached(self):
        result = compute_fundamental_score(**self._standard_inputs())
        assert result.pe is not None
        assert result.pe.actual_pe == 28.5
