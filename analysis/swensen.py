"""
Portfolio allocation engine for StockIQ — Swensen framework.

Implements the long-term portfolio philosophy from David Swensen's
"Unconventional Success: A Fundamental Approach to Personal Investment"
(Free Press, 2005), adapted for individual investors using low-cost ETFs.

Core principles implemented:
    1. Six diversified asset classes with low correlation to each other.
    2. Low-cost passive instruments (index ETFs) over active funds.
    3. Annual rebalancing with a 5% drift threshold.
    4. Long-term horizon (10+ years) — not suitable for short-term trading.

What this module does:
    - Defines the canonical Swensen allocation and its ETF mappings.
    - Accepts a user's current portfolio and computes drift from target.
    - Generates rebalancing actions when drift exceeds the threshold.
    - Produces P&L projections under three return scenarios.
    - Provides a SwensenScore (0–100) indicating how well the current
      portfolio aligns with the Swensen philosophy.

What this module does NOT do:
    - It never recommends individual stocks. Swensen was explicit that
      individual investors should not try to pick stocks or time the market.
    - It does not account for taxes, transaction costs, or personal
      circumstances. The user must consult a financial advisor for that.

References:
    Swensen, D.F. (2005). Unconventional Success: A Fundamental Approach
    to Personal Investment. Free Press. ISBN 0-7432-2838-3.
    — Chapter 2: Core Asset Classes
    — Chapter 8: Portfolio Management (rebalancing rules)
    — Chapter 9: Investment Process
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Asset class definitions
# ---------------------------------------------------------------------------

class AssetClass(str, Enum):
    """The six core asset classes in the Swensen model.

    Each class has a specific role in the portfolio. They are selected
    for low correlation with each other — the key to Swensen's approach.

    Reference: Swensen (2005) Chapter 2.
    """

    DOMESTIC_EQUITY = "domestic_equity"
    INTERNATIONAL_EQUITY = "international_equity"
    EMERGING_MARKETS = "emerging_markets"
    REAL_ESTATE = "real_estate"
    GOVERNMENT_BONDS = "government_bonds"
    INFLATION_PROTECTED = "inflation_protected"


# ---------------------------------------------------------------------------
# ETF recommendations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ETFRecommendation:
    """A recommended ETF for a given asset class.

    Swensen's guiding principle: use the lowest-cost passive index fund
    available for each asset class. Active management consistently
    underperforms after fees. (Swensen, 2005, Chapter 3)

    Attributes:
        ticker: Exchange ticker symbol.
        name: Full fund name.
        expense_ratio: Annual TER as decimal (e.g. 0.0003 = 0.03%).
        issuer: Fund provider (Vanguard, Schwab, etc.).
        description: What the fund tracks and why it fits the asset class.
        ucits_alternative: European UCITS-compliant alternative ticker.
            US-domiciled ETFs (VTI, VXUS etc.) are not available to EU
            retail investors — always provide a UCITS alternative.
    """

    ticker: str
    name: str
    expense_ratio: float
    issuer: str
    description: str
    ucits_alternative: str | None = None


# Canonical ETF mapping — one primary + one UCITS alternative per class.
# Expense ratios as of 2024. Review annually.
ETF_RECOMMENDATIONS: dict[AssetClass, ETFRecommendation] = {
    AssetClass.DOMESTIC_EQUITY: ETFRecommendation(
        ticker="VTI",
        name="Vanguard Total Stock Market ETF",
        expense_ratio=0.0003,
        issuer="Vanguard",
        description=(
            "Total US market exposure — ~4,000 stocks. Swensen's preferred "
            "domestic equity vehicle: maximally diversified, minimal cost. "
            "Swensen (2005) p.55."
        ),
        ucits_alternative="VUAA.L",  # Vanguard S&P 500 UCITS ETF (London)
    ),
    AssetClass.INTERNATIONAL_EQUITY: ETFRecommendation(
        ticker="VXUS",
        name="Vanguard Total International Stock ETF",
        expense_ratio=0.0007,
        issuer="Vanguard",
        description=(
            "Developed market equities outside the US — Europe, Japan, "
            "Australia, Canada. Provides currency diversification and "
            "exposure to different economic cycles. Swensen (2005) p.61."
        ),
        ucits_alternative="VWRL.L",  # Vanguard FTSE All-World UCITS ETF
    ),
    AssetClass.EMERGING_MARKETS: ETFRecommendation(
        ticker="VWO",
        name="Vanguard FTSE Emerging Markets ETF",
        expense_ratio=0.0008,
        issuer="Vanguard",
        description=(
            "Exposure to higher-growth developing economies (China, India, "
            "Brazil, Taiwan). Higher risk and return potential than developed "
            "markets. Swensen included this class for long-term return "
            "enhancement. Swensen (2005) p.65."
        ),
        ucits_alternative="EIMI.L",  # iShares Core MSCI EM IMI UCITS ETF
    ),
    AssetClass.REAL_ESTATE: ETFRecommendation(
        ticker="VNQ",
        name="Vanguard Real Estate ETF",
        expense_ratio=0.0012,
        issuer="Vanguard",
        description=(
            "US REITs — real estate investment trusts. Provides inflation "
            "protection and income through dividends. Low correlation with "
            "bonds and moderate correlation with equities makes it a useful "
            "diversifier. Swensen (2005) p.70."
        ),
        ucits_alternative="IPRP.L",  # iShares Developed Markets Property UCITS
    ),
    AssetClass.GOVERNMENT_BONDS: ETFRecommendation(
        ticker="BND",
        name="Vanguard Total Bond Market ETF",
        expense_ratio=0.0003,
        issuer="Vanguard",
        description=(
            "US government and investment-grade corporate bonds. Acts as a "
            "portfolio shock absorber during equity market downturns. "
            "Swensen preferred nominal Treasuries for their negative "
            "correlation with equities in crisis periods. Swensen (2005) p.78."
        ),
        ucits_alternative="VDTY.L",  # Vanguard USD Treasury Bond UCITS ETF
    ),
    AssetClass.INFLATION_PROTECTED: ETFRecommendation(
        ticker="SCHP",
        name="Schwab US TIPS ETF",
        expense_ratio=0.0003,
        issuer="Schwab",
        description=(
            "US Treasury Inflation-Protected Securities (TIPS). The principal "
            "adjusts with CPI, protecting purchasing power. Swensen considered "
            "this the most reliable inflation hedge for individual investors. "
            "Swensen (2005) p.83."
        ),
        ucits_alternative="ITPS.L",  # iShares $ TIPS UCITS ETF
    ),
}

# Canonical Swensen allocation for individual investors.
# Source: Swensen (2005) Appendix — "Model Portfolios for Individual Investors"
# Note: Swensen acknowledged these are starting points, not rigid rules.
CANONICAL_ALLOCATION: dict[AssetClass, float] = {
    AssetClass.DOMESTIC_EQUITY: 0.30,       # 30%
    AssetClass.INTERNATIONAL_EQUITY: 0.15,  # 15%
    AssetClass.EMERGING_MARKETS: 0.05,      # 5%
    AssetClass.REAL_ESTATE: 0.20,           # 20%
    AssetClass.GOVERNMENT_BONDS: 0.15,      # 15%
    AssetClass.INFLATION_PROTECTED: 0.15,   # 15%
}

# Human-readable labels for UI display (bilingual)
ASSET_CLASS_LABELS: dict[AssetClass, dict[str, str]] = {
    AssetClass.DOMESTIC_EQUITY: {
        "en": "Domestic equities (US)",
        "es": "Acciones domésticas (EE.UU.)",
    },
    AssetClass.INTERNATIONAL_EQUITY: {
        "en": "International equities",
        "es": "Acciones internacionales",
    },
    AssetClass.EMERGING_MARKETS: {
        "en": "Emerging markets",
        "es": "Mercados emergentes",
    },
    AssetClass.REAL_ESTATE: {
        "en": "Real estate (REITs)",
        "es": "Inmobiliario (REITs)",
    },
    AssetClass.GOVERNMENT_BONDS: {
        "en": "Government bonds",
        "es": "Bonos de gobierno",
    },
    AssetClass.INFLATION_PROTECTED: {
        "en": "Inflation-protected (TIPS)",
        "es": "Protección contra inflación (TIPS)",
    },
}


# ---------------------------------------------------------------------------
# Portfolio position and rebalancing dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PortfolioPosition:
    """A single asset class position in the user's portfolio.

    Attributes:
        asset_class: The Swensen asset class this position belongs to.
        current_weight: Current weight in the portfolio as decimal (0–1).
        target_weight: Target weight from the Swensen allocation.
        current_value: Current market value in the user's currency.
        drift: current_weight - target_weight. Positive = overweight.
        drift_pct: drift expressed as percentage points.
        needs_rebalancing: True if |drift| > settings.swensen_rebalance_threshold.
        action: "buy", "sell", or "hold" based on drift and threshold.
        etf: Recommended ETF for this position.
    """

    asset_class: AssetClass
    current_weight: float
    target_weight: float
    current_value: float
    drift: float
    drift_pct: float
    needs_rebalancing: bool
    action: str
    etf: ETFRecommendation


@dataclass(frozen=True)
class RebalancingAction:
    """A concrete rebalancing instruction for the UI.

    Attributes:
        asset_class: The asset class to act on.
        action: "buy" or "sell".
        amount: Approximate amount to buy/sell in the user's currency.
            Calculated to bring the position back to target weight,
            assuming total portfolio value is constant.
        current_weight: Current weight before rebalancing.
        target_weight: Target weight after rebalancing.
        etf_ticker: Recommended ETF ticker to execute the trade.
        rationale: Human-readable explanation for the UI.
    """

    asset_class: AssetClass
    action: str
    amount: float
    current_weight: float
    target_weight: float
    etf_ticker: str
    rationale: str


@dataclass(frozen=True)
class GrowthProjection:
    """P&L projection under three return scenarios.

    Attributes:
        initial_investment: Starting portfolio value.
        horizon_years: Projection horizon in years.
        pessimistic_rate: Annual return in the pessimistic scenario.
        base_rate: Annual return in the base (expected) scenario.
        optimistic_rate: Annual return in the optimistic scenario.
        pessimistic_value: Final value under pessimistic scenario.
        base_value: Final value under base scenario.
        optimistic_value: Final value under optimistic scenario.
        year_by_year: List of dicts with {"year", "pessimistic", "base",
            "optimistic"} for each year — for the chart data.

    Note:
        Returns are gross — taxes, inflation, and transaction costs
        are not deducted. The UI must make this explicit.
    """

    initial_investment: float
    horizon_years: int
    pessimistic_rate: float
    base_rate: float
    optimistic_rate: float
    pessimistic_value: float
    base_value: float
    optimistic_value: float
    year_by_year: list[dict[str, float]]


@dataclass(frozen=True)
class SwensenPortfolioResult:
    """Complete output of the Swensen portfolio analyser.

    Attributes:
        positions: All six asset class positions with drift and action.
        rebalancing_actions: Only positions that need rebalancing.
            Empty list if all positions are within threshold.
        total_portfolio_value: Sum of all position values.
        swensen_score: Alignment score 0–100. 100 = perfect Swensen
            allocation. Degrades proportionally with drift.
        needs_rebalancing: True if any position exceeds the threshold.
        projection: 10-year growth projection under three scenarios.
        annual_cost_estimate: Estimated annual cost (TER × portfolio value).
        notes: Educational notes explaining the analysis.
        disclaimer: Always included — models are illustrative only.
    """

    positions: list[PortfolioPosition]
    rebalancing_actions: list[RebalancingAction]
    total_portfolio_value: float
    swensen_score: float
    needs_rebalancing: bool
    projection: GrowthProjection
    annual_cost_estimate: float
    notes: list[str]
    disclaimer: str = field(default=(
        "This portfolio analysis is for educational purposes only. "
        "Swensen's model is a starting point, not a guarantee. "
        "Returns shown are gross historical averages — they do not account "
        "for taxes, inflation, transaction costs, or your personal "
        "financial situation. Consult a qualified financial advisor "
        "before making investment decisions."
    ))


# ---------------------------------------------------------------------------
# Historical return assumptions for projections
# (Swensen's long-run estimates, Unconventional Success p.28)
# ---------------------------------------------------------------------------

_PROJECTION_RATES = {
    "pessimistic": 0.04,   # 4% — below-average decade (e.g. 2000–2010)
    "base": 0.072,         # 7.2% — Swensen's long-run estimate for his model
    "optimistic": 0.10,    # 10% — historical S&P 500 long-run average
}

# Weighted average TER of the canonical ETF portfolio
_CANONICAL_TER = sum(
    ETF_RECOMMENDATIONS[cls].expense_ratio * weight
    for cls, weight in CANONICAL_ALLOCATION.items()
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_portfolio(
    current_allocation: dict[AssetClass, float],
    total_value: float,
    target_allocation: dict[AssetClass, float] | None = None,
    horizon_years: int = 10,
    rebalance_threshold: float | None = None,
) -> SwensenPortfolioResult:
    """Analyse a portfolio against the Swensen framework.

    Args:
        current_allocation: Dict mapping AssetClass → current weight as
            decimal. Weights should sum to 1.0 but are normalised if not.
            Missing asset classes are treated as 0% allocation.
        total_value: Total portfolio value in any currency (used for
            computing rebalancing amounts in absolute terms).
        target_allocation: Custom target allocation. Defaults to
            CANONICAL_ALLOCATION (Swensen's model). Must sum to 1.0.
        horizon_years: Projection horizon for the growth chart.
            Typically 10–20 for long-term investors. Default: 10.
        rebalance_threshold: Drift threshold above which rebalancing
            is triggered. Defaults to settings.swensen_rebalance_threshold
            (5%). Swensen's original rule. Swensen (2005) p.195.

    Returns:
        SwensenPortfolioResult with positions, rebalancing actions,
        score, projection, and educational notes.

    Raises:
        ValueError: If total_value <= 0 or if current_allocation is empty.

    Example:
        result = analyse_portfolio(
            current_allocation={
                AssetClass.DOMESTIC_EQUITY: 0.40,   # overweight
                AssetClass.REAL_ESTATE: 0.20,
                AssetClass.GOVERNMENT_BONDS: 0.25,  # overweight
                AssetClass.INFLATION_PROTECTED: 0.15,
            },
            total_value=50_000.0,
        )
        print(result.swensen_score)    # e.g. 72.4
        print(result.needs_rebalancing)  # True
    """
    if total_value <= 0:
        raise ValueError(f"total_value must be positive, got {total_value}")
    if not current_allocation:
        raise ValueError("current_allocation cannot be empty")

    threshold = rebalance_threshold or settings.swensen_rebalance_threshold
    target = target_allocation or CANONICAL_ALLOCATION

    # Normalise weights if they don't sum to 1 (user might input percentages)
    normalised = _normalise_allocation(current_allocation)

    positions = _compute_positions(normalised, target, total_value, threshold)
    rebalancing_actions = _compute_rebalancing_actions(positions, total_value)
    swensen_score = _compute_swensen_score(positions)
    projection = _compute_projection(total_value, horizon_years)
    annual_cost = _compute_annual_cost(normalised, total_value)
    notes = _build_notes(positions, swensen_score, rebalancing_actions, annual_cost)

    needs_rebalancing = any(p.needs_rebalancing for p in positions)

    logger.info(
        "swensen_analysis total_value=%.0f score=%.1f "
        "needs_rebalancing=%s actions=%d",
        total_value, swensen_score,
        needs_rebalancing, len(rebalancing_actions),
    )

    return SwensenPortfolioResult(
        positions=positions,
        rebalancing_actions=rebalancing_actions,
        total_portfolio_value=total_value,
        swensen_score=swensen_score,
        needs_rebalancing=needs_rebalancing,
        projection=projection,
        annual_cost_estimate=annual_cost,
        notes=notes,
    )


def compute_target_amounts(
    total_value: float,
    target_allocation: dict[AssetClass, float] | None = None,
) -> dict[AssetClass, float]:
    """Return the target monetary amount for each asset class.

    Useful for the "how much should I put in each ETF?" question.

    Args:
        total_value: Total portfolio value.
        target_allocation: Defaults to CANONICAL_ALLOCATION.

    Returns:
        Dict mapping AssetClass → target monetary amount.

    Example:
        amounts = compute_target_amounts(total_value=10_000)
        # {DOMESTIC_EQUITY: 3000.0, REAL_ESTATE: 2000.0, ...}
    """
    target = target_allocation or CANONICAL_ALLOCATION
    return {cls: round(total_value * weight, 2) for cls, weight in target.items()}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _normalise_allocation(
    allocation: dict[AssetClass, float],
) -> dict[AssetClass, float]:
    """Normalise weights to sum to 1.0 and fill missing classes with 0.

    Args:
        allocation: Raw allocation dict — may not sum to 1.0.

    Returns:
        Normalised dict with all six AssetClass keys, summing to 1.0.
    """
    # Fill missing asset classes with zero
    full: dict[AssetClass, float] = {cls: 0.0 for cls in AssetClass}
    full.update(allocation)

    total = sum(full.values())
    if total <= 0:
        return full  # all zeros — return as-is, caller handles edge case

    if abs(total - 1.0) > 0.01:
        logger.warning(
            "allocation weights sum to %.3f — normalising to 1.0", total
        )
        return {cls: w / total for cls, w in full.items()}

    return full


def _compute_positions(
    normalised: dict[AssetClass, float],
    target: dict[AssetClass, float],
    total_value: float,
    threshold: float,
) -> list[PortfolioPosition]:
    """Compute drift and action for each asset class position."""
    positions: list[PortfolioPosition] = []

    for cls in AssetClass:
        current_w = normalised.get(cls, 0.0)
        target_w = target.get(cls, 0.0)
        drift = round(current_w - target_w, 6)
        drift_pct = round(drift * 100, 2)
        current_value = round(current_w * total_value, 2)
        needs_rebalancing = abs(drift) > threshold

        if needs_rebalancing:
            action = "sell" if drift > 0 else "buy"
        else:
            action = "hold"

        positions.append(PortfolioPosition(
            asset_class=cls,
            current_weight=round(current_w, 6),
            target_weight=round(target_w, 6),
            current_value=current_value,
            drift=drift,
            drift_pct=drift_pct,
            needs_rebalancing=needs_rebalancing,
            action=action,
            etf=ETF_RECOMMENDATIONS[cls],
        ))

    return positions


def _compute_rebalancing_actions(
    positions: list[PortfolioPosition],
    total_value: float,
) -> list[RebalancingAction]:
    """Generate concrete rebalancing instructions for drifted positions.

    The amount to trade brings the position exactly back to its target
    weight, assuming no new cash is added. In practice, Swensen recommended
    using new contributions to rebalance before selling — but we compute
    the pure rebalancing amount for clarity.

    Reference: Swensen (2005) p.195 — "Rebalance whenever a position
    drifts more than five percentage points from its target."
    """
    actions: list[RebalancingAction] = []

    for pos in positions:
        if not pos.needs_rebalancing:
            continue

        amount = round(abs(pos.drift) * total_value, 2)
        direction = "above" if pos.drift > 0 else "below"
        rationale = (
            f"{pos.etf.ticker} is {abs(pos.drift_pct):.1f}pp {direction} its "
            f"target of {pos.target_weight:.0%}. "
            f"{'Reduce' if pos.action == 'sell' else 'Increase'} by "
            f"approx. {amount:,.0f} to restore balance. "
            f"Swensen (2005) p.195: rebalance when drift exceeds 5pp."
        )
        actions.append(RebalancingAction(
            asset_class=pos.asset_class,
            action=pos.action,
            amount=amount,
            current_weight=pos.current_weight,
            target_weight=pos.target_weight,
            etf_ticker=pos.etf.ticker,
            rationale=rationale,
        ))

    return actions


def _compute_swensen_score(positions: list[PortfolioPosition]) -> float:
    """Score portfolio alignment with Swensen's model (0–100).

    Score = 100 − (sum of |drift_pct| across all classes) × 2.
    A perfect Swensen portfolio (zero drift) scores 100.
    Each percentage point of total drift reduces the score by 2.
    Score is floored at 0.

    This is a bespoke scoring rule — not from Swensen's book.
    It is clearly labelled as such in the UI.
    """
    total_drift_pct = sum(abs(p.drift_pct) for p in positions)
    score = max(0.0, round(100.0 - total_drift_pct * 2, 1))
    return score


def _compute_projection(
    initial_value: float,
    horizon_years: int,
) -> GrowthProjection:
    """Compute year-by-year portfolio growth under three scenarios.

    Uses Swensen's long-run return estimates (Unconventional Success p.28).
    Returns are gross — the UI must note that taxes and costs are excluded.

    Args:
        initial_value: Starting portfolio value.
        horizon_years: Number of years to project.

    Returns:
        GrowthProjection with year-by-year data and final values.
    """
    rates = _PROJECTION_RATES
    year_by_year: list[dict[str, float]] = []

    for year in range(1, horizon_years + 1):
        year_by_year.append({
            "year": float(year),
            "pessimistic": round(
                initial_value * (1 + rates["pessimistic"]) ** year, 2
            ),
            "base": round(
                initial_value * (1 + rates["base"]) ** year, 2
            ),
            "optimistic": round(
                initial_value * (1 + rates["optimistic"]) ** year, 2
            ),
        })

    final = year_by_year[-1]
    return GrowthProjection(
        initial_investment=initial_value,
        horizon_years=horizon_years,
        pessimistic_rate=rates["pessimistic"],
        base_rate=rates["base"],
        optimistic_rate=rates["optimistic"],
        pessimistic_value=final["pessimistic"],
        base_value=final["base"],
        optimistic_value=final["optimistic"],
        year_by_year=year_by_year,
    )


def _compute_annual_cost(
    normalised: dict[AssetClass, float],
    total_value: float,
) -> float:
    """Estimate annual cost (TER) of the portfolio.

    Uses each asset class's ETF TER weighted by its allocation.
    Swensen was emphatic: costs compound over decades and destroy returns.
    (Swensen, 2005, Chapter 3: "The Tyranny of Costs")

    Args:
        normalised: Normalised allocation dict.
        total_value: Total portfolio value.

    Returns:
        Annual cost estimate in monetary units.
    """
    weighted_ter = sum(
        normalised.get(cls, 0.0) * ETF_RECOMMENDATIONS[cls].expense_ratio
        for cls in AssetClass
    )
    return round(weighted_ter * total_value, 2)


def _build_notes(
    positions: list[PortfolioPosition],
    score: float,
    actions: list[RebalancingAction],
    annual_cost: float,
) -> list[str]:
    """Build educational notes for the UI panel.

    Each note is self-contained and cites Swensen where applicable.
    They explain not just what the numbers are, but why they matter.
    """
    notes: list[str] = []

    notes.append(
        f"Swensen alignment score: {score:.0f}/100. "
        "This measures how closely your portfolio matches the Swensen "
        "model allocation. A score of 100 means zero drift across all classes."
    )

    if not actions:
        notes.append(
            "No rebalancing required. All positions are within the "
            f"{settings.swensen_rebalance_threshold:.0%} drift threshold. "
            "Swensen (2005) p.195: 'Rebalance when positions drift more than "
            "five percentage points from targets.'"
        )
    else:
        overweight = [a for a in actions if a.action == "sell"]
        underweight = [a for a in actions if a.action == "buy"]
        if overweight:
            tickers = ", ".join(a.etf_ticker for a in overweight)
            notes.append(
                f"Overweight positions to reduce: {tickers}. "
                "Selling what has risen most is counter-intuitive but "
                "essential to disciplined rebalancing. "
                "Swensen (2005) p.196: 'Rebalancing forces investors to sell "
                "high and buy low systematically.'"
            )
        if underweight:
            tickers = ", ".join(a.etf_ticker for a in underweight)
            notes.append(
                f"Underweight positions to increase: {tickers}. "
                "If you have new contributions, direct them here first "
                "before selling overweight positions."
            )

    notes.append(
        f"Estimated annual portfolio cost: {annual_cost:.2f} "
        "(weighted average TER of recommended ETFs). "
        "Swensen (2005) Chapter 3: 'The tyranny of compounding costs "
        "devastates investor returns over decades.'"
    )

    notes.append(
        "Investment horizon: Swensen's framework is designed for 10+ year "
        "horizons. Short-term market movements are irrelevant to this strategy. "
        "Swensen (2005) p.22: 'Patient, disciplined investors reap rewards "
        "that active traders cannot.'"
    )

    return notes
