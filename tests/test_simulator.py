"""
Tests for simulation/simulator.py.

All tests are pure unit tests — no I/O, no network, no mocks needed.
The functions under test are deterministic and side-effect free.

Test organisation:
    TestValidateInputs          — input validation and error raising
    TestResolveBaseRate         — base rate priority chain
    TestComputeScenarios        — scenario values and CAGR
    TestComputeDCA              — DCA formula correctness
    TestRiskMetrics             — VaR, Sharpe, break-even
    TestBreakEvenAnalysis       — Gordon margin of safety
    TestYearByYear              — chart data generation
    TestSimulate                — public API (integration-style)
    TestSimulationResultContract — shape and invariants of the output
"""

import math

import pytest

from simulation.simulator import (
    SimulationResult,
    _compute_break_even,
    _compute_dca,
    _compute_risk_metrics,
    _compute_scenarios,
    _compute_year_by_year,
    _resolve_base_rate,
    _resolve_volatility,
    simulate,
)


# ---------------------------------------------------------------------------
# TestValidateInputs
# ---------------------------------------------------------------------------

class TestValidateInputs:
    def test_raises_on_zero_investment(self):
        with pytest.raises(ValueError, match="positive"):
            simulate("AAPL", initial_investment=0.0)

    def test_raises_on_negative_investment(self):
        with pytest.raises(ValueError, match="positive"):
            simulate("AAPL", initial_investment=-1000.0)

    def test_raises_on_zero_horizon(self):
        with pytest.raises(ValueError, match="horizon_years"):
            simulate("AAPL", initial_investment=1000.0, horizon_years=0)

    def test_raises_on_negative_horizon(self):
        with pytest.raises(ValueError, match="horizon_years"):
            simulate("AAPL", initial_investment=1000.0, horizon_years=-1)

    def test_raises_on_horizon_above_50(self):
        with pytest.raises(ValueError, match="50-year cap"):
            simulate("AAPL", initial_investment=1000.0, horizon_years=51)

    def test_accepts_horizon_of_exactly_50(self):
        result = simulate("AAPL", initial_investment=1000.0, horizon_years=50)
        assert result.horizon_years == 50

    def test_accepts_valid_inputs(self):
        result = simulate("AAPL", initial_investment=10_000.0, horizon_years=10)
        assert result is not None


# ---------------------------------------------------------------------------
# TestResolveBaseRate
# ---------------------------------------------------------------------------

class TestResolveBaseRate:
    def test_capm_takes_priority_over_explicit(self):
        rate = _resolve_base_rate(
            capm_required_return=0.095, explicit_base_rate=0.08
        )
        assert rate == pytest.approx(0.095, abs=1e-6)

    def test_explicit_used_when_no_capm(self):
        rate = _resolve_base_rate(
            capm_required_return=None, explicit_base_rate=0.08
        )
        assert rate == pytest.approx(0.08, abs=1e-6)

    def test_default_used_when_both_none(self):
        from simulation.simulator import _DEFAULT_BASE_RATE
        rate = _resolve_base_rate(
            capm_required_return=None, explicit_base_rate=None
        )
        assert rate == pytest.approx(_DEFAULT_BASE_RATE, abs=1e-6)

    def test_zero_capm_falls_through_to_explicit(self):
        """CAPM rate of 0 is treated as not provided."""
        rate = _resolve_base_rate(
            capm_required_return=0.0, explicit_base_rate=0.08
        )
        assert rate == pytest.approx(0.08, abs=1e-6)


# ---------------------------------------------------------------------------
# TestResolveVolatility
# ---------------------------------------------------------------------------

class TestResolveVolatility:
    def test_provided_volatility_used_directly(self):
        vol, source = _resolve_volatility(0.24)
        assert vol == pytest.approx(0.24, abs=1e-6)
        assert source == "historical"

    def test_none_volatility_returns_default(self):
        vol, source = _resolve_volatility(None)
        assert vol == pytest.approx(0.18, abs=1e-4)
        assert "estimate" in source.lower()

    def test_zero_volatility_returns_default(self):
        vol, source = _resolve_volatility(0.0)
        assert vol == pytest.approx(0.18, abs=1e-4)


# ---------------------------------------------------------------------------
# TestComputeScenarios
# ---------------------------------------------------------------------------

class TestComputeScenarios:
    def test_returns_three_scenarios(self):
        results = _compute_scenarios(10_000, 10, 0.04, 0.072, 0.10)
        assert len(results) == 3

    def test_scenario_labels_correct(self):
        results = _compute_scenarios(10_000, 10, 0.04, 0.072, 0.10)
        labels = [r.label for r in results]
        assert labels == ["pessimistic", "base", "optimistic"]

    def test_base_final_value_correct(self):
        # 10_000 * (1.072)^10 = 10_000 * 2.00007... ≈ 20,001
        results = _compute_scenarios(10_000, 10, 0.04, 0.072, 0.10)
        base = results[1]
        expected = 10_000 * (1.072 ** 10)
        assert base.final_value == pytest.approx(expected, rel=0.001)

    def test_optimistic_greater_than_base_greater_than_pessimistic(self):
        results = _compute_scenarios(10_000, 10, 0.04, 0.072, 0.10)
        assert results[2].final_value > results[1].final_value > results[0].final_value

    def test_gain_pct_consistent_with_final_value(self):
        results = _compute_scenarios(10_000, 10, 0.04, 0.072, 0.10)
        for r in results:
            expected_gain_pct = ((r.final_value - 10_000) / 10_000) * 100
            assert r.gain_pct == pytest.approx(expected_gain_pct, abs=0.01)

    def test_cagr_consistent_with_annual_rate(self):
        """For constant returns, CAGR must equal the annual rate."""
        results = _compute_scenarios(10_000, 10, 0.04, 0.072, 0.10)
        for r in results:
            assert r.cagr == pytest.approx(r.annual_rate, abs=0.001)

    def test_all_final_values_above_initial(self):
        results = _compute_scenarios(10_000, 10, 0.04, 0.072, 0.10)
        for r in results:
            assert r.final_value > 10_000

    def test_single_year_horizon(self):
        results = _compute_scenarios(10_000, 1, 0.04, 0.072, 0.10)
        base = results[1]
        assert base.final_value == pytest.approx(10_000 * 1.072, abs=0.01)


# ---------------------------------------------------------------------------
# TestComputeDCA
# ---------------------------------------------------------------------------

class TestComputeDCA:
    def test_total_contributed_includes_lump_and_monthly(self):
        result = _compute_dca(
            initial=10_000, monthly=200, years=10,
            base_rate=0.072, base_final_no_dca=20_000
        )
        expected = 10_000 + 200 * 12 * 10
        assert result.total_contributed == pytest.approx(expected, abs=0.01)

    def test_final_value_above_no_dca_value(self):
        """DCA adds contributions, so final value must exceed no-DCA."""
        no_dca_base = 10_000 * (1.072 ** 10)
        result = _compute_dca(
            initial=10_000, monthly=200, years=10,
            base_rate=0.072, base_final_no_dca=no_dca_base
        )
        assert result.final_value_base > no_dca_base

    def test_gain_from_dca_positive(self):
        no_dca_base = 10_000 * (1.072 ** 10)
        result = _compute_dca(
            initial=10_000, monthly=500, years=10,
            base_rate=0.072, base_final_no_dca=no_dca_base
        )
        assert result.gain_from_dca > 0

    def test_higher_monthly_gives_higher_final_value(self):
        no_dca = 10_000 * (1.072 ** 10)
        low = _compute_dca(10_000, 100, 10, 0.072, no_dca)
        high = _compute_dca(10_000, 500, 10, 0.072, no_dca)
        assert high.final_value_base > low.final_value_base

    def test_effective_cagr_positive_for_positive_rate(self):
        no_dca = 10_000 * (1.072 ** 10)
        result = _compute_dca(10_000, 200, 10, 0.072, no_dca)
        assert result.effective_cagr > 0

    def test_dca_annuity_formula_precision(self):
        """Verify the DCA formula against a manually computed value."""
        initial = 10_000
        monthly = 100
        years = 5
        r_annual = 0.10
        r_monthly = r_annual / 12
        n = years * 12

        fv_lump = initial * (1 + r_annual) ** years
        fv_annuity = monthly * ((1 + r_monthly) ** n - 1) / r_monthly
        expected = round(fv_lump + fv_annuity, 2)

        no_dca = initial * (1 + r_annual) ** years
        result = _compute_dca(initial, monthly, years, r_annual, no_dca)
        assert result.final_value_base == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# TestRiskMetrics
# ---------------------------------------------------------------------------

class TestRiskMetrics:
    def test_sharpe_ratio_formula_correct(self):
        # Sharpe = (0.072 - 0.045) / 0.18 = 0.027 / 0.18 = 0.15
        risk = _compute_risk_metrics(
            base_rate=0.072, volatility=0.18,
            risk_free_rate=0.045, initial_investment=10_000,
            vol_source="historical",
        )
        assert risk.sharpe_ratio == pytest.approx(0.027 / 0.18, abs=0.001)

    def test_var_95_positive_for_high_volatility(self):
        """High volatility should produce a meaningful loss estimate."""
        risk = _compute_risk_metrics(
            base_rate=0.072, volatility=0.30,
            risk_free_rate=0.045, initial_investment=10_000,
            vol_source="historical",
        )
        # VaR = max(-(0.072 - 1.645*0.30), 0) = max(0.4215, 0) = 0.4215
        assert risk.value_at_risk_95 > 0

    def test_var_95_zero_for_very_high_return_low_vol(self):
        """If base_rate >> volatility, VaR is zero (no expected loss)."""
        risk = _compute_risk_metrics(
            base_rate=0.50, volatility=0.01,
            risk_free_rate=0.045, initial_investment=10_000,
            vol_source="historical",
        )
        assert risk.value_at_risk_95 == 0.0

    def test_max_drawdown_capped_at_100_pct(self):
        """Max drawdown cannot exceed 100% of investment."""
        risk = _compute_risk_metrics(
            base_rate=0.05, volatility=0.80,
            risk_free_rate=0.045, initial_investment=10_000,
            vol_source="historical",
        )
        assert risk.max_drawdown_estimate <= 1.0

    def test_max_drawdown_proportional_to_volatility(self):
        low_vol = _compute_risk_metrics(0.07, 0.10, 0.045, 10_000, "historical")
        high_vol = _compute_risk_metrics(0.07, 0.30, 0.045, 10_000, "historical")
        assert high_vol.max_drawdown_estimate > low_vol.max_drawdown_estimate

    def test_break_even_positive_for_meaningful_loss(self):
        risk = _compute_risk_metrics(
            base_rate=0.072, volatility=0.25,
            risk_free_rate=0.045, initial_investment=10_000,
            vol_source="historical",
        )
        # With significant VaR, break-even should be > 0
        if risk.value_at_risk_95 > 0:
            assert risk.break_even_years > 0

    def test_volatility_source_stored_correctly(self):
        risk = _compute_risk_metrics(
            base_rate=0.072, volatility=0.18,
            risk_free_rate=0.045, initial_investment=10_000,
            vol_source="historical",
        )
        assert risk.volatility_source == "historical"


# ---------------------------------------------------------------------------
# TestBreakEvenAnalysis
# ---------------------------------------------------------------------------

class TestBreakEvenAnalysis:
    def test_undervalued_when_fair_value_above_price(self):
        result = _compute_break_even(0.04, 0.072, gordon_fair_value=200.0, current_price=150.0)
        assert result.is_undervalued is True

    def test_overvalued_when_fair_value_below_price(self):
        result = _compute_break_even(0.04, 0.072, gordon_fair_value=100.0, current_price=150.0)
        assert result.is_undervalued is False

    def test_margin_of_safety_computed_correctly(self):
        # (200 - 150) / 150 = 0.3333
        result = _compute_break_even(0.04, 0.072, gordon_fair_value=200.0, current_price=150.0)
        assert result.margin_of_safety == pytest.approx(0.3333, abs=0.001)

    def test_negative_margin_when_overvalued(self):
        result = _compute_break_even(0.04, 0.072, gordon_fair_value=100.0, current_price=150.0)
        assert result.margin_of_safety is not None
        assert result.margin_of_safety < 0

    def test_none_gordon_gives_none_margin(self):
        result = _compute_break_even(0.04, 0.072, gordon_fair_value=None, current_price=150.0)
        assert result.margin_of_safety is None
        assert result.is_undervalued is None

    def test_none_current_price_gives_none_margin(self):
        result = _compute_break_even(0.04, 0.072, gordon_fair_value=200.0, current_price=None)
        assert result.margin_of_safety is None


# ---------------------------------------------------------------------------
# TestYearByYear
# ---------------------------------------------------------------------------

class TestYearByYear:
    def test_length_equals_horizon(self):
        data = _compute_year_by_year(10_000, 0, 10, 0.04, 0.072, 0.10)
        assert len(data) == 10

    def test_year_numbers_are_sequential(self):
        data = _compute_year_by_year(10_000, 0, 5, 0.04, 0.072, 0.10)
        years = [d.year for d in data]
        assert years == [1, 2, 3, 4, 5]

    def test_base_values_increase_monotonically(self):
        data = _compute_year_by_year(10_000, 0, 10, 0.04, 0.072, 0.10)
        bases = [d.base for d in data]
        assert all(bases[i] < bases[i + 1] for i in range(len(bases) - 1))

    def test_optimistic_always_above_base(self):
        data = _compute_year_by_year(10_000, 0, 10, 0.04, 0.072, 0.10)
        assert all(d.optimistic > d.base for d in data)

    def test_pessimistic_always_below_base(self):
        data = _compute_year_by_year(10_000, 0, 10, 0.04, 0.072, 0.10)
        assert all(d.pessimistic < d.base for d in data)

    def test_dca_base_equals_base_when_no_monthly(self):
        data = _compute_year_by_year(10_000, 0, 5, 0.04, 0.072, 0.10)
        for d in data:
            assert d.dca_base == pytest.approx(d.base, abs=0.01)

    def test_dca_base_above_base_when_monthly_positive(self):
        data = _compute_year_by_year(10_000, 200, 10, 0.04, 0.072, 0.10)
        for d in data:
            assert d.dca_base >= d.base


# ---------------------------------------------------------------------------
# TestSimulate — public API
# ---------------------------------------------------------------------------

class TestSimulate:
    def test_returns_simulation_result(self):
        result = simulate("AAPL", 10_000)
        assert isinstance(result, SimulationResult)

    def test_ticker_uppercased(self):
        result = simulate("aapl", 10_000)
        assert result.ticker == "AAPL"

    def test_three_scenarios_always_present(self):
        result = simulate("AAPL", 10_000)
        assert len(result.scenarios) == 3

    def test_dca_none_when_no_monthly_contribution(self):
        result = simulate("AAPL", 10_000, monthly_contribution=0.0)
        assert result.dca is None

    def test_dca_present_when_monthly_contribution_given(self):
        result = simulate("AAPL", 10_000, monthly_contribution=200.0)
        assert result.dca is not None

    def test_capm_rate_used_as_base(self):
        result = simulate(
            "AAPL", 10_000, capm_required_return=0.095
        )
        base_scenario = result.scenarios[1]
        assert base_scenario.annual_rate == pytest.approx(0.095, abs=1e-6)

    def test_gordon_fair_value_flows_to_break_even(self):
        result = simulate(
            "AAPL", 10_000,
            gordon_fair_value=201.50,
            current_price=182.40,
        )
        assert result.break_even.gordon_fair_value == 201.50
        assert result.break_even.is_undervalued is True

    def test_year_by_year_length_matches_horizon(self):
        result = simulate("AAPL", 10_000, horizon_years=15)
        assert len(result.year_by_year) == 15

    def test_notes_non_empty(self):
        result = simulate("AAPL", 10_000)
        assert len(result.notes) > 0

    def test_assumptions_dict_has_required_keys(self):
        result = simulate("AAPL", 10_000)
        assert "base_rate" in result.assumptions
        assert "annual_volatility" in result.assumptions
        assert "return_type" in result.assumptions

    def test_assumptions_flags_gross_returns(self):
        result = simulate("AAPL", 10_000)
        assert "gross" in str(result.assumptions["return_type"]).lower()

    def test_disclaimer_always_present(self):
        result = simulate("AAPL", 10_000)
        assert "financial advice" in result.disclaimer.lower()

    def test_result_is_frozen(self):
        result = simulate("AAPL", 10_000)
        with pytest.raises(Exception):
            result.initial_investment = 99_999.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestSimulationResultContract
# ---------------------------------------------------------------------------

class TestSimulationResultContract:
    """Ensure the shape of SimulationResult is stable — this is the API contract."""

    def _r(self) -> SimulationResult:
        return simulate(
            "AAPL",
            initial_investment=10_000,
            horizon_years=10,
            monthly_contribution=200,
            capm_required_return=0.098,
            gordon_fair_value=201.50,
            current_price=182.40,
            annual_volatility=0.24,
        )

    def test_ticker_is_string(self):
        assert isinstance(self._r().ticker, str)

    def test_initial_investment_matches_input(self):
        assert self._r().initial_investment == 10_000.0

    def test_horizon_matches_input(self):
        assert self._r().horizon_years == 10

    def test_all_scenario_labels_present(self):
        labels = {s.label for s in self._r().scenarios}
        assert labels == {"pessimistic", "base", "optimistic"}

    def test_risk_metrics_present(self):
        r = self._r()
        assert r.risk is not None
        assert r.risk.sharpe_ratio is not None

    def test_break_even_present(self):
        r = self._r()
        assert r.break_even is not None

    def test_dca_present_when_monthly_given(self):
        assert self._r().dca is not None

    def test_notes_reference_sources(self):
        notes_text = " ".join(self._r().notes)
        # At least one source reference
        assert any(
            ref in notes_text
            for ref in ["Swensen", "Bodie", "Sharpe", "CAPM"]
        )
