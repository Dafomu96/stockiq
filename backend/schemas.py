"""
Pydantic request and response schemas for the StockIQ FastAPI backend.

These are the public API contracts. Changing a field name or type here
is a breaking change — bump the API version prefix (/v1/ → /v2/).

Design decisions:
    - Request bodies use Pydantic BaseModel for automatic validation,
      documentation, and OpenAPI schema generation.
    - Response models mirror the analysis dataclasses but are Pydantic
      models so they serialise cleanly to JSON (including nested objects
      and enums).
    - Nested objects are flattened where it aids readability in the
      client, and kept nested where the structure carries meaning.
    - All monetary values are plain floats — the currency is a separate
      string field. The API never assumes a currency.

See: ADR-004 — Why Pydantic v2 for schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str = "ok"
    version: str
    message: str


# ---------------------------------------------------------------------------
# Analyse endpoint — POST /v1/analyze
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Request body for POST /v1/analyze.

    Attributes:
        ticker: Any globally-traded ticker symbol. Yahoo Finance format.
            Append exchange suffix for non-US stocks (e.g. 'ASML.AS').
        period: yfinance period string for price history.
            '1y' gives ~252 bars — sufficient for all indicators.
        strategy: Scoring strategy to apply.
            'weighted_average' (default) or 'fundamental_only'.
    """

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Ticker symbol (e.g. 'AAPL', 'ASML.AS', '7203.T')",
        examples=["AAPL", "ASML.AS"],
    )
    period: str = Field(
        default="1y",
        description="Price history period (yfinance format: '1y', '2y', '6mo')",
        examples=["1y"],
    )
    strategy: str = Field(
        default="weighted_average",
        description="Scoring strategy: 'weighted_average' or 'fundamental_only'",
    )

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("period")
    @classmethod
    def period_valid(cls, v: str) -> str:
        valid = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
        if v not in valid:
            raise ValueError(f"period must be one of {sorted(valid)}")
        return v

    @field_validator("strategy")
    @classmethod
    def strategy_valid(cls, v: str) -> str:
        valid = {"weighted_average", "fundamental_only"}
        if v not in valid:
            raise ValueError(f"strategy must be one of {sorted(valid)}")
        return v


class CAPMOut(BaseModel):
    required_return: float
    risk_free_rate: float
    market_return: float
    beta: float
    market_risk_premium: float


class GordonOut(BaseModel):
    fair_value: float | None
    current_price: float
    dividend: float
    discount_rate: float
    growth_rate: float
    upside_pct: float | None
    assumption_warning: str | None


class PERatioOut(BaseModel):
    actual_pe: float | None
    theoretical_pe: float | None
    forward_pe: float | None
    pe_gap: float | None
    interpretation: str


class FundamentalOut(BaseModel):
    score: float
    signal: str
    components: dict[str, float]
    capm: CAPMOut
    gordon: GordonOut | None
    pe: PERatioOut
    notes: list[str]


class RSIOut(BaseModel):
    value: float | None
    signal: str
    overbought_threshold: float
    oversold_threshold: float


class MACDOut(BaseModel):
    macd: float | None
    signal_line: float | None
    histogram: float | None
    signal: str
    is_bullish_crossover: bool
    is_bearish_crossover: bool


class BollingerOut(BaseModel):
    upper: float | None
    middle: float | None
    lower: float | None
    bandwidth: float | None
    percent_b: float | None
    signal: str


class MovingAverageOut(BaseModel):
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    ema_20: float | None
    current_price: float
    golden_cross: bool
    death_cross: bool
    price_above_sma200: bool
    signal: str


class OBVOut(BaseModel):
    current_obv: float | None
    obv_sma: float | None
    volume_trend: str
    confirms_price_trend: bool
    signal: str


class ADXOut(BaseModel):
    adx: float | None
    plus_di: float | None
    minus_di: float | None
    trend_strength: str
    signal: str


class TechnicalOut(BaseModel):
    score: float
    signal: str
    components: dict[str, float]
    rsi: RSIOut
    macd: MACDOut
    bollinger: BollingerOut
    moving_averages: MovingAverageOut
    obv: OBVOut
    adx: ADXOut
    notes: list[str]
    data_quality_warnings: list[str]


class AnalyzeResponse(BaseModel):
    """Response for POST /v1/analyze.

    The complete analysis result including fundamental, technical,
    and composite scoring. Mirrors CompositeResult from scoring.py.
    """

    ticker: str
    composite_score: float
    signal: str
    strategy_name: str
    weights: dict[str, float]
    score_breakdown: dict[str, float]
    confidence: str
    confidence_reasons: list[str]
    fundamental: FundamentalOut
    technical: TechnicalOut
    summary_notes: list[str]
    analysed_at: str
    disclaimer: str


# ---------------------------------------------------------------------------
# Portfolio endpoint — POST /v1/portfolio
# ---------------------------------------------------------------------------

class PortfolioRequest(BaseModel):
    """Request body for POST /v1/portfolio.

    Attributes:
        current_allocation: Dict mapping asset class name → weight (decimal).
            Missing classes are treated as 0%. Weights are normalised if
            they don't sum to 1.0.
        total_value: Total portfolio value in any currency.
        horizon_years: Projection horizon. Default: 10.
        rebalance_threshold: Drift threshold. Default: 0.05 (5pp).
    """

    current_allocation: dict[str, float] = Field(
        ...,
        description=(
            "Asset class weights as decimals. "
            "Keys: domestic_equity, international_equity, emerging_markets, "
            "real_estate, government_bonds, inflation_protected."
        ),
        examples=[{
            "domestic_equity": 0.40,
            "international_equity": 0.15,
            "emerging_markets": 0.05,
            "real_estate": 0.15,
            "government_bonds": 0.15,
            "inflation_protected": 0.10,
        }],
    )
    total_value: float = Field(
        ..., gt=0, description="Total portfolio value (any currency)", examples=[50000.0]
    )
    horizon_years: int = Field(
        default=10, ge=1, le=30, description="Projection horizon in years"
    )
    rebalance_threshold: float = Field(
        default=0.05, ge=0.01, le=0.20,
        description="Drift threshold for rebalancing (default 5%)"
    )

    @field_validator("current_allocation")
    @classmethod
    def validate_allocation_values(cls, v: dict[str, float]) -> dict[str, float]:
        valid_keys = {
            "domestic_equity", "international_equity", "emerging_markets",
            "real_estate", "government_bonds", "inflation_protected",
        }
        unknown = set(v.keys()) - valid_keys
        if unknown:
            raise ValueError(
                f"Unknown asset class(es): {unknown}. "
                f"Valid keys: {sorted(valid_keys)}"
            )
        for key, weight in v.items():
            if not (0.0 <= weight <= 1.0):
                raise ValueError(
                    f"Weight for '{key}' must be in [0, 1], got {weight}"
                )
        return v


class PositionOut(BaseModel):
    asset_class: str
    current_weight: float
    target_weight: float
    current_value: float
    drift: float
    drift_pct: float
    needs_rebalancing: bool
    action: str
    etf_ticker: str
    etf_name: str
    etf_expense_ratio: float
    etf_ucits_alternative: str | None


class RebalancingActionOut(BaseModel):
    asset_class: str
    action: str
    amount: float
    current_weight: float
    target_weight: float
    etf_ticker: str
    rationale: str


class YearProjectionOut(BaseModel):
    year: int
    pessimistic: float
    base: float
    optimistic: float


class GrowthProjectionOut(BaseModel):
    initial_investment: float
    horizon_years: int
    pessimistic_rate: float
    base_rate: float
    optimistic_rate: float
    pessimistic_value: float
    base_value: float
    optimistic_value: float
    year_by_year: list[YearProjectionOut]


class PortfolioResponse(BaseModel):
    """Response for POST /v1/portfolio."""

    positions: list[PositionOut]
    rebalancing_actions: list[RebalancingActionOut]
    total_portfolio_value: float
    swensen_score: float
    needs_rebalancing: bool
    projection: GrowthProjectionOut
    annual_cost_estimate: float
    notes: list[str]
    disclaimer: str


# ---------------------------------------------------------------------------
# Simulate endpoint — POST /v1/simulate
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    """Request body for POST /v1/simulate.

    At minimum requires ticker and initial_investment.
    CAPM and Gordon values can be supplied from a prior /analyze call
    to produce a personalised base rate.
    """

    ticker: str = Field(..., min_length=1, max_length=20)
    initial_investment: float = Field(..., gt=0, examples=[10000.0])
    horizon_years: int = Field(default=10, ge=1, le=50)
    monthly_contribution: float = Field(default=0.0, ge=0)
    annual_volatility: float | None = Field(
        default=None, ge=0.01, le=2.0,
        description="Annualised volatility as decimal. Defaults to 18% if not provided.",
    )
    capm_required_return: float | None = Field(
        default=None, ge=0,
        description="From a prior /analyze call. Used as the base return rate.",
    )
    gordon_fair_value: float | None = Field(
        default=None, ge=0,
        description="From a prior /analyze call. Used in margin of safety calculation.",
    )
    current_price: float | None = Field(default=None, ge=0)
    risk_free_rate: float = Field(
        default=0.045, ge=0, le=0.20,
        description="Risk-free rate for Sharpe ratio (default 4.5%).",
    )

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        return v.strip().upper()


class ScenarioOut(BaseModel):
    label: str
    annual_rate: float
    final_value: float
    total_gain: float
    gain_pct: float
    cagr: float


class DCAOut(BaseModel):
    monthly_contribution: float
    total_contributed: float
    final_value_base: float
    gain_from_dca: float
    effective_cagr: float


class RiskMetricsOut(BaseModel):
    annual_volatility: float
    value_at_risk_95: float
    max_drawdown_estimate: float
    sharpe_ratio: float
    break_even_years: float
    volatility_source: str


class BreakEvenOut(BaseModel):
    break_even_year_base: int
    break_even_year_pessimistic: int
    gordon_fair_value: float | None
    current_price: float | None
    is_undervalued: bool | None
    margin_of_safety: float | None


class SimulateYearOut(BaseModel):
    year: int
    pessimistic: float
    base: float
    optimistic: float
    dca_base: float


class SimulateResponse(BaseModel):
    """Response for POST /v1/simulate."""

    ticker: str
    initial_investment: float
    horizon_years: int
    scenarios: list[ScenarioOut]
    dca: DCAOut | None
    risk: RiskMetricsOut
    break_even: BreakEvenOut
    year_by_year: list[SimulateYearOut]
    assumptions: dict[str, str]
    notes: list[str]
    disclaimer: str
