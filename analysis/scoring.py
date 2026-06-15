"""
Composite scoring engine for StockIQ.

Combines the fundamental score (Shiller) and the technical score (Murphy)
into a single actionable verdict for a ticker.

Design: Strategy Pattern
    The abstract base class ScoringStrategy defines the interface.
    WeightedAverageStrategy is the default implementation.
    Adding a new strategy (e.g. a momentum-only or value-only mode)
    requires only a new subclass — zero changes to callers.

    See: ADR-003 — Why Strategy Pattern for scoring.

The CompositeResult dataclass is the single object consumed by:
    - The Streamlit UI (pages/overview.py)
    - The FastAPI endpoint (routers/analyze.py)
    - The Swensen portfolio module (analysis/swensen.py)

References:
    - Shiller, R.J. (2000). Irrational Exuberance. Princeton University Press.
    - Murphy, J.J. (1999). Technical Analysis of the Financial Markets.
      New York Institute of Finance.
    - Gamma, E. et al. (1994). Design Patterns. Addison-Wesley. (Strategy, p.315)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from analysis.fundamentals import FundamentalScore
from analysis.technical import TechnicalScore
from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompositeResult:
    """The final, unified analysis result for a single ticker.

    This is the primary output of the scoring engine and the contract
    between the analysis layer and the UI/API layers. Adding fields here
    is a breaking change — update all consumers.

    Attributes:
        ticker: The analysed symbol (uppercase, e.g. "AAPL", "ASML.AS").
        composite_score: Weighted aggregate of fundamental + technical
            scores. Range [0, 100]. Higher = more attractive.
        signal: Final directional verdict: "buy", "neutral", or "sell".
            Derived from composite_score using configurable thresholds.
        fundamental: Full FundamentalScore from analysis/fundamentals.py.
        technical: Full TechnicalScore from analysis/technical.py.
        strategy_name: Human-readable name of the strategy used.
            Included so the UI can surface which scoring approach was applied.
        weights: Dict mapping score source → weight applied.
            e.g. {"fundamental": 0.5, "technical": 0.5}
        score_breakdown: Dict for the UI score gauge.
            Keys: "fundamental", "technical", "composite".
        confidence: Qualitative confidence level: "high", "medium", "low".
            Degrades when data is missing or assumptions are borderline.
        confidence_reasons: List of reasons the confidence was reduced.
        summary_notes: Merged notes from both analysis modules.
            Suitable for the "What does this mean?" UI panel.
        analysed_at: UTC timestamp of when the analysis was run.
            The UI must display this so users know data freshness.
        disclaimer: Regulatory-style disclaimer in the active language.
            Always included — never optional.
    """

    ticker: str
    composite_score: float
    signal: str
    fundamental: FundamentalScore
    technical: TechnicalScore
    strategy_name: str
    weights: dict[str, float]
    score_breakdown: dict[str, float]
    confidence: str
    confidence_reasons: list[str]
    summary_notes: list[str]
    analysed_at: str
    disclaimer: str = field(default=(
        "This analysis is for educational purposes only and does not constitute "
        "financial advice. All models are theoretical and based on historical data. "
        "Past performance does not guarantee future results. "
        "Data is End-of-Day (EOD) — not suitable for intraday trading decisions."
    ))


# ---------------------------------------------------------------------------
# Abstract strategy
# ---------------------------------------------------------------------------

class ScoringStrategy(ABC):
    """Abstract base class for composite scoring strategies.

    Subclasses implement a single method: combine().
    The engine (run_scoring) always works with this interface,
    never with a concrete implementation directly.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name for UI display."""

    @property
    @abstractmethod
    def weights(self) -> dict[str, float]:
        """Weights applied to each score source. Must sum to 1.0."""

    @abstractmethod
    def combine(
        self,
        ticker: str,
        fundamental: FundamentalScore,
        technical: TechnicalScore,
    ) -> CompositeResult:
        """Combine the two analysis results into a single CompositeResult.

        Args:
            ticker: The ticker symbol being scored.
            fundamental: Output of compute_fundamental_score().
            technical: Output of compute_technical_score().

        Returns:
            CompositeResult with composite_score, signal, and all metadata.
        """


# ---------------------------------------------------------------------------
# Default strategy: weighted average
# ---------------------------------------------------------------------------

class WeightedAverageStrategy(ScoringStrategy):
    """Default strategy: weighted average of fundamental and technical scores.

    Weights are read from settings (STOCKIQ_WEIGHT_FUNDAMENTAL /
    STOCKIQ_WEIGHT_TECHNICAL) and validated to sum to 1.0 at init time.

    Score thresholds:
        composite >= 60 → "buy"
        composite < 40  → "sell"
        otherwise       → "neutral"

    These are intentionally conservative — a score of 60 does NOT mean
    "definitely buy". It means the combined evidence leans positive.
    The disclaimer makes this explicit in the UI.

    Confidence degradation rules:
        - "high"   → both scores available, no warnings, no model errors
        - "medium" → one data quality warning OR one model assumption skipped
        - "low"    → multiple warnings OR fundamental score is missing key data
    """

    _BUY_THRESHOLD = 60.0
    _SELL_THRESHOLD = 40.0

    def __init__(
        self,
        weight_fundamental: float | None = None,
        weight_technical: float | None = None,
    ) -> None:
        w_f = weight_fundamental if weight_fundamental is not None else settings.weight_fundamental
        w_t = weight_technical if weight_technical is not None else settings.weight_technical

        if not (0 < w_f <= 1 and 0 < w_t <= 1):
            raise ValueError(
                f"Weights must be in (0, 1]. Got fundamental={w_f}, technical={w_t}"
            )
        total = w_f + w_t
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0. Got {w_f} + {w_t} = {total:.3f}"
            )

        self._w_f = w_f
        self._w_t = w_t

    @property
    def name(self) -> str:
        return (
            f"Weighted average "
            f"(fundamental {self._w_f:.0%} / technical {self._w_t:.0%})"
        )

    @property
    def weights(self) -> dict[str, float]:
        return {"fundamental": self._w_f, "technical": self._w_t}

    def combine(
        self,
        ticker: str,
        fundamental: FundamentalScore,
        technical: TechnicalScore,
    ) -> CompositeResult:
        composite = round(
            fundamental.score * self._w_f + technical.score * self._w_t,
            1,
        )

        if composite >= self._BUY_THRESHOLD:
            signal = "buy"
        elif composite < self._SELL_THRESHOLD:
            signal = "sell"
        else:
            signal = "neutral"

        confidence, confidence_reasons = self._assess_confidence(
            fundamental, technical
        )

        summary_notes = _merge_notes(fundamental, technical)

        logger.info(
            "composite_score ticker=%s fundamental=%.1f technical=%.1f "
            "composite=%.1f signal=%s confidence=%s",
            ticker,
            fundamental.score, technical.score,
            composite, signal, confidence,
        )

        return CompositeResult(
            ticker=ticker.upper(),
            composite_score=composite,
            signal=signal,
            fundamental=fundamental,
            technical=technical,
            strategy_name=self.name,
            weights=self.weights,
            score_breakdown={
                "fundamental": fundamental.score,
                "technical": technical.score,
                "composite": composite,
            },
            confidence=confidence,
            confidence_reasons=confidence_reasons,
            summary_notes=summary_notes,
            analysed_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _assess_confidence(
        fundamental: FundamentalScore,
        technical: TechnicalScore,
    ) -> tuple[str, list[str]]:
        """Determine confidence level and list reasons for any degradation.

        Returns:
            Tuple of (confidence_level, reasons_list).
        """
        reasons: list[str] = []

        # Fundamental confidence hits
        gordon_skipped = fundamental.gordon is None
        if gordon_skipped:
            reasons.append(
                "Gordon Growth Model not applicable (no dividend). "
                "Fundamental score relies only on CAPM and P/E."
            )

        pe_unavailable = fundamental.pe.actual_pe is None
        if pe_unavailable:
            reasons.append(
                "P/E ratio not available (negative earnings or missing data). "
                "Fundamental score is less reliable."
            )

        # Technical confidence hits
        warnings_count = len(technical.data_quality_warnings)
        if warnings_count > 0:
            reasons.extend(technical.data_quality_warnings)

        # Confidence level
        if not reasons:
            confidence = "high"
        elif len(reasons) == 1:
            confidence = "medium"
        else:
            confidence = "low"

        return confidence, reasons


# ---------------------------------------------------------------------------
# Fundamental-only strategy (for assets without reliable technical data)
# ---------------------------------------------------------------------------

class FundamentalOnlyStrategy(ScoringStrategy):
    """Scoring strategy that uses only fundamental analysis.

    Useful when:
    - The asset has very few price history bars (< 50)
    - The user explicitly wants a value-investing perspective only

    The technical score is still computed and attached to the result
    for informational purposes, but does not affect the composite score.
    """

    _BUY_THRESHOLD = 60.0
    _SELL_THRESHOLD = 40.0

    @property
    def name(self) -> str:
        return "Fundamental only (Shiller framework)"

    @property
    def weights(self) -> dict[str, float]:
        return {"fundamental": 1.0, "technical": 0.0}

    def combine(
        self,
        ticker: str,
        fundamental: FundamentalScore,
        technical: TechnicalScore,
    ) -> CompositeResult:
        composite = round(fundamental.score, 1)

        signal = (
            "buy" if composite >= self._BUY_THRESHOLD
            else "sell" if composite < self._SELL_THRESHOLD
            else "neutral"
        )

        reasons = ["Technical analysis excluded — fundamental-only mode."]
        confidence = "medium"  # always medium without technical confirmation

        logger.info(
            "composite_score strategy=fundamental_only ticker=%s "
            "score=%.1f signal=%s",
            ticker, composite, signal,
        )

        return CompositeResult(
            ticker=ticker.upper(),
            composite_score=composite,
            signal=signal,
            fundamental=fundamental,
            technical=technical,
            strategy_name=self.name,
            weights=self.weights,
            score_breakdown={
                "fundamental": fundamental.score,
                "technical": technical.score,
                "composite": composite,
            },
            confidence=confidence,
            confidence_reasons=reasons,
            summary_notes=_merge_notes(fundamental, technical),
            analysed_at=datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Engine — the single public entry point
# ---------------------------------------------------------------------------

def run_scoring(
    ticker: str,
    fundamental: FundamentalScore,
    technical: TechnicalScore,
    strategy: ScoringStrategy | None = None,
) -> CompositeResult:
    """Run the composite scoring engine for a ticker.

    This is the primary entry point consumed by all UI and API layers.
    It never imports yfinance or makes network calls — it receives
    pre-computed analysis objects and combines them.

    Args:
        ticker: Ticker symbol (e.g. "AAPL", "ASML.AS"). Case-insensitive.
        fundamental: Output of analysis.fundamentals.compute_fundamental_score().
        technical: Output of analysis.technical.compute_technical_score().
        strategy: Scoring strategy to apply. Defaults to
            WeightedAverageStrategy with weights from settings.

    Returns:
        CompositeResult — the unified result for the UI and API.

    Example:
        fetcher = MarketDataFetcher()
        df = fetcher.get_ohlcv("AAPL")
        info = fetcher.get_fundamental_info("AAPL")
        rf = fetcher.get_risk_free_rate()

        fundamental = compute_fundamental_score(
            current_price=info["regularMarketPrice"],
            beta=info["beta"],
            trailing_pe=info["trailingPE"],
            forward_pe=info["forwardPE"],
            dividend_rate=info["dividendRate"],
            dividend_yield=info["dividendYield"],
            earnings_growth=info["earningsGrowth"],
            risk_free_rate=rf,
        )
        technical = compute_technical_score(df)
        result = run_scoring("AAPL", fundamental, technical)
        print(result.signal, result.composite_score)
    """
    effective_strategy = strategy or WeightedAverageStrategy()
    return effective_strategy.combine(ticker, fundamental, technical)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _merge_notes(
    fundamental: FundamentalScore,
    technical: TechnicalScore,
) -> list[str]:
    """Merge and deduplicate notes from both analysis modules.

    Fundamental notes come first (valuation context), then technical
    (timing context). This mirrors how Murphy recommends analysts work:
    fundamentals decide WHAT to buy, technicals decide WHEN.

    Args:
        fundamental: FundamentalScore with its notes list.
        technical: TechnicalScore with its notes list.

    Returns:
        Combined list with section headers for the UI panel.
    """
    merged: list[str] = []

    if fundamental.notes:
        merged.append("── Fundamental analysis (Shiller) ──")
        merged.extend(fundamental.notes)

    if technical.notes:
        merged.append("── Technical analysis (Murphy) ──")
        merged.extend(technical.notes)

    return merged
