"""
P&L simulation engine for StockIQ.

Answers the core investor question: "If I invest X€ in this asset
today, what happens over time?"

The simulator combines three analytical layers:
    1. Scenario analysis (pessimistic / base / optimistic) using the
       CAPM required return, Gordon fair value growth, and historical
       volatility as the three anchors.
    2. Dollar-Cost Averaging (DCA) — the compounding effect of regular
       monthly contributions alongside the initial lump sum.
    3. Risk metrics — maximum drawdown estimate, Value at Risk (95%),
       and Sharpe ratio — so the user understands the downside, not
       just the upside.

Design principles:
    - All functions are pure: same input → same output, no side effects.
    - No market data fetching — receives pre-computed values as arguments.
    - Outputs are typed dataclasses, never raw dicts.
    - Every assumption is documented and surfaced in the output so the
      UI can display it transparently.

Limitations (must be communicated in the UI):
    - All projections assume returns are constant year-over-year. Real
      markets are volatile — sequence-of-returns risk is real.
    - DCA projections assume contributions are made at month-end at the
      same price. Real execution will differ.
    - Risk metrics (VaR, drawdown) are statistical estimates based on
      historical volatility, not guarantees.
    - Tax, transaction costs, and inflation are NOT deducted. Results
      are gross nominal returns.

References:
    - Bodie, Z., Kane, A., Marcus, A.J. (2014). Investments (10th ed.).
      McGraw-Hill. Chapter 5 (risk/return), Chapter 6 (portfolio risk).
    - Sharpe, W.F. (1994). The Sharpe Ratio. Journal of Portfolio
      Management, 21(1), 49–58.
    - Swensen, D.F. (2005). Unconventional Success. Free Press. Ch. 9.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scenario return rates
# These are the same rates used by the Swensen module for consistency.
# The base rate is the CAPM-required return when available; otherwise
# Swensen's long-run 7.2% estimate is the fallback.
# ---------------------------------------------------------------------------

_DEFAULT_PESSIMISTIC_RATE = 0.04    # 4%  — below-average decade
_DEFAULT_BASE_RATE = 0.072          # 7.2% — Swensen long-run estimate
_DEFAULT_OPTIMISTIC_RATE = 0.10     # 10% — historical S&P 500 long-run

# Sharpe ratio risk-free rate fallback (if CAPM rf not supplied)
_DEFAULT_RISK_FREE_RATE = 0.045


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class YearDataPoint:
    """A single year's projected values across all scenarios.

    Attributes:
        year: Year number (1-based).
        pessimistic: Portfolio value under pessimistic scenario.
        base: Portfolio value under base scenario.
        optimistic: Portfolio value under optimistic scenario.
        dca_base: Portfolio value with DCA under base scenario.
            Equal to base if monthly_contribution == 0.
    """

    year: int
    pessimistic: float
    base: float
    optimistic: float
    dca_base: float


@dataclass(frozen=True)
class ScenarioResult:
    """Final outcome of a single return scenario.

    Attributes:
        label: Scenario name ("pessimistic", "base", "optimistic").
        annual_rate: Annual return rate used. Decimal.
        final_value: Total portfolio value at end of horizon.
        total_gain: final_value − initial_investment.
        gain_pct: (total_gain / initial_investment) * 100.
        cagr: Compound Annual Growth Rate over the horizon.
    """

    label: str
    annual_rate: float
    final_value: float
    total_gain: float
    gain_pct: float
    cagr: float


@dataclass(frozen=True)
class DCAResult:
    """Dollar-Cost Averaging simulation result.

    Attributes:
        monthly_contribution: Monthly amount contributed.
        total_contributed: initial_investment + (monthly * 12 * years).
        final_value_base: Final value under base scenario with DCA.
        gain_from_dca: final_value_base − (no-DCA base final value).
            Shows the incremental benefit of regular contributions.
        effective_cagr: Annualised return on total capital contributed.
    """

    monthly_contribution: float
    total_contributed: float
    final_value_base: float
    gain_from_dca: float
    effective_cagr: float


@dataclass(frozen=True)
class RiskMetrics:
    """Quantitative risk estimates for the simulation.

    Attributes:
        annual_volatility: Annualised standard deviation of returns used
            in the simulation. Decimal (e.g. 0.18 = 18%).
        value_at_risk_95: Maximum expected loss over one year at 95%
            confidence level, as a fraction of investment. Decimal.
            VaR formula: base_rate - 1.645 * volatility (parametric).
            Source: Bodie et al. (2014) Chapter 5.
        max_drawdown_estimate: Estimated worst-case peak-to-trough decline
            over the horizon. Based on 2 * annual_volatility heuristic.
            This is an approximation — historical max drawdowns vary widely.
        sharpe_ratio: (base_rate - risk_free_rate) / annual_volatility.
            Measures return per unit of risk. > 1 is generally considered
            good. Source: Sharpe (1994).
        break_even_years: Years required to recover from a VaR-95 loss
            event under the base return scenario.
        volatility_source: Description of where the volatility figure
            came from ("historical", "asset_class_estimate", "default").
    """

    annual_volatility: float
    value_at_risk_95: float
    max_drawdown_estimate: float
    sharpe_ratio: float
    break_even_years: float
    volatility_source: str


@dataclass(frozen=True)
class BreakEvenAnalysis:
    """Break-even analysis: when does the investment turn profitable?

    Attributes:
        break_even_year_base: Year at which cumulative return exceeds 0
            under the base scenario. Always 1 for positive return rates.
        break_even_year_pessimistic: Same for pessimistic scenario.
        gordon_fair_value: Fair value from the Gordon model if available.
            If current price > fair value, includes the years needed to
            grow into the valuation.
        current_price: Price used for comparison with Gordon fair value.
        is_undervalued: True if current_price < gordon_fair_value.
        margin_of_safety: (gordon_fair_value - current_price) / current_price.
            Positive = discount to intrinsic value. Negative = premium.
    """

    break_even_year_base: int
    break_even_year_pessimistic: int
    gordon_fair_value: float | None
    current_price: float | None
    is_undervalued: bool | None
    margin_of_safety: float | None


@dataclass(frozen=True)
class SimulationResult:
    """Complete P&L simulation output for a ticker and investment amount.

    This is the primary output consumed by:
        - pages/simulator.py (Streamlit)
        - routers/simulate.py (FastAPI)

    Attributes:
        ticker: Analysed ticker symbol.
        initial_investment: Starting lump-sum amount.
        horizon_years: Simulation horizon in years.
        scenarios: List of three ScenarioResults (pessimistic/base/optimistic).
        dca: DCA result. None if monthly_contribution == 0.
        risk: Quantitative risk metrics.
        break_even: Break-even analysis.
        year_by_year: Year-by-year data for the chart.
        assumptions: Dict of all assumptions used, for UI transparency.
        notes: Human-readable explanations for the UI education panel.
        disclaimer: Always included — projections are illustrative only.
    """

    ticker: str
    initial_investment: float
    horizon_years: int
    scenarios: list[ScenarioResult]
    dca: DCAResult | None
    risk: RiskMetrics
    break_even: BreakEvenAnalysis
    year_by_year: list[YearDataPoint]
    assumptions: dict[str, object]
    notes: list[str]
    disclaimer: str = field(default=(
        "All projections are illustrative only. They assume constant annual "
        "returns — real markets are volatile. Results are gross nominal returns "
        "and do not account for taxes, inflation, or transaction costs. "
        "Past performance does not guarantee future results. "
        "This is not financial advice."
    ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate(
    ticker: str,
    initial_investment: float,
    horizon_years: int = 10,
    monthly_contribution: float = 0.0,
    annual_volatility: float | None = None,
    capm_required_return: float | None = None,
    gordon_fair_value: float | None = None,
    current_price: float | None = None,
    risk_free_rate: float = _DEFAULT_RISK_FREE_RATE,
    pessimistic_rate: float = _DEFAULT_PESSIMISTIC_RATE,
    base_rate: float | None = None,
    optimistic_rate: float = _DEFAULT_OPTIMISTIC_RATE,
) -> SimulationResult:
    """Run a full P&L simulation for a given ticker and investment amount.

    The base scenario rate is determined in this priority order:
        1. capm_required_return — if provided, use CAPM as the base rate.
           This is the theoretically required return for the asset's risk.
        2. base_rate — if explicitly provided, use that.
        3. _DEFAULT_BASE_RATE (7.2% — Swensen's long-run estimate).

    Args:
        ticker: Ticker symbol for labelling (does not trigger data fetch).
        initial_investment: Lump-sum investment in any currency. Must be > 0.
        horizon_years: Simulation horizon in years. Default: 10.
            Swensen recommends 10+ years for meaningful results.
        monthly_contribution: Optional regular monthly contribution (DCA).
            Default: 0 (lump sum only).
        annual_volatility: Annualised volatility (std dev of returns).
            Used for VaR and Sharpe ratio. If None, an asset-class
            estimate of 18% is used and flagged in output.
        capm_required_return: CAPM required return from fundamentals.
            Used as base scenario rate when provided.
        gordon_fair_value: Gordon Growth Model fair value from fundamentals.
            Used in break-even analysis.
        current_price: Current market price. Used with gordon_fair_value.
        risk_free_rate: Risk-free rate for Sharpe ratio. Default: 4.5%.
        pessimistic_rate: Annual return in pessimistic scenario. Default: 4%.
        base_rate: Explicit base rate override. See priority order above.
        optimistic_rate: Annual return in optimistic scenario. Default: 10%.

    Returns:
        SimulationResult with scenarios, DCA, risk metrics, and chart data.

    Raises:
        ValueError: If initial_investment <= 0 or horizon_years < 1.

    Example:
        result = simulate(
            ticker="AAPL",
            initial_investment=10_000,
            horizon_years=10,
            monthly_contribution=200,
            capm_required_return=0.098,
            gordon_fair_value=201.50,
            current_price=182.40,
            annual_volatility=0.24,
        )
        print(result.scenarios[1].final_value)  # base scenario
    """
    _validate_inputs(initial_investment, horizon_years)

    # Resolve base rate from priority chain
    effective_base_rate = _resolve_base_rate(capm_required_return, base_rate)

    # Resolve volatility
    effective_volatility, vol_source = _resolve_volatility(annual_volatility)

    scenarios = _compute_scenarios(
        initial_investment, horizon_years,
        pessimistic_rate, effective_base_rate, optimistic_rate,
    )

    dca_result: DCAResult | None = None
    if monthly_contribution > 0:
        dca_result = _compute_dca(
            initial_investment, monthly_contribution,
            horizon_years, effective_base_rate,
            scenarios[1].final_value,  # base scenario no-DCA value
        )

    risk = _compute_risk_metrics(
        base_rate=effective_base_rate,
        volatility=effective_volatility,
        risk_free_rate=risk_free_rate,
        initial_investment=initial_investment,
        vol_source=vol_source,
    )

    break_even = _compute_break_even(
        pessimistic_rate=pessimistic_rate,
        base_rate=effective_base_rate,
        gordon_fair_value=gordon_fair_value,
        current_price=current_price,
    )

    year_by_year = _compute_year_by_year(
        initial_investment, monthly_contribution,
        horizon_years, pessimistic_rate, effective_base_rate, optimistic_rate,
    )

    assumptions = _build_assumptions(
        pessimistic_rate, effective_base_rate, optimistic_rate,
        effective_volatility, vol_source, risk_free_rate,
        capm_required_return, monthly_contribution,
    )

    notes = _build_notes(
        scenarios, dca_result, risk, break_even, effective_base_rate,
        capm_required_return,
    )

    logger.info(
        "simulation ticker=%s investment=%.0f horizon=%dy "
        "base_rate=%.3f base_final=%.0f",
        ticker, initial_investment, horizon_years,
        effective_base_rate, scenarios[1].final_value,
    )

    return SimulationResult(
        ticker=ticker.upper(),
        initial_investment=initial_investment,
        horizon_years=horizon_years,
        scenarios=scenarios,
        dca=dca_result,
        risk=risk,
        break_even=break_even,
        year_by_year=year_by_year,
        assumptions=assumptions,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_inputs(initial_investment: float, horizon_years: int) -> None:
    if initial_investment <= 0:
        raise ValueError(
            f"initial_investment must be positive, got {initial_investment}. "
            "Use a positive number representing the amount to invest."
        )
    if horizon_years < 1:
        raise ValueError(
            f"horizon_years must be >= 1, got {horizon_years}."
        )
    if horizon_years > 50:
        raise ValueError(
            f"horizon_years={horizon_years} exceeds the 50-year cap. "
            "Projections beyond 50 years have no meaningful precision."
        )


# ---------------------------------------------------------------------------
# Core computation helpers
# ---------------------------------------------------------------------------

def _resolve_base_rate(
    capm_required_return: float | None,
    explicit_base_rate: float | None,
) -> float:
    """Resolve base scenario rate from priority chain.

    Priority: CAPM required return > explicit base_rate > default 7.2%.
    """
    if capm_required_return is not None and capm_required_return > 0:
        logger.debug(
            "base_rate resolved from CAPM: %.4f", capm_required_return
        )
        return capm_required_return
    if explicit_base_rate is not None:
        logger.debug(
            "base_rate resolved from explicit: %.4f", explicit_base_rate
        )
        return explicit_base_rate
    logger.debug("base_rate using Swensen default: %.4f", _DEFAULT_BASE_RATE)
    return _DEFAULT_BASE_RATE


def _resolve_volatility(
    annual_volatility: float | None,
) -> tuple[float, str]:
    """Resolve volatility with fallback and source labelling.

    Returns:
        Tuple of (volatility_decimal, source_description).
    """
    if annual_volatility is not None and annual_volatility > 0:
        return annual_volatility, "historical"
    # Fallback: broad equity market estimate (S&P 500 long-run ~18%)
    # Bodie et al. (2014) Chapter 5, Table 5.3
    return 0.18, "asset_class_estimate (S&P 500 long-run ~18%)"


def _compute_scenarios(
    initial: float,
    years: int,
    pessimistic_rate: float,
    base_rate: float,
    optimistic_rate: float,
) -> list[ScenarioResult]:
    """Compute final values and CAGR for each return scenario."""
    results: list[ScenarioResult] = []

    for label, rate in [
        ("pessimistic", pessimistic_rate),
        ("base", base_rate),
        ("optimistic", optimistic_rate),
    ]:
        final_value = round(initial * (1 + rate) ** years, 2)
        total_gain = round(final_value - initial, 2)
        gain_pct = round((total_gain / initial) * 100, 2)
        # CAGR = (final/initial)^(1/years) - 1
        cagr = round((final_value / initial) ** (1 / years) - 1, 6)

        results.append(ScenarioResult(
            label=label,
            annual_rate=rate,
            final_value=final_value,
            total_gain=total_gain,
            gain_pct=gain_pct,
            cagr=cagr,
        ))

    return results


def _compute_dca(
    initial: float,
    monthly: float,
    years: int,
    base_rate: float,
    base_final_no_dca: float,
) -> DCAResult:
    """Compute DCA final value and incremental benefit.

    DCA future value formula (ordinary annuity):
        FV = PMT * [(1 + r/12)^(12*n) - 1] / (r/12)

    Where PMT = monthly contribution, r = annual rate, n = years.
    Source: Bodie et al. (2014) Chapter 5.

    Args:
        initial: Lump-sum initial investment.
        monthly: Monthly DCA contribution.
        years: Horizon in years.
        base_rate: Annual return rate for base scenario.
        base_final_no_dca: Base scenario final value without DCA,
            used to compute the incremental benefit.
    """
    monthly_rate = base_rate / 12
    n_months = years * 12
    total_contributed = round(initial + monthly * n_months, 2)

    # FV of initial lump sum
    fv_lump = initial * (1 + base_rate) ** years

    # FV of monthly contributions (ordinary annuity)
    if monthly_rate > 0:
        fv_annuity = monthly * ((1 + monthly_rate) ** n_months - 1) / monthly_rate
    else:
        fv_annuity = monthly * n_months  # zero interest edge case

    final_value = round(fv_lump + fv_annuity, 2)
    gain_from_dca = round(final_value - base_final_no_dca, 2)

    # Effective CAGR on total capital contributed
    if total_contributed > 0 and final_value > 0:
        effective_cagr = round(
            (final_value / total_contributed) ** (1 / years) - 1, 6
        )
    else:
        effective_cagr = 0.0

    return DCAResult(
        monthly_contribution=monthly,
        total_contributed=total_contributed,
        final_value_base=final_value,
        gain_from_dca=gain_from_dca,
        effective_cagr=effective_cagr,
    )


def _compute_risk_metrics(
    base_rate: float,
    volatility: float,
    risk_free_rate: float,
    initial_investment: float,
    vol_source: str,
) -> RiskMetrics:
    """Compute quantitative risk estimates.

    VaR (95%, parametric, 1-year):
        VaR = base_rate - 1.645 * volatility
        Source: Bodie et al. (2014) Chapter 5, equation 5.15.
        Interpretation: with 95% confidence, the loss will not exceed
        |VaR| in a single year.

    Max drawdown estimate:
        2 * annual_volatility is a conservative heuristic for single-year
        peak-to-trough. Actual drawdowns depend on serial correlation
        and market regime.

    Sharpe ratio:
        (base_rate - risk_free_rate) / volatility
        Source: Sharpe (1994). > 1.0 is generally considered good.

    Break-even after VaR loss:
        Years to recover from a VaR-95 loss event at the base rate.
    """
    # Parametric VaR (1-year, 95% confidence)
    z_95 = 1.645  # 95th percentile of standard normal
    var_95 = base_rate - z_95 * volatility  # may be negative (a loss)
    var_loss_fraction = max(-var_95, 0.0)  # express as positive loss fraction

    # Max drawdown estimate (heuristic)
    max_dd = min(2.0 * volatility, 1.0)  # cap at 100% loss

    # Sharpe ratio
    if volatility > 0:
        sharpe = round((base_rate - risk_free_rate) / volatility, 4)
    else:
        sharpe = 0.0

    # Break-even years: (1 - var_loss)^(1/n) * (1 + base_rate)^n = 1
    # Approximation: n = -ln(1 - var_loss_fraction) / ln(1 + base_rate)
    if var_loss_fraction > 0 and base_rate > 0:
        try:
            break_even_yrs = round(
                -math.log(1 - var_loss_fraction) / math.log(1 + base_rate), 1
            )
        except (ValueError, ZeroDivisionError):
            break_even_yrs = float("inf")
    else:
        break_even_yrs = 0.0

    return RiskMetrics(
        annual_volatility=round(volatility, 4),
        value_at_risk_95=round(var_loss_fraction, 4),
        max_drawdown_estimate=round(max_dd, 4),
        sharpe_ratio=sharpe,
        break_even_years=break_even_yrs,
        volatility_source=vol_source,
    )


def _compute_break_even(
    pessimistic_rate: float,
    base_rate: float,
    gordon_fair_value: float | None,
    current_price: float | None,
) -> BreakEvenAnalysis:
    """Compute break-even analysis with optional Gordon fair value context."""
    # Break-even year for a lump-sum investment with positive rates is always 1
    # (the investment is positive from day 1). We report year 1 for both.
    break_even_base = 1
    break_even_pess = 1 if pessimistic_rate > 0 else 0

    # Gordon margin of safety
    is_undervalued: bool | None = None
    margin_of_safety: float | None = None

    if gordon_fair_value is not None and current_price is not None and current_price > 0:
        is_undervalued = gordon_fair_value > current_price
        margin_of_safety = round(
            (gordon_fair_value - current_price) / current_price, 4
        )

    return BreakEvenAnalysis(
        break_even_year_base=break_even_base,
        break_even_year_pessimistic=break_even_pess,
        gordon_fair_value=gordon_fair_value,
        current_price=current_price,
        is_undervalued=is_undervalued,
        margin_of_safety=margin_of_safety,
    )


def _compute_year_by_year(
    initial: float,
    monthly: float,
    years: int,
    pessimistic_rate: float,
    base_rate: float,
    optimistic_rate: float,
) -> list[YearDataPoint]:
    """Compute year-by-year portfolio values for all scenarios.

    DCA base uses the annuity formula for each year t.
    """
    monthly_rate = base_rate / 12
    data: list[YearDataPoint] = []

    for t in range(1, years + 1):
        pess = round(initial * (1 + pessimistic_rate) ** t, 2)
        base = round(initial * (1 + base_rate) ** t, 2)
        opt = round(initial * (1 + optimistic_rate) ** t, 2)

        # DCA base: lump sum + annuity up to year t
        n_months = t * 12
        fv_lump = initial * (1 + base_rate) ** t
        if monthly > 0 and monthly_rate > 0:
            fv_annuity = monthly * ((1 + monthly_rate) ** n_months - 1) / monthly_rate
        elif monthly > 0:
            fv_annuity = monthly * n_months
        else:
            fv_annuity = 0.0
        dca_base = round(fv_lump + fv_annuity, 2)

        data.append(YearDataPoint(
            year=t,
            pessimistic=pess,
            base=base,
            optimistic=opt,
            dca_base=dca_base,
        ))

    return data


def _build_assumptions(
    pessimistic_rate: float,
    base_rate: float,
    optimistic_rate: float,
    volatility: float,
    vol_source: str,
    risk_free_rate: float,
    capm_required_return: float | None,
    monthly_contribution: float,
) -> dict[str, object]:
    """Build a transparent assumptions dict for the UI panel.

    The UI should display these assumptions prominently so users
    understand the basis of every projection.
    """
    base_rate_source = (
        f"CAPM required return ({capm_required_return:.1%})"
        if capm_required_return is not None
        else "Swensen long-run estimate (7.2%)"
    )

    return {
        "pessimistic_rate": f"{pessimistic_rate:.1%}",
        "base_rate": f"{base_rate:.1%}",
        "base_rate_source": base_rate_source,
        "optimistic_rate": f"{optimistic_rate:.1%}",
        "annual_volatility": f"{volatility:.1%}",
        "volatility_source": vol_source,
        "risk_free_rate": f"{risk_free_rate:.1%}",
        "monthly_contribution": f"{monthly_contribution:,.2f}",
        "return_type": "gross nominal (taxes and costs not deducted)",
        "var_confidence": "95% parametric (Bodie et al. 2014, Ch.5)",
        "sharpe_formula": "(base_rate - rf) / volatility (Sharpe 1994)",
    }


def _build_notes(
    scenarios: list[ScenarioResult],
    dca: DCAResult | None,
    risk: RiskMetrics,
    break_even: BreakEvenAnalysis,
    base_rate: float,
    capm_required_return: float | None,
) -> list[str]:
    """Build educational notes for the UI education panel."""
    notes: list[str] = []
    base = scenarios[1]
    pess = scenarios[0]
    opt = scenarios[2]

    notes.append(
        f"Base scenario ({base.annual_rate:.1%}/yr): "
        f"initial investment grows to {base.final_value:,.0f} "
        f"(+{base.gain_pct:.1f}%) over {base.final_value:.0f} years. "
        + (
            f"Rate derived from CAPM required return — "
            f"this is what the market theoretically demands for this asset's risk."
            if capm_required_return is not None
            else "Rate based on Swensen's long-run 7.2% equity estimate."
        )
    )

    notes.append(
        f"Pessimistic scenario ({pess.annual_rate:.1%}/yr): "
        f"models a below-average decade (e.g. 2000–2010 US equity returns). "
        f"Final value: {pess.final_value:,.0f} (+{pess.gain_pct:.1f}%)."
    )

    notes.append(
        f"Optimistic scenario ({opt.annual_rate:.1%}/yr): "
        f"models a strong decade (e.g. 1990s bull market). "
        f"Final value: {opt.final_value:,.0f} (+{opt.gain_pct:.1f}%)."
    )

    if dca is not None:
        notes.append(
            f"DCA ({dca.monthly_contribution:,.0f}/month): "
            f"regular contributions add {dca.gain_from_dca:,.0f} vs lump-sum only. "
            f"Total contributed: {dca.total_contributed:,.0f}. "
            f"Effective CAGR on all capital: {dca.effective_cagr:.1%}. "
            "Swensen (2005) p.22: 'Regular contributions smooth entry price "
            "and reduce timing risk.'"
        )

    notes.append(
        f"Risk — Sharpe ratio: {risk.sharpe_ratio:.2f}. "
        f"VaR (95%, 1yr): {risk.value_at_risk_95:.1%} of investment. "
        f"Estimated max drawdown: {risk.max_drawdown_estimate:.1%}. "
        "Source: Bodie, Kane, Marcus (2014) Investments, Ch. 5."
    )

    if break_even.margin_of_safety is not None:
        mos = break_even.margin_of_safety
        direction = "discount to" if mos > 0 else "premium over"
        notes.append(
            f"Gordon margin of safety: {abs(mos):.1%} {direction} intrinsic value. "
            + (
                "Positive margin of safety provides a buffer against errors "
                "in the growth rate assumption."
                if mos > 0
                else "Negative margin means you are paying above intrinsic value. "
                "Ensure the growth rate assumption is conservative."
            )
        )

    notes.append(
        "Important: all returns are gross nominal. Taxes, inflation (~2–3% p.a.), "
        "and transaction costs will reduce real returns. "
        "Swensen (2005) Ch. 3: 'The tyranny of costs compounds silently.'"
    )

    return notes
