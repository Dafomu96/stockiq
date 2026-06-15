"""
Fundamental analysis engine for StockIQ.

Implements the quantitative models from Robert Shiller's work on asset
valuation and the CAPM framework, applied to individual securities.

Models implemented:
    - Capital Asset Pricing Model (CAPM)
    - Gordon Growth Model (Dividend Discount Model)
    - Present Discounted Value (PDV) of future dividends
    - P/E ratio analysis (actual vs theoretical)
    - Fair value assessment (price vs intrinsic value)
    - Fundamental score (0–100) for the composite scoring engine

All functions are pure (no side effects, no I/O). They receive pre-fetched
data and return typed dataclasses. This makes them trivially testable and
reusable across both the Streamlit and FastAPI layers.

References:
    - Shiller, R.J. (2000). Irrational Exuberance. Princeton University Press.
    - Shiller, R.J. (2005). Market Volatility. MIT Press.
    - Bodie, Z., Kane, A., Marcus, A.J. (2014). Investments (10th ed.).
      McGraw-Hill. Chapter 9 (CAPM), Chapter 18 (equity valuation).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from config.exceptions import ModelAssumptionError
from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CAPMResult:
    """Output of the Capital Asset Pricing Model.

    Attributes:
        required_return: Theoretically required annual return for the asset
            given its systematic risk. Decimal (e.g. 0.098 = 9.8%).
        risk_free_rate: Risk-free rate used in the calculation. Decimal.
        market_return: Expected market return used. Decimal.
        beta: Systematic risk coefficient of the asset.
        market_risk_premium: (market_return - risk_free_rate). Decimal.
        excess_return_vs_required: Difference between the asset's historical
            return and the CAPM-required return. Positive = above-average
            risk-adjusted performance. None if historical return unavailable.
    """

    required_return: float
    risk_free_rate: float
    market_return: float
    beta: float
    market_risk_premium: float
    excess_return_vs_required: float | None = None


@dataclass(frozen=True)
class GordonResult:
    """Output of the Gordon Growth Model (Dividend Discount Model).

    Attributes:
        fair_value: Theoretical intrinsic price of the stock. None if the
            model assumptions are violated (g >= r) or dividend is zero.
        current_price: Current market price used for comparison.
        dividend: Annual dividend per share used (next year's expected).
        discount_rate: Rate r used in the denominator (r - g).
        growth_rate: Perpetual dividend growth rate g assumed.
        upside_pct: (fair_value / current_price - 1) * 100. Positive means
            the stock appears undervalued vs the Gordon model.
        assumption_warning: Human-readable warning if model assumptions
            are borderline (e.g. g close to r, or zero dividend).
    """

    fair_value: float | None
    current_price: float
    dividend: float
    discount_rate: float
    growth_rate: float
    upside_pct: float | None = None
    assumption_warning: str | None = None


@dataclass(frozen=True)
class PDVResult:
    """Present Discounted Value of a finite stream of dividends.

    Attributes:
        pdv: Sum of discounted future dividends over the horizon. Decimal.
        horizon_years: Number of years discounted.
        discount_rate: Annual discount rate applied.
        annual_dividend: Dividend per share per year assumed constant.
        terminal_value: PDV of the Gordon terminal value at year N.
            Included only when a terminal growth rate is provided.
        total_value: pdv + terminal_value (None if no terminal value).
    """

    pdv: float
    horizon_years: int
    discount_rate: float
    annual_dividend: float
    terminal_value: float | None = None
    total_value: float | None = None


@dataclass(frozen=True)
class PERatioResult:
    """P/E ratio analysis — actual vs theoretically justified.

    Attributes:
        actual_pe: Trailing P/E from market data. None if unavailable.
        theoretical_pe: 1 / (r - g) from the Gordon/Shiller framework.
            Represents what the P/E *should* be given discount and growth
            rates. See Shiller (2000) Ch. 3.
        forward_pe: Forward P/E from analyst estimates. None if unavailable.
        pe_gap: actual_pe - theoretical_pe. Positive = market paying a
            premium over the theoretical value; negative = discount.
        interpretation: One of "overvalued", "fairly_valued", "undervalued",
            "insufficient_data".
    """

    actual_pe: float | None
    theoretical_pe: float | None
    forward_pe: float | None
    pe_gap: float | None
    interpretation: str


@dataclass(frozen=True)
class FundamentalScore:
    """Composite fundamental score and component breakdown.

    Attributes:
        score: Overall fundamental score in [0, 100]. Higher = more
            attractive from a fundamental standpoint.
        components: Dict mapping component name → sub-score (0–100).
            Keys: "capm", "gordon", "pe_ratio", "dividend_yield".
        signal: "buy", "neutral", or "avoid" derived from score thresholds.
        capm: Full CAPMResult.
        gordon: Full GordonResult. None if no dividend data.
        pe: Full PERatioResult.
        notes: List of human-readable explanations for the score.
    """

    score: float
    components: dict[str, float]
    signal: str
    capm: CAPMResult
    gordon: GordonResult | None
    pe: PERatioResult
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Score thresholds
# ---------------------------------------------------------------------------

_SIGNAL_BUY_THRESHOLD = 60.0     # score >= 60 → buy signal
_SIGNAL_AVOID_THRESHOLD = 40.0   # score < 40  → avoid signal


# ---------------------------------------------------------------------------
# Core model functions
# ---------------------------------------------------------------------------

def compute_capm(
    beta: float,
    risk_free_rate: float,
    market_return: float | None = None,
) -> CAPMResult:
    """Compute the CAPM required return for an asset.

    Formula: r_i = r_f + β_i · (r_m - r_f)
    Source: Sharpe (1964), Lintner (1965). See Bodie et al. (2014) Ch. 9.

    Args:
        beta: Systematic risk coefficient. Typically in [0, 3] for equities.
            Negative beta (e.g. gold miners) is valid.
        risk_free_rate: Current risk-free rate as decimal (e.g. 0.045).
            Use the US 10Y T-bill or equivalent for the asset's currency.
        market_return: Expected annual market return as decimal.
            Defaults to settings.market_return (~10% historical S&P 500).

    Returns:
        CAPMResult with the required return and all input parameters.

    Raises:
        ValueError: If risk_free_rate is negative or beta is NaN.

    Example:
        >>> result = compute_capm(beta=1.24, risk_free_rate=0.045)
        >>> result.required_return  # 0.045 + 1.24 * (0.10 - 0.045)
        0.1132
    """
    if math.isnan(beta):
        raise ValueError("beta cannot be NaN — check the data source")
    if risk_free_rate < 0:
        raise ValueError(
            f"risk_free_rate={risk_free_rate} is negative. "
            "Use the nominal T-bill rate, not a real rate."
        )

    r_m = market_return if market_return is not None else settings.market_return
    market_risk_premium = r_m - risk_free_rate
    required_return = risk_free_rate + beta * market_risk_premium

    logger.debug(
        "capm beta=%.3f rf=%.4f rm=%.4f required=%.4f",
        beta, risk_free_rate, r_m, required_return,
    )

    return CAPMResult(
        required_return=round(required_return, 6),
        risk_free_rate=round(risk_free_rate, 6),
        market_return=round(r_m, 6),
        beta=round(beta, 4),
        market_risk_premium=round(market_risk_premium, 6),
    )


def compute_gordon(
    dividend: float,
    discount_rate: float,
    growth_rate: float,
    current_price: float,
) -> GordonResult:
    """Compute the Gordon Growth Model (Dividend Discount Model) fair value.

    Formula: P = D / (r - g)
    Source: Gordon, M.J. (1962). The Investment, Financing, and Valuation
    of the Corporation. Irwin. See Bodie et al. (2014) Ch. 18.

    The model assumes dividends grow at a constant rate g in perpetuity.
    This is a strong assumption — it works best for mature, dividend-paying
    companies with stable payout ratios.

    Args:
        dividend: Expected annual dividend per share for the *next* year.
            Use trailing dividend * (1 + expected_growth) for forward estimate.
            If zero, returns a GordonResult with fair_value=None and a warning.
        discount_rate: Required return r for the equity (use CAPM output).
            Must be a decimal (e.g. 0.098).
        growth_rate: Perpetual dividend growth rate g as decimal.
            Must be strictly less than discount_rate. Capped at
            settings.gordon_growth_max to prevent unrealistic inputs.
        current_price: Current market price for upside calculation.

    Returns:
        GordonResult with fair_value and upside_pct.
        fair_value is None when assumptions are violated or dividend is 0.

    Raises:
        ModelAssumptionError: If g >= r after applying the growth cap.
            The caller should surface this as a user-visible warning, not
            crash the application.

    Example:
        >>> result = compute_gordon(
        ...     dividend=0.96, discount_rate=0.098,
        ...     growth_rate=0.05, current_price=182.40
        ... )
        >>> result.fair_value  # 0.96 / (0.098 - 0.05)
        20.0  # (simplified example)
    """
    warning: str | None = None

    # --- Handle zero dividend ---
    if dividend <= 0:
        logger.info("gordon dividend=0 fair_value=None ticker_has_no_dividend")
        return GordonResult(
            fair_value=None,
            current_price=current_price,
            dividend=0.0,
            discount_rate=discount_rate,
            growth_rate=growth_rate,
            upside_pct=None,
            assumption_warning=(
                "Gordon Growth Model requires a positive dividend. "
                "This stock pays no dividend — the model does not apply. "
                "Consider using P/E or DCF analysis instead."
            ),
        )

    # --- Cap growth rate to prevent absurd inputs ---
    effective_growth = min(growth_rate, settings.gordon_growth_max)
    if effective_growth != growth_rate:
        warning = (
            f"Provided growth rate g={growth_rate:.1%} exceeds the cap of "
            f"{settings.gordon_growth_max:.1%}. Using {effective_growth:.1%}. "
            "The Gordon model is unreliable for very high growth stocks."
        )
        logger.warning("gordon growth_rate_capped original=%.4f capped=%.4f", growth_rate, effective_growth)

    # --- Core assumption: g must be strictly less than r ---
    if effective_growth >= discount_rate:
        raise ModelAssumptionError(
            model="Gordon Growth Model",
            violation=(
                f"growth rate g={effective_growth:.4f} must be strictly less than "
                f"discount rate r={discount_rate:.4f}. "
                "The model breaks down when g >= r (denominator ≤ 0). "
                "Consider a two-stage DDM for high-growth companies."
            ),
        )

    fair_value = dividend / (discount_rate - effective_growth)
    upside_pct = (fair_value / current_price - 1) * 100

    logger.debug(
        "gordon D=%.4f r=%.4f g=%.4f fair_value=%.2f price=%.2f upside=%.1f%%",
        dividend, discount_rate, effective_growth, fair_value, current_price, upside_pct,
    )

    return GordonResult(
        fair_value=round(fair_value, 4),
        current_price=current_price,
        dividend=dividend,
        discount_rate=discount_rate,
        growth_rate=effective_growth,
        upside_pct=round(upside_pct, 2),
        assumption_warning=warning,
    )


def compute_pdv(
    annual_dividend: float,
    discount_rate: float,
    horizon_years: int,
    terminal_growth_rate: float | None = None,
) -> PDVResult:
    """Compute the Present Discounted Value of a finite dividend stream.

    Formula: PDV = Σ [D / (1+r)^t] for t = 1..N
    Optionally adds a Gordon terminal value at year N:
        TV = D*(1+g) / (r-g)  discounted back N years.

    Source: Shiller (2000) Chapter 3; Bodie et al. (2014) Ch. 18.

    Args:
        annual_dividend: Constant annual dividend per share (simplified).
            For a more accurate model, pass a growing dividend series.
        discount_rate: Annual discount rate as decimal.
        horizon_years: Number of years to discount explicitly. Typically
            5–10 for a medium-term view.
        terminal_growth_rate: If provided, adds a Gordon terminal value
            at year N representing value beyond the horizon. Must be < r.

    Returns:
        PDVResult with pdv, terminal_value, and total_value.

    Raises:
        ValueError: If horizon_years < 1 or discount_rate <= 0.
        ModelAssumptionError: If terminal_growth_rate >= discount_rate.

    Example:
        >>> result = compute_pdv(
        ...     annual_dividend=0.96, discount_rate=0.098,
        ...     horizon_years=10, terminal_growth_rate=0.03
        ... )
    """
    if horizon_years < 1:
        raise ValueError(f"horizon_years={horizon_years} must be >= 1")
    if discount_rate <= 0:
        raise ValueError(f"discount_rate={discount_rate} must be positive")
    if annual_dividend <= 0:
        return PDVResult(
            pdv=0.0,
            horizon_years=horizon_years,
            discount_rate=discount_rate,
            annual_dividend=0.0,
            terminal_value=None,
            total_value=None,
        )

    pdv = sum(
        annual_dividend / (1 + discount_rate) ** t
        for t in range(1, horizon_years + 1)
    )

    terminal_value: float | None = None
    total_value: float | None = None

    if terminal_growth_rate is not None:
        if terminal_growth_rate >= discount_rate:
            raise ModelAssumptionError(
                model="PDV terminal value",
                violation=(
                    f"terminal growth rate g={terminal_growth_rate:.4f} "
                    f"must be < discount rate r={discount_rate:.4f}"
                ),
            )
        # Gordon terminal value at year N, discounted to today
        terminal_dividend = annual_dividend * (1 + terminal_growth_rate)
        tv_at_n = terminal_dividend / (discount_rate - terminal_growth_rate)
        terminal_value = tv_at_n / (1 + discount_rate) ** horizon_years
        total_value = pdv + terminal_value

    logger.debug(
        "pdv D=%.4f r=%.4f N=%d pdv=%.4f tv=%s",
        annual_dividend, discount_rate, horizon_years,
        pdv, f"{terminal_value:.4f}" if terminal_value else "None",
    )

    return PDVResult(
        pdv=round(pdv, 4),
        horizon_years=horizon_years,
        discount_rate=discount_rate,
        annual_dividend=annual_dividend,
        terminal_value=round(terminal_value, 4) if terminal_value is not None else None,
        total_value=round(total_value, 4) if total_value is not None else None,
    )


def compute_pe_ratio(
    current_price: float,
    trailing_pe: float | None,
    forward_pe: float | None,
    discount_rate: float,
    growth_rate: float,
) -> PERatioResult:
    """Analyse the P/E ratio against its theoretically justified value.

    The theoretical P/E from Shiller's framework is:
        P/E = 1 / (r - g)
    which is the Gordon model re-arranged (assuming E ≈ D for a mature firm).
    Source: Shiller (2000) Ch. 3.

    A P/E above the theoretical value implies the market expects higher growth
    than assumed in g, OR the stock is overvalued. Interpretation requires
    judgement — a persistent P/E premium may reflect genuine quality.

    Args:
        current_price: Current market price per share.
        trailing_pe: Actual trailing twelve-month P/E from market data.
            None if unavailable (e.g. negative earnings).
        forward_pe: Forward P/E from analyst estimates. None if unavailable.
        discount_rate: Required return r (from CAPM). Decimal.
        growth_rate: Expected long-term earnings growth g. Decimal.

    Returns:
        PERatioResult with actual vs theoretical P/E and interpretation.
    """
    # Theoretical P/E = 1 / (r - g), valid only when r > g
    theoretical_pe: float | None = None
    if discount_rate > growth_rate and (discount_rate - growth_rate) > 0.001:
        theoretical_pe = round(1 / (discount_rate - growth_rate), 2)

    pe_gap: float | None = None
    interpretation = "insufficient_data"

    if trailing_pe is not None and trailing_pe > 0 and theoretical_pe is not None:
        pe_gap = round(trailing_pe - theoretical_pe, 2)
        # Interpretation bands — loosely calibrated to Shiller's CAPE work
        if pe_gap > 10:
            interpretation = "overvalued"
        elif pe_gap < -5:
            interpretation = "undervalued"
        else:
            interpretation = "fairly_valued"
    elif trailing_pe is not None and trailing_pe <= 0:
        interpretation = "insufficient_data"  # negative earnings

    logger.debug(
        "pe actual=%.1f theoretical=%s gap=%s interpretation=%s",
        trailing_pe or 0,
        f"{theoretical_pe:.1f}" if theoretical_pe else "N/A",
        f"{pe_gap:.1f}" if pe_gap is not None else "N/A",
        interpretation,
    )

    return PERatioResult(
        actual_pe=trailing_pe,
        theoretical_pe=theoretical_pe,
        forward_pe=forward_pe,
        pe_gap=pe_gap,
        interpretation=interpretation,
    )


# ---------------------------------------------------------------------------
# Composite fundamental score
# ---------------------------------------------------------------------------

def compute_fundamental_score(
    current_price: float,
    beta: float | None,
    trailing_pe: float | None,
    forward_pe: float | None,
    dividend_rate: float | None,
    dividend_yield: float | None,
    earnings_growth: float | None,
    risk_free_rate: float,
) -> FundamentalScore:
    """Compute a composite fundamental score (0–100) for a stock.

    Aggregates CAPM, Gordon Growth Model, and P/E analysis into a single
    score suitable for the composite scoring engine in scoring.py.

    Scoring breakdown:
        - CAPM (30 pts): Is the expected return attractive vs systematic risk?
          Full points if required_return < 8% (low-risk asset priced fairly).
          Scales down as required return rises above 12%.
        - Gordon upside (40 pts): How much upside does the Gordon model show?
          Full points at >= 20% upside. Zero at <= -20% (overvalued).
          Skipped (redistributed to P/E) if no dividend.
        - P/E ratio (30 pts): How does the actual P/E compare to theoretical?
          Full points if undervalued. Zero if overvalued by > 10 points.
          Extra weight when Gordon is unavailable.

    Args:
        current_price: Current market price per share.
        beta: Systematic risk coefficient. Uses 1.0 as fallback if None.
        trailing_pe: Trailing twelve-month P/E. None if unavailable.
        forward_pe: Forward P/E. None if unavailable.
        dividend_rate: Annual dividend per share. None if not paying.
        dividend_yield: Dividend / price ratio. None if not paying.
        earnings_growth: Expected earnings growth rate as decimal. Used
            as proxy for g in Gordon/P/E models. Defaults to 0.03 if None.
        risk_free_rate: Current risk-free rate as decimal.

    Returns:
        FundamentalScore with score, signal, component breakdown, and
        human-readable notes explaining the score.
    """
    notes: list[str] = []
    components: dict[str, float] = {}

    # --- Fallbacks for missing data ---
    effective_beta = beta if (beta is not None and not math.isnan(beta)) else 1.0
    if beta is None:
        notes.append("Beta not available — using market beta of 1.0 as fallback.")

    effective_growth = earnings_growth if earnings_growth is not None else 0.03
    if earnings_growth is None:
        notes.append("Earnings growth not available — using conservative 3% estimate.")

    # --- CAPM (30 points) ---
    capm_result = compute_capm(
        beta=effective_beta,
        risk_free_rate=risk_free_rate,
    )
    # Higher required return = riskier asset. We reward low-risk (low β)
    # assets with a higher sub-score. Full score at r_required <= 8%.
    # Zero score at r_required >= 15%.
    r = capm_result.required_return
    if r <= 0.08:
        capm_score = 100.0
    elif r >= 0.15:
        capm_score = 0.0
    else:
        capm_score = round((0.15 - r) / (0.15 - 0.08) * 100, 1)
    components["capm"] = capm_score
    notes.append(
        f"CAPM required return: {r:.1%} (β={effective_beta:.2f}). "
        f"Sub-score: {capm_score:.0f}/100."
    )

    # --- Gordon Growth Model (40 points if dividend, else 0 redistributed) ---
    gordon_result: GordonResult | None = None
    has_dividend = dividend_rate is not None and dividend_rate > 0

    if has_dividend:
        try:
            gordon_result = compute_gordon(
                dividend=dividend_rate,  # type: ignore[arg-type]
                discount_rate=capm_result.required_return,
                growth_rate=effective_growth,
                current_price=current_price,
            )
            if gordon_result.upside_pct is not None:
                upside = gordon_result.upside_pct
                if upside >= 20:
                    gordon_score = 100.0
                elif upside <= -20:
                    gordon_score = 0.0
                else:
                    gordon_score = round((upside + 20) / 40 * 100, 1)
                components["gordon"] = gordon_score
                notes.append(
                    f"Gordon fair value: ${gordon_result.fair_value:.2f} "
                    f"(current: ${current_price:.2f}, upside: {upside:.1f}%). "
                    f"Sub-score: {gordon_score:.0f}/100."
                )
        except ModelAssumptionError as exc:
            notes.append(f"Gordon model skipped: {exc.violation}")
            has_dividend = False  # treat as no-dividend for scoring
    else:
        notes.append(
            "No dividend — Gordon Growth Model not applicable. "
            "P/E weight increased to compensate."
        )

    # --- P/E ratio (30 points, or 70 points if no dividend) ---
    pe_result = compute_pe_ratio(
        current_price=current_price,
        trailing_pe=trailing_pe,
        forward_pe=forward_pe,
        discount_rate=capm_result.required_return,
        growth_rate=effective_growth,
    )

    pe_score: float
    match pe_result.interpretation:
        case "undervalued":
            pe_score = 85.0
        case "fairly_valued":
            pe_score = 60.0
        case "overvalued":
            # Partial credit — moderately overvalued is not a disaster
            gap = pe_result.pe_gap or 0
            pe_score = max(0.0, round(60 - (gap - 10) * 3, 1))
        case _:
            pe_score = 50.0  # insufficient data — neutral
    components["pe_ratio"] = pe_score
    notes.append(
        f"P/E: actual={pe_result.actual_pe or 'N/A'}, "
        f"theoretical={pe_result.theoretical_pe or 'N/A'}. "
        f"Interpretation: {pe_result.interpretation}. "
        f"Sub-score: {pe_score:.0f}/100."
    )

    # --- Dividend yield bonus (up to 10 extra points) ---
    div_bonus = 0.0
    if dividend_yield is not None and dividend_yield > 0:
        # Reward meaningful yield (> 2%) up to a cap.
        # Swensen favours assets with real cash return.
        div_bonus = min(dividend_yield * 200, 10.0)  # 5% yield → 10 pts
        components["dividend_yield"] = round(div_bonus, 1)
        notes.append(
            f"Dividend yield: {dividend_yield:.2%}. Bonus: +{div_bonus:.1f} pts."
        )

    # --- Weighted aggregate ---
    if has_dividend and "gordon" in components:
        # Full model: CAPM 30% + Gordon 40% + P/E 30%
        raw_score = (
            capm_score * 0.30
            + components["gordon"] * 0.40
            + pe_score * 0.30
        )
    else:
        # No dividend: CAPM 30% + P/E 70%
        raw_score = capm_score * 0.30 + pe_score * 0.70

    final_score = round(min(raw_score + div_bonus, 100.0), 1)

    # --- Signal ---
    if final_score >= _SIGNAL_BUY_THRESHOLD:
        signal = "buy"
    elif final_score < _SIGNAL_AVOID_THRESHOLD:
        signal = "avoid"
    else:
        signal = "neutral"

    logger.info(
        "fundamental_score ticker_price=%.2f score=%.1f signal=%s",
        current_price, final_score, signal,
    )

    return FundamentalScore(
        score=final_score,
        components=components,
        signal=signal,
        capm=capm_result,
        gordon=gordon_result,
        pe=pe_result,
        notes=notes,
    )
