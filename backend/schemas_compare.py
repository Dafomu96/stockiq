"""
Additional Pydantic schemas for POST /v1/compare.

These extend the existing schemas.py — add them to the bottom of that file.
"""

from pydantic import BaseModel, Field, field_validator


class CompareRequest(BaseModel):
    """Request body for POST /v1/compare.

    Attributes:
        ticker_a: First ticker symbol.
        ticker_b: Second ticker symbol.
        period:   Price history period (yfinance format).
        strategy: Scoring strategy to apply to both tickers.
    """

    ticker_a: str = Field(
        ..., min_length=1, max_length=20,
        description="First ticker (e.g. 'AAPL')",
        examples=["AAPL"],
    )
    ticker_b: str = Field(
        ..., min_length=1, max_length=20,
        description="Second ticker (e.g. 'MSFT')",
        examples=["MSFT"],
    )
    period: str = Field(default="1y")
    strategy: str = Field(default="weighted_average")

    @field_validator("ticker_a", "ticker_b")
    @classmethod
    def uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("ticker_b")
    @classmethod
    def tickers_must_differ(cls, v: str, info) -> str:
        a = info.data.get("ticker_a", "")
        if v == a.strip().upper():
            raise ValueError("ticker_a and ticker_b must be different symbols")
        return v

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


class ScoreSummary(BaseModel):
    """Compact score summary for one ticker in a comparison."""

    ticker: str
    composite_score: float
    signal: str
    fundamental_score: float
    technical_score: float
    confidence: str

    # Key fundamental metrics
    capm_return: float | None
    beta: float | None
    fair_value: float | None
    current_price: float | None
    upside_pct: float | None
    pe_actual: float | None
    pe_interpretation: str | None

    # Key technical signals
    rsi_value: float | None
    rsi_signal: str
    macd_signal: str
    ma_signal: str
    golden_cross: bool
    price_above_sma200: bool

    # Notes for the UI education panel
    notes: list[str]
    data_quality_warnings: list[str]


class WinnerVerdict(BaseModel):
    """Head-to-head verdict between the two tickers."""

    winner: str | None
    """Ticker symbol of the winner, or None if tied."""

    margin: float
    """Difference in composite scores (winner - loser). 0 if tied."""

    reason: str
    """Human-readable explanation of why one ticker scored higher."""

    is_tied: bool
    """True if the score difference is < 2 points."""

    fundamental_winner: str | None
    """Ticker with higher fundamental score."""

    technical_winner: str | None
    """Ticker with higher technical score."""


class CompareResponse(BaseModel):
    """Response for POST /v1/compare.

    Contains full score summaries for both tickers plus a head-to-head verdict.
    The client receives everything needed to render a side-by-side comparison
    without making additional API calls.
    """

    ticker_a: ScoreSummary
    ticker_b: ScoreSummary
    verdict: WinnerVerdict
    analysed_at: str
    disclaimer: str = (
        "Comparison is for educational purposes only. Higher score does not "
        "guarantee better investment outcome. Both analyses are based on "
        "End-of-Day data and theoretical models. Not financial advice."
    )
