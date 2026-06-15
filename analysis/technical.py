"""
Technical analysis engine for StockIQ.

Implements the indicators and signal logic from John J. Murphy's
"Technical Analysis of the Financial Markets" (New York Institute
of Finance, 1999).

Indicators computed:
    - RSI (Relative Strength Index)          Murphy Ch. 10, p.225
    - MACD (Moving Average Convergence/Div.) Murphy Ch. 10, p.233
    - Bollinger Bands                        Murphy Ch. 10, p.209
    - SMA 20 / 50 / 200 (simple MAs)        Murphy Ch. 9,  p.193
    - EMA 20 (exponential MA)               Murphy Ch. 9,  p.196
    - OBV (On-Balance Volume)               Murphy Ch. 7,  p.171
    - ADX (Average Directional Index)        Murphy Ch. 14, p.344

Design principles:
    - All computation is done in a single pass over the DataFrame.
    - pandas-ta handles the indicator math — we own the signal logic.
    - Functions are pure: same input → same output, no side effects.
    - Missing / NaN indicator values degrade gracefully to Signal.NEUTRAL.
    - The TechnicalScore dataclass is the only output consumed by scoring.py.

References:
    Murphy, J.J. (1999). Technical Analysis of the Financial Markets.
    New York Institute of Finance. ISBN 0-7352-0066-1.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import pandas_ta as ta  # noqa: F401  (activates the DataFrame accessor)

from config.exceptions import InsufficientDataError
from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal enum — single source of truth for all indicator verdicts
# ---------------------------------------------------------------------------

class Signal(str, Enum):
    """Directional verdict for a single indicator or the composite score.

    Inherits from str so it serialises cleanly to JSON without extra handling.
    """

    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"


# ---------------------------------------------------------------------------
# Per-indicator result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RSIResult:
    """RSI reading and derived signal.

    Attributes:
        value: Current RSI value (0–100). None if insufficient data.
        signal: BUY if oversold (< rsi_oversold), SELL if overbought
                (> rsi_overbought), NEUTRAL otherwise.
        overbought_threshold: Upper boundary used (from settings).
        oversold_threshold: Lower boundary used (from settings).

    Reference: Murphy (1999) p.225 — "readings below 30 are considered
    oversold and above 70 overbought."
    """

    value: float | None
    signal: Signal
    overbought_threshold: float
    oversold_threshold: float


@dataclass(frozen=True)
class MACDResult:
    """MACD line, signal line, histogram and derived signal.

    Attributes:
        macd: MACD line value (fast EMA − slow EMA).
        signal_line: Signal line (EMA of MACD).
        histogram: MACD − signal_line. Positive → bullish momentum.
        signal: BUY if MACD crosses above signal line (bullish crossover),
                SELL if crosses below, NEUTRAL otherwise.
        is_bullish_crossover: True when histogram is positive and turning up.
        is_bearish_crossover: True when histogram is negative and turning down.

    Reference: Murphy (1999) p.233 — "buy when the MACD line crosses
    above the signal line; sell when it crosses below."
    """

    macd: float | None
    signal_line: float | None
    histogram: float | None
    signal: Signal
    is_bullish_crossover: bool
    is_bearish_crossover: bool


@dataclass(frozen=True)
class BollingerResult:
    """Bollinger Bands reading and derived signal.

    Attributes:
        upper: Upper band value.
        middle: Middle band (SMA of window).
        lower: Lower band value.
        bandwidth: (upper − lower) / middle. Measures volatility.
        percent_b: Position of price within the bands.
                   0 = at lower band, 1 = at upper band.
        signal: BUY if price near/below lower band (percent_b < 0.2),
                SELL if near/above upper band (percent_b > 0.8),
                NEUTRAL if inside bands.

    Reference: Murphy (1999) p.209 — Bollinger Bands measure relative
    price levels. Price touching the upper band is not automatically a
    sell signal — it may indicate strong momentum in a trend.
    """

    upper: float | None
    middle: float | None
    lower: float | None
    bandwidth: float | None
    percent_b: float | None
    signal: Signal


@dataclass(frozen=True)
class MovingAverageResult:
    """Moving average values and crossover signals.

    Attributes:
        sma_20: Simple MA (20 periods).
        sma_50: Simple MA (50 periods).
        sma_200: Simple MA (200 periods).
        ema_20: Exponential MA (20 periods).
        current_price: Price at the time of analysis.
        golden_cross: True if SMA50 > SMA200 (long-term bullish trend).
        death_cross: True if SMA50 < SMA200 (long-term bearish trend).
        price_above_sma200: True if current_price > SMA200.
        signal: BUY if golden cross + price above SMA200,
                SELL if death cross + price below SMA200,
                NEUTRAL otherwise.

    Reference: Murphy (1999) p.193 — "The 200-day moving average is
    the most widely watched long-term indicator on Wall Street."
    The Golden Cross (50-day crossing above 200-day) is described on p.196.
    """

    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    ema_20: float | None
    current_price: float
    golden_cross: bool
    death_cross: bool
    price_above_sma200: bool
    signal: Signal


@dataclass(frozen=True)
class OBVResult:
    """On-Balance Volume reading and trend signal.

    Attributes:
        current_obv: Current OBV value.
        obv_sma: SMA of OBV over 20 periods (trend proxy).
        volume_trend: "rising", "falling", or "flat".
        confirms_price_trend: True if OBV direction matches price direction.
        signal: BUY if OBV is rising and confirming price rise,
                SELL if OBV is falling and confirming price fall,
                NEUTRAL otherwise.

    Reference: Murphy (1999) p.171 — "When OBV is moving in the same
    direction as the price trend, the trend is confirmed. Divergence
    between OBV and price is a warning signal."
    """

    current_obv: float | None
    obv_sma: float | None
    volume_trend: str
    confirms_price_trend: bool
    signal: Signal


@dataclass(frozen=True)
class ADXResult:
    """Average Directional Index — trend strength indicator.

    Attributes:
        adx: ADX value (0–100). > 25 indicates a strong trend.
        plus_di: +DI directional indicator.
        minus_di: −DI directional indicator.
        trend_strength: "strong" (ADX>25), "moderate" (20-25), "weak" (<20).
        signal: BUY if strong trend with +DI > −DI,
                SELL if strong trend with −DI > +DI,
                NEUTRAL if trend is weak (ADX < 20).

    Reference: Murphy (1999) p.344 — "ADX above 25 indicates that a
    trend is in force. Below 20, the market is trendless."
    """

    adx: float | None
    plus_di: float | None
    minus_di: float | None
    trend_strength: str
    signal: Signal


# ---------------------------------------------------------------------------
# Composite score output
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TechnicalScore:
    """Composite technical score and all individual indicator results.

    Attributes:
        score: Overall technical score in [0, 100]. Higher = more
               bullish from a technical standpoint.
        signal: "buy", "neutral", or "sell" from score thresholds.
        components: Dict mapping indicator name → sub-score (0–100).
        rsi: Full RSIResult.
        macd: Full MACDResult.
        bollinger: Full BollingerResult.
        moving_averages: Full MovingAverageResult.
        obv: Full OBVResult.
        adx: Full ADXResult.
        notes: Human-readable explanations for each signal, suitable for
               the educational UI tooltips.
        data_quality_warnings: List of warnings about missing/unreliable data.
    """

    score: float
    signal: str
    components: dict[str, float]
    rsi: RSIResult
    macd: MACDResult
    bollinger: BollingerResult
    moving_averages: MovingAverageResult
    obv: OBVResult
    adx: ADXResult
    notes: list[str] = field(default_factory=list)
    data_quality_warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Indicator constants (derived from settings to keep them in one place)
# ---------------------------------------------------------------------------

_RSI_OVERBOUGHT = settings.rsi_overbought   # 70.0 — Murphy p.225
_RSI_OVERSOLD = settings.rsi_oversold       # 30.0 — Murphy p.225
_RSI_PERIOD = settings.rsi_period           # 14
_SMA_SHORT = settings.sma_short             # 20
_SMA_MEDIUM = settings.sma_medium           # 50
_SMA_LONG = settings.sma_long               # 200
_BB_WINDOW = settings.bb_window             # 20
_BB_STD = settings.bb_std                   # 2.0

_SCORE_BUY_THRESHOLD = 60.0
_SCORE_SELL_THRESHOLD = 40.0

# Indicator weights in the composite score
_WEIGHTS: dict[str, float] = {
    "rsi": 0.20,
    "macd": 0.25,
    "bollinger": 0.15,
    "moving_averages": 0.25,
    "obv": 0.10,
    "adx": 0.05,
}


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def compute_technical_score(df: pd.DataFrame) -> TechnicalScore:
    """Compute all technical indicators and return a composite score.

    This is the single entry point for technical analysis. It:
        1. Validates that the DataFrame has sufficient history.
        2. Computes all indicators via pandas-ta in one pass.
        3. Derives per-indicator signals from the last row.
        4. Aggregates into a weighted composite score.
        5. Returns a fully-typed, immutable TechnicalScore.

    Args:
        df: OHLCV DataFrame from MarketDataFetcher.get_ohlcv().
            Required columns: Open, High, Low, Close, Volume.
            Index: UTC-aware DatetimeIndex, sorted ascending.
            Minimum rows: 200 (for SMA200). At least 252 recommended.

    Returns:
        TechnicalScore with score, signal, all indicator results,
        educational notes, and data quality warnings.

    Raises:
        InsufficientDataError: If fewer than 50 rows are available —
            below this threshold, even MACD is unreliable.
        ValueError: If required columns are missing from df.

    Example:
        fetcher = MarketDataFetcher()
        df = fetcher.get_ohlcv("AAPL", period="1y")
        score = compute_technical_score(df)
        print(f"Signal: {score.signal}, Score: {score.score}")
    """
    _validate_dataframe(df)

    # Compute all indicators in a single copy — never mutate the input
    df_ind = _compute_all_indicators(df.copy())

    last = df_ind.iloc[-1]
    prev = df_ind.iloc[-2] if len(df_ind) >= 2 else last
    warnings: list[str] = []

    rsi = _derive_rsi_signal(last, warnings)
    macd = _derive_macd_signal(last, prev, warnings)
    bb = _derive_bollinger_signal(last, warnings)
    ma = _derive_ma_signal(last, df_ind, warnings)
    obv = _derive_obv_signal(last, df_ind, warnings)
    adx = _derive_adx_signal(last, warnings)

    components, notes = _aggregate_components(rsi, macd, bb, ma, obv, adx)

    raw_score = sum(
        components.get(k, 50.0) * w for k, w in _WEIGHTS.items()
    )
    final_score = round(min(max(raw_score, 0.0), 100.0), 1)

    if final_score >= _SCORE_BUY_THRESHOLD:
        signal = Signal.BUY.value
    elif final_score < _SCORE_SELL_THRESHOLD:
        signal = Signal.SELL.value
    else:
        signal = Signal.NEUTRAL.value

    logger.info(
        "technical_score rows=%d score=%.1f signal=%s",
        len(df), final_score, signal,
    )

    return TechnicalScore(
        score=final_score,
        signal=signal,
        components=components,
        rsi=rsi,
        macd=macd,
        bollinger=bb,
        moving_averages=ma,
        obv=obv,
        adx=adx,
        notes=notes,
        data_quality_warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_dataframe(df: pd.DataFrame) -> None:
    """Raise descriptive errors for common bad inputs."""
    required_cols = {"Open", "High", "Low", "Close", "Volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {sorted(missing)}. "
            "Use MarketDataFetcher.get_ohlcv() to obtain correctly shaped data."
        )

    min_rows = 50  # Hard floor — below this, MACD (26+9) is meaningless
    if len(df) < min_rows:
        raise InsufficientDataError(
            indicator="Technical analysis",
            required=min_rows,
            available=len(df),
        )


# ---------------------------------------------------------------------------
# Indicator computation
# ---------------------------------------------------------------------------

def _compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Append all indicator columns to df and return it.

    Uses pandas-ta's DataFrame accessor (.ta) for all computations.
    Column names are the pandas-ta defaults, which we reference explicitly
    to be insulated from any future API changes in pandas-ta.

    If fewer than 200 bars are available, SMA200 will be NaN for early
    rows — this is expected and handled in the signal derivation step.
    """
    n = len(df)

    df.ta.rsi(length=_RSI_PERIOD, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.bbands(length=_BB_WINDOW, std=_BB_STD, append=True)
    df.ta.sma(length=_SMA_SHORT, append=True)
    df.ta.sma(length=_SMA_MEDIUM, append=True)
    df.ta.ema(length=_SMA_SHORT, append=True)
    df.ta.obv(append=True)
    df.ta.adx(length=14, append=True)

    # SMA200 only makes sense with enough history
    if n >= _SMA_LONG:
        df.ta.sma(length=_SMA_LONG, append=True)
    else:
        df[f"SMA_{_SMA_LONG}"] = float("nan")

    return df


# ---------------------------------------------------------------------------
# Signal derivation helpers
# ---------------------------------------------------------------------------

def _safe_float(val: object) -> float | None:
    """Convert pandas scalar to float, returning None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)  # type: ignore[arg-type]
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _derive_rsi_signal(last: pd.Series, warnings: list[str]) -> RSIResult:
    """Derive RSI value and signal from the most recent bar."""
    col = f"RSI_{_RSI_PERIOD}"
    value = _safe_float(last.get(col))

    if value is None:
        warnings.append(
            f"RSI({_RSI_PERIOD}) could not be computed — "
            f"need at least {_RSI_PERIOD + 1} bars."
        )
        return RSIResult(
            value=None, signal=Signal.NEUTRAL,
            overbought_threshold=_RSI_OVERBOUGHT,
            oversold_threshold=_RSI_OVERSOLD,
        )

    if value < _RSI_OVERSOLD:
        signal = Signal.BUY     # oversold — potential reversal up
    elif value > _RSI_OVERBOUGHT:
        signal = Signal.SELL    # overbought — potential reversal down
    else:
        signal = Signal.NEUTRAL

    return RSIResult(
        value=round(value, 2),
        signal=signal,
        overbought_threshold=_RSI_OVERBOUGHT,
        oversold_threshold=_RSI_OVERSOLD,
    )


def _derive_macd_signal(
    last: pd.Series,
    prev: pd.Series,
    warnings: list[str],
) -> MACDResult:
    """Derive MACD crossover signal from the last two bars.

    A bullish crossover is when the histogram turns from negative to
    positive (MACD crosses above signal line).
    A bearish crossover is the opposite.
    Murphy (1999) p.233.
    """
    macd_col = "MACD_12_26_9"
    sig_col = "MACDs_12_26_9"
    hist_col = "MACDh_12_26_9"

    macd_val = _safe_float(last.get(macd_col))
    sig_val = _safe_float(last.get(sig_col))
    hist_now = _safe_float(last.get(hist_col))
    hist_prev = _safe_float(prev.get(hist_col))

    if macd_val is None or sig_val is None:
        warnings.append(
            "MACD could not be computed — need at least 35 bars (26 slow + 9 signal)."
        )
        return MACDResult(
            macd=None, signal_line=None, histogram=None,
            signal=Signal.NEUTRAL,
            is_bullish_crossover=False, is_bearish_crossover=False,
        )

    # Crossover detection: histogram changes sign
    bullish = (
        hist_now is not None and hist_prev is not None
        and hist_now > 0 and hist_prev <= 0
    )
    bearish = (
        hist_now is not None and hist_prev is not None
        and hist_now < 0 and hist_prev >= 0
    )

    # Trend bias even without fresh crossover
    if bullish or (hist_now is not None and hist_now > 0 and macd_val > 0):
        signal = Signal.BUY
    elif bearish or (hist_now is not None and hist_now < 0 and macd_val < 0):
        signal = Signal.SELL
    else:
        signal = Signal.NEUTRAL

    return MACDResult(
        macd=round(macd_val, 4),
        signal_line=round(sig_val, 4),
        histogram=round(hist_now, 4) if hist_now is not None else None,
        signal=signal,
        is_bullish_crossover=bullish,
        is_bearish_crossover=bearish,
    )


def _derive_bollinger_signal(last: pd.Series, warnings: list[str]) -> BollingerResult:
    """Derive Bollinger Bands position and signal.

    percent_b < 0.2 → near/below lower band → BUY (potential mean reversion)
    percent_b > 0.8 → near/above upper band → SELL (potential mean reversion)
    Murphy (1999) p.209.
    """
    upper = _safe_float(last.get(f"BBU_{_BB_WINDOW}_{_BB_STD}_{_BB_STD}"))
    middle = _safe_float(last.get(f"BBM_{_BB_WINDOW}_{_BB_STD}_{_BB_STD}"))
    lower = _safe_float(last.get(f"BBL_{_BB_WINDOW}_{_BB_STD}_{_BB_STD}"))
    pct_b = _safe_float(last.get(f"BBP_{_BB_WINDOW}_{_BB_STD}_{_BB_STD}"))
    bw = _safe_float(last.get(f"BBB_{_BB_WINDOW}_{_BB_STD}_{_BB_STD}"))

    if upper is None or lower is None:
        warnings.append(
            f"Bollinger Bands({_BB_WINDOW}) could not be computed "
            f"— need at least {_BB_WINDOW} bars."
        )
        return BollingerResult(
            upper=None, middle=None, lower=None,
            bandwidth=None, percent_b=None, signal=Signal.NEUTRAL,
        )

    if pct_b is not None and pct_b < 0.2:
        signal = Signal.BUY
    elif pct_b is not None and pct_b > 0.8:
        signal = Signal.SELL
    else:
        signal = Signal.NEUTRAL

    return BollingerResult(
        upper=round(upper, 4),
        middle=round(middle, 4) if middle is not None else None,
        lower=round(lower, 4),
        bandwidth=round(bw, 4) if bw is not None else None,
        percent_b=round(pct_b, 4) if pct_b is not None else None,
        signal=signal,
    )


def _derive_ma_signal(
    last: pd.Series,
    df: pd.DataFrame,
    warnings: list[str],
) -> MovingAverageResult:
    """Derive moving average crossover signals.

    Golden Cross: SMA50 crosses above SMA200 → long-term bullish.
    Death Cross:  SMA50 crosses below SMA200 → long-term bearish.
    Murphy (1999) p.196.
    """
    price = _safe_float(last.get("Close"))
    sma20 = _safe_float(last.get(f"SMA_{_SMA_SHORT}"))
    sma50 = _safe_float(last.get(f"SMA_{_SMA_MEDIUM}"))
    sma200 = _safe_float(last.get(f"SMA_{_SMA_LONG}"))
    ema20 = _safe_float(last.get(f"EMA_{_SMA_SHORT}"))

    if sma200 is None:
        warnings.append(
            f"SMA200 not available — need at least {_SMA_LONG} bars for the "
            "long-term trend filter. Using SMA50 as fallback."
        )

    golden_cross = (
        sma50 is not None and sma200 is not None and sma50 > sma200
    )
    death_cross = (
        sma50 is not None and sma200 is not None and sma50 < sma200
    )
    above_200 = (
        price is not None and sma200 is not None and price > sma200
    )

    # Signal logic: trend + position relative to long-term MA
    if golden_cross and above_200:
        signal = Signal.BUY
    elif death_cross and not above_200:
        signal = Signal.SELL
    elif sma50 is not None and price is not None and price > sma50:
        # Price above medium-term MA — mildly bullish
        signal = Signal.BUY
    elif sma50 is not None and price is not None and price < sma50:
        signal = Signal.SELL
    else:
        signal = Signal.NEUTRAL

    return MovingAverageResult(
        sma_20=round(sma20, 4) if sma20 is not None else None,
        sma_50=round(sma50, 4) if sma50 is not None else None,
        sma_200=round(sma200, 4) if sma200 is not None else None,
        ema_20=round(ema20, 4) if ema20 is not None else None,
        current_price=round(price, 4) if price is not None else 0.0,
        golden_cross=golden_cross,
        death_cross=death_cross,
        price_above_sma200=above_200,
        signal=signal,
    )


def _derive_obv_signal(
    last: pd.Series,
    df: pd.DataFrame,
    warnings: list[str],
) -> OBVResult:
    """Derive OBV trend and volume confirmation signal.

    OBV rising while price rises = volume confirms the trend.
    OBV diverging from price = warning signal.
    Murphy (1999) p.171.
    """
    obv_series = df["OBV"].dropna() if "OBV" in df.columns else pd.Series(dtype=float)

    if len(obv_series) < 5:
        warnings.append("OBV could not be computed — insufficient volume data.")
        return OBVResult(
            current_obv=None, obv_sma=None, volume_trend="unknown",
            confirms_price_trend=False, signal=Signal.NEUTRAL,
        )

    current_obv = _safe_float(obv_series.iloc[-1])
    obv_sma = float(obv_series.tail(20).mean()) if len(obv_series) >= 20 else None

    # OBV trend: compare last 5 values
    recent_obv = obv_series.tail(5)
    obv_slope = float(recent_obv.iloc[-1] - recent_obv.iloc[0])
    if obv_slope > 0:
        volume_trend = "rising"
    elif obv_slope < 0:
        volume_trend = "falling"
    else:
        volume_trend = "flat"

    # Price trend over same 5 bars
    price_series = df["Close"].dropna().tail(5)
    price_slope = (
        float(price_series.iloc[-1] - price_series.iloc[0])
        if len(price_series) >= 2 else 0.0
    )

    confirms = (
        (obv_slope > 0 and price_slope > 0)
        or (obv_slope < 0 and price_slope < 0)
    )

    if volume_trend == "rising" and price_slope > 0:
        signal = Signal.BUY
    elif volume_trend == "falling" and price_slope < 0:
        signal = Signal.SELL
    else:
        signal = Signal.NEUTRAL

    return OBVResult(
        current_obv=round(current_obv, 0) if current_obv is not None else None,
        obv_sma=round(obv_sma, 0) if obv_sma is not None else None,
        volume_trend=volume_trend,
        confirms_price_trend=confirms,
        signal=signal,
    )


def _derive_adx_signal(last: pd.Series, warnings: list[str]) -> ADXResult:
    """Derive ADX trend strength and directional signal.

    ADX > 25 = strong trend in force.
    +DI > -DI in a strong trend = bullish direction.
    Murphy (1999) p.344.
    """
    adx = _safe_float(last.get("ADX_14"))
    plus_di = _safe_float(last.get("DMP_14"))
    minus_di = _safe_float(last.get("DMN_14"))

    if adx is None:
        warnings.append("ADX could not be computed — need at least 14 bars.")
        return ADXResult(
            adx=None, plus_di=None, minus_di=None,
            trend_strength="unknown", signal=Signal.NEUTRAL,
        )

    if adx >= 25:
        trend_strength = "strong"
    elif adx >= 20:
        trend_strength = "moderate"
    else:
        trend_strength = "weak"

    if trend_strength == "strong" and plus_di is not None and minus_di is not None:
        signal = Signal.BUY if plus_di > minus_di else Signal.SELL
    else:
        signal = Signal.NEUTRAL  # no clear trend → don't trade ADX signal

    return ADXResult(
        adx=round(adx, 2),
        plus_di=round(plus_di, 2) if plus_di is not None else None,
        minus_di=round(minus_di, 2) if minus_di is not None else None,
        trend_strength=trend_strength,
        signal=signal,
    )


# ---------------------------------------------------------------------------
# Score aggregation
# ---------------------------------------------------------------------------

def _signal_to_score(signal: Signal) -> float:
    """Convert a Signal enum to a numeric sub-score."""
    return {Signal.BUY: 80.0, Signal.NEUTRAL: 50.0, Signal.SELL: 20.0}[signal]


def _aggregate_components(
    rsi: RSIResult,
    macd: MACDResult,
    bb: BollingerResult,
    ma: MovingAverageResult,
    obv: OBVResult,
    adx: ADXResult,
) -> tuple[dict[str, float], list[str]]:
    """Convert indicator signals to numeric scores and build notes.

    Returns:
        components: Dict of indicator → score (0–100).
        notes: Human-readable explanations for each indicator, suitable
               for the educational UI panel ("What does this mean?").
    """
    components: dict[str, float] = {
        "rsi": _signal_to_score(rsi.signal),
        "macd": _signal_to_score(macd.signal),
        "bollinger": _signal_to_score(bb.signal),
        "moving_averages": _signal_to_score(ma.signal),
        "obv": _signal_to_score(obv.signal),
        "adx": _signal_to_score(adx.signal),
    }

    notes: list[str] = []

    # RSI note
    if rsi.value is not None:
        zone = (
            "oversold — potential reversal upward" if rsi.signal == Signal.BUY
            else "overbought — potential reversal downward" if rsi.signal == Signal.SELL
            else "neutral zone"
        )
        notes.append(
            f"RSI({_RSI_PERIOD}): {rsi.value:.1f} — {zone}. "
            f"Thresholds: oversold <{_RSI_OVERSOLD}, overbought >{_RSI_OVERBOUGHT}. "
            "(Murphy, Technical Analysis, p.225)"
        )

    # MACD note
    if macd.macd is not None:
        crossover = ""
        if macd.is_bullish_crossover:
            crossover = "Bullish crossover detected (MACD crossed above signal line). "
        elif macd.is_bearish_crossover:
            crossover = "Bearish crossover detected (MACD crossed below signal line). "
        notes.append(
            f"MACD: {macd.macd:.4f} | Signal: {macd.signal_line:.4f} | "
            f"Histogram: {macd.histogram:.4f}. {crossover}"
            "(Murphy, Technical Analysis, p.233)"
        )

    # Bollinger note
    if bb.percent_b is not None:
        position = (
            "near lower band — potential buy zone" if bb.signal == Signal.BUY
            else "near upper band — potential sell zone" if bb.signal == Signal.SELL
            else "inside bands — no extreme signal"
        )
        notes.append(
            f"Bollinger Bands: %B={bb.percent_b:.2f} ({position}). "
            f"Bandwidth={bb.bandwidth:.4f}. "
            "(Murphy, Technical Analysis, p.209)"
        )

    # Moving averages note
    cross = ""
    if ma.golden_cross:
        cross = "Golden Cross active (SMA50 > SMA200) — long-term bullish. "
    elif ma.death_cross:
        cross = "Death Cross active (SMA50 < SMA200) — long-term bearish. "
    price_rel = "above" if ma.price_above_sma200 else "below"
    notes.append(
        f"Moving averages: SMA50={ma.sma_50}, SMA200={ma.sma_200}. "
        f"{cross}Price is {price_rel} SMA200. "
        "(Murphy, Technical Analysis, p.193)"
    )

    # OBV note
    notes.append(
        f"OBV trend: {obv.volume_trend}. "
        f"Volume {'confirms' if obv.confirms_price_trend else 'diverges from'} price trend. "
        "(Murphy, Technical Analysis, p.171)"
    )

    # ADX note
    if adx.adx is not None:
        notes.append(
            f"ADX: {adx.adx:.1f} — trend strength: {adx.trend_strength}. "
            f"+DI={adx.plus_di}, -DI={adx.minus_di}. "
            "ADX > 25 indicates a trend is in force. "
            "(Murphy, Technical Analysis, p.344)"
        )

    return components, notes
