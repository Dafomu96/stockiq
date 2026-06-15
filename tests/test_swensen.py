"""
Tests for analysis/swensen.py.

All tests are pure unit tests — no I/O, no network, no mocks needed.
The functions under test are deterministic and side-effect free.

Test organisation:
    TestNormaliseAllocation       — weight normalisation edge cases
    TestComputePositions          — drift calculation and action assignment
    TestRebalancingActions        — concrete rebalancing instructions
    TestSwensenScore              — alignment score computation
    TestGrowthProjection          — P&L projection scenarios
    TestAnalysePortfolio          — main public API (integration-style)
    TestComputeTargetAmounts      — target monetary amounts helper
    TestCanonicalAllocation       — invariants of the built-in model
"""

import pytest

from analysis.swensen import (
    CANONICAL_ALLOCATION,
    ETF_RECOMMENDATIONS,
    AssetClass,
    SwensenPortfolioResult,
    analyse_portfolio,
    compute_target_amounts,
    _normalise_allocation,
    _compute_swensen_score,
    _compute_projection,
    _compute_annual_cost,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _perfect_allocation() -> dict[AssetClass, float]:
    """Return the canonical Swensen allocation — zero drift."""
    return dict(CANONICAL_ALLOCATION)


def _drifted_allocation() -> dict[AssetClass, float]:
    """Return an allocation with deliberate drift for testing."""
    return {
        AssetClass.DOMESTIC_EQUITY: 0.45,       # +15pp (overweight)
        AssetClass.INTERNATIONAL_EQUITY: 0.15,  # on target
        AssetClass.EMERGING_MARKETS: 0.05,      # on target
        AssetClass.REAL_ESTATE: 0.10,           # -10pp (underweight)
        AssetClass.GOVERNMENT_BONDS: 0.15,      # on target
        AssetClass.INFLATION_PROTECTED: 0.10,   # -5pp (at threshold)
    }


# ---------------------------------------------------------------------------
# TestCanonicalAllocation
# ---------------------------------------------------------------------------

class TestCanonicalAllocation:
    def test_canonical_allocation_sums_to_one(self):
        total = sum(CANONICAL_ALLOCATION.values())
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_canonical_allocation_has_six_classes(self):
        assert len(CANONICAL_ALLOCATION) == 6

    def test_all_asset_classes_have_positive_weight(self):
        for cls, weight in CANONICAL_ALLOCATION.items():
            assert weight > 0, f"{cls} has non-positive weight"

    def test_all_asset_classes_have_etf_recommendation(self):
        for cls in AssetClass:
            assert cls in ETF_RECOMMENDATIONS

    def test_all_etfs_have_positive_expense_ratio(self):
        for cls, etf in ETF_RECOMMENDATIONS.items():
            assert etf.expense_ratio > 0, f"{cls} ETF has zero TER"

    def test_all_etfs_have_ucits_alternative(self):
        """EU investors can't buy US-domiciled ETFs — UCITS must always exist."""
        for cls, etf in ETF_RECOMMENDATIONS.items():
            assert etf.ucits_alternative is not None, (
                f"{cls} ETF {etf.ticker} has no UCITS alternative"
            )

    def test_domestic_equity_is_largest_allocation(self):
        """Swensen's model has 30% domestic equity as the anchor."""
        assert CANONICAL_ALLOCATION[AssetClass.DOMESTIC_EQUITY] == 0.30


# ---------------------------------------------------------------------------
# TestNormaliseAllocation
# ---------------------------------------------------------------------------

class TestNormaliseAllocation:
    def test_perfect_allocation_unchanged(self):
        result = _normalise_allocation(_perfect_allocation())
        assert sum(result.values()) == pytest.approx(1.0, abs=1e-6)

    def test_missing_classes_filled_with_zero(self):
        partial = {AssetClass.DOMESTIC_EQUITY: 1.0}
        result = _normalise_allocation(partial)
        assert result[AssetClass.REAL_ESTATE] == 0.0
        assert result[AssetClass.GOVERNMENT_BONDS] == 0.0

    def test_weights_normalised_when_sum_not_one(self):
        """If user inputs 40+30+30 = 100 (%), normalise to decimals."""
        unnormalised = {
            AssetClass.DOMESTIC_EQUITY: 0.40,
            AssetClass.REAL_ESTATE: 0.30,
            AssetClass.GOVERNMENT_BONDS: 0.50,  # sum = 1.20, not 1.0
        }
        result = _normalise_allocation(unnormalised)
        assert sum(result.values()) == pytest.approx(1.0, abs=1e-4)

    def test_all_six_classes_always_present_in_output(self):
        partial = {AssetClass.DOMESTIC_EQUITY: 1.0}
        result = _normalise_allocation(partial)
        assert len(result) == 6
        for cls in AssetClass:
            assert cls in result

    def test_zero_allocation_returns_all_zeros(self):
        empty = {cls: 0.0 for cls in AssetClass}
        result = _normalise_allocation(empty)
        assert all(v == 0.0 for v in result.values())


# ---------------------------------------------------------------------------
# TestComputePositions (via analyse_portfolio)
# ---------------------------------------------------------------------------

class TestComputePositions:
    def test_perfect_portfolio_has_zero_drift(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        for pos in result.positions:
            assert abs(pos.drift) < 1e-6

    def test_perfect_portfolio_action_is_hold(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        for pos in result.positions:
            assert pos.action == "hold"

    def test_overweight_position_action_is_sell(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        domestic = next(
            p for p in result.positions
            if p.asset_class == AssetClass.DOMESTIC_EQUITY
        )
        assert domestic.action == "sell"
        assert domestic.drift > 0

    def test_underweight_position_action_is_buy(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        reits = next(
            p for p in result.positions
            if p.asset_class == AssetClass.REAL_ESTATE
        )
        assert reits.action == "buy"
        assert reits.drift < 0

    def test_drift_pct_equals_drift_times_100(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        for pos in result.positions:
            assert pos.drift_pct == pytest.approx(pos.drift * 100, abs=0.01)

    def test_current_value_consistent_with_weight_and_total(self):
        total = 50_000.0
        result = analyse_portfolio(_perfect_allocation(), total_value=total)
        for pos in result.positions:
            expected = pos.current_weight * total
            assert pos.current_value == pytest.approx(expected, abs=0.01)

    def test_positions_list_has_six_entries(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert len(result.positions) == 6

    def test_each_position_has_etf_recommendation(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        for pos in result.positions:
            assert pos.etf is not None
            assert pos.etf.ticker != ""


# ---------------------------------------------------------------------------
# TestRebalancingActions
# ---------------------------------------------------------------------------

class TestRebalancingActions:
    def test_no_actions_when_portfolio_is_perfect(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert result.rebalancing_actions == []

    def test_drifted_portfolio_generates_actions(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        assert len(result.rebalancing_actions) > 0

    def test_action_amounts_are_positive(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        for action in result.rebalancing_actions:
            assert action.amount > 0

    def test_sell_action_for_overweight_position(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        domestic_action = next(
            (a for a in result.rebalancing_actions
             if a.asset_class == AssetClass.DOMESTIC_EQUITY), None
        )
        assert domestic_action is not None
        assert domestic_action.action == "sell"

    def test_buy_action_for_underweight_position(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        reit_action = next(
            (a for a in result.rebalancing_actions
             if a.asset_class == AssetClass.REAL_ESTATE), None
        )
        assert reit_action is not None
        assert reit_action.action == "buy"

    def test_action_amount_proportional_to_drift(self):
        """Larger drift → larger rebalancing amount."""
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        amounts = {a.asset_class: a.amount for a in result.rebalancing_actions}
        # Domestic equity has +15pp drift, REITS has -10pp drift
        # Domestic action should be larger
        if (AssetClass.DOMESTIC_EQUITY in amounts
                and AssetClass.REAL_ESTATE in amounts):
            assert amounts[AssetClass.DOMESTIC_EQUITY] > amounts[AssetClass.REAL_ESTATE]

    def test_rebalancing_action_has_rationale(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        for action in result.rebalancing_actions:
            assert len(action.rationale) > 20

    def test_rationale_cites_swensen(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        for action in result.rebalancing_actions:
            assert "Swensen" in action.rationale

    def test_custom_threshold_respected(self):
        """Custom threshold of 1% should trigger more rebalancing actions."""
        tight = analyse_portfolio(
            _drifted_allocation(), total_value=10_000, rebalance_threshold=0.01
        )
        standard = analyse_portfolio(
            _drifted_allocation(), total_value=10_000
        )
        assert len(tight.rebalancing_actions) >= len(standard.rebalancing_actions)


# ---------------------------------------------------------------------------
# TestSwensenScore
# ---------------------------------------------------------------------------

class TestSwensenScore:
    def test_perfect_portfolio_scores_100(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert result.swensen_score == pytest.approx(100.0, abs=0.1)

    def test_drifted_portfolio_scores_below_100(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        assert result.swensen_score < 100.0

    def test_score_in_valid_range(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        assert 0.0 <= result.swensen_score <= 100.0

    def test_more_drift_means_lower_score(self):
        slightly_off = {
            AssetClass.DOMESTIC_EQUITY: 0.32,  # +2pp
            AssetClass.INTERNATIONAL_EQUITY: 0.15,
            AssetClass.EMERGING_MARKETS: 0.05,
            AssetClass.REAL_ESTATE: 0.18,      # -2pp
            AssetClass.GOVERNMENT_BONDS: 0.15,
            AssetClass.INFLATION_PROTECTED: 0.15,
        }
        good = analyse_portfolio(slightly_off, total_value=10_000)
        bad = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        assert good.swensen_score > bad.swensen_score

    def test_score_never_negative(self):
        """Extreme drift should floor at 0, not go negative."""
        extreme = {
            AssetClass.DOMESTIC_EQUITY: 1.0,
            AssetClass.INTERNATIONAL_EQUITY: 0.0,
            AssetClass.EMERGING_MARKETS: 0.0,
            AssetClass.REAL_ESTATE: 0.0,
            AssetClass.GOVERNMENT_BONDS: 0.0,
            AssetClass.INFLATION_PROTECTED: 0.0,
        }
        result = analyse_portfolio(extreme, total_value=10_000)
        assert result.swensen_score >= 0.0


# ---------------------------------------------------------------------------
# TestGrowthProjection
# ---------------------------------------------------------------------------

class TestGrowthProjection:
    def test_base_value_higher_than_pessimistic(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert result.projection.base_value > result.projection.pessimistic_value

    def test_optimistic_value_higher_than_base(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert result.projection.optimistic_value > result.projection.base_value

    def test_all_final_values_above_initial(self):
        """All scenarios assume positive returns."""
        initial = 10_000.0
        result = analyse_portfolio(_perfect_allocation(), total_value=initial)
        assert result.projection.pessimistic_value > initial
        assert result.projection.base_value > initial
        assert result.projection.optimistic_value > initial

    def test_year_by_year_has_correct_length(self):
        result = analyse_portfolio(
            _perfect_allocation(), total_value=10_000, horizon_years=20
        )
        assert len(result.projection.year_by_year) == 20

    def test_year_by_year_values_increase_monotonically(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        bases = [row["base"] for row in result.projection.year_by_year]
        assert all(bases[i] < bases[i + 1] for i in range(len(bases) - 1))

    def test_final_year_matches_standalone_calculation(self):
        initial = 10_000.0
        years = 10
        result = analyse_portfolio(
            _perfect_allocation(), total_value=initial, horizon_years=years
        )
        expected_base = round(initial * (1 + 0.072) ** years, 2)
        assert result.projection.base_value == pytest.approx(expected_base, abs=0.1)

    def test_projection_horizon_matches_input(self):
        result = analyse_portfolio(
            _perfect_allocation(), total_value=10_000, horizon_years=15
        )
        assert result.projection.horizon_years == 15


# ---------------------------------------------------------------------------
# TestAnalysePortfolio — main public API
# ---------------------------------------------------------------------------

class TestAnalysePortfolio:
    def test_returns_swensen_portfolio_result(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert isinstance(result, SwensenPortfolioResult)

    def test_result_is_frozen(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        with pytest.raises(Exception):
            result.swensen_score = 99.0  # type: ignore[misc]

    def test_total_value_stored_correctly(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=25_000.0)
        assert result.total_portfolio_value == 25_000.0

    def test_raises_on_negative_total_value(self):
        with pytest.raises(ValueError, match="positive"):
            analyse_portfolio(_perfect_allocation(), total_value=-1000.0)

    def test_raises_on_zero_total_value(self):
        with pytest.raises(ValueError, match="positive"):
            analyse_portfolio(_perfect_allocation(), total_value=0.0)

    def test_raises_on_empty_allocation(self):
        with pytest.raises(ValueError, match="empty"):
            analyse_portfolio({}, total_value=10_000.0)

    def test_needs_rebalancing_false_for_perfect(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert result.needs_rebalancing is False

    def test_needs_rebalancing_true_for_drifted(self):
        result = analyse_portfolio(_drifted_allocation(), total_value=10_000)
        assert result.needs_rebalancing is True

    def test_notes_list_non_empty(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert len(result.notes) > 0

    def test_notes_cite_swensen(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert any("Swensen" in note for note in result.notes)

    def test_disclaimer_always_present(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert "financial advisor" in result.disclaimer.lower()

    def test_custom_target_allocation_respected(self):
        """User can override the Swensen allocation with their own."""
        custom = {cls: 1/6 for cls in AssetClass}  # equal weight
        result = analyse_portfolio(
            _perfect_allocation(), total_value=10_000,
            target_allocation=custom,
        )
        for pos in result.positions:
            assert pos.target_weight == pytest.approx(1/6, abs=1e-4)

    def test_annual_cost_positive(self):
        result = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        assert result.annual_cost_estimate > 0

    def test_annual_cost_scales_with_portfolio_size(self):
        small = analyse_portfolio(_perfect_allocation(), total_value=10_000)
        large = analyse_portfolio(_perfect_allocation(), total_value=100_000)
        assert large.annual_cost_estimate == pytest.approx(
            small.annual_cost_estimate * 10, abs=0.01
        )


# ---------------------------------------------------------------------------
# TestComputeTargetAmounts
# ---------------------------------------------------------------------------

class TestComputeTargetAmounts:
    def test_amounts_sum_to_total_value(self):
        total = 50_000.0
        amounts = compute_target_amounts(total_value=total)
        assert sum(amounts.values()) == pytest.approx(total, abs=0.01)

    def test_domestic_equity_amount_is_30_percent(self):
        amounts = compute_target_amounts(total_value=10_000)
        assert amounts[AssetClass.DOMESTIC_EQUITY] == pytest.approx(3_000.0, abs=0.01)

    def test_has_all_six_asset_classes(self):
        amounts = compute_target_amounts(total_value=10_000)
        assert len(amounts) == 6
        for cls in AssetClass:
            assert cls in amounts

    def test_all_amounts_positive(self):
        amounts = compute_target_amounts(total_value=10_000)
        for cls, amount in amounts.items():
            assert amount > 0

    def test_custom_allocation_respected(self):
        custom = {AssetClass.DOMESTIC_EQUITY: 1.0,
                  **{cls: 0.0 for cls in AssetClass
                     if cls != AssetClass.DOMESTIC_EQUITY}}
        amounts = compute_target_amounts(
            total_value=10_000, target_allocation=custom
        )
        assert amounts[AssetClass.DOMESTIC_EQUITY] == pytest.approx(10_000.0)
