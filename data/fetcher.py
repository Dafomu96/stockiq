"""
Market data fetcher for StockIQ.

Responsibilities:
- Download OHLCV price history and fundamental info from yfinance.
- Fetch the risk-free rate (US 10Y T-bill) from the FRED API.
- Cache every response to avoid redundant network calls.
- Degrade gracefully: if the primary source fails, try secondary;
  if both fail, return stale cache with a warning rather than crashing.

Data sources:
- Primary prices & fundamentals: yfinance (Yahoo Finance, unofficial API)
- Risk-free rate: FRED series DGS10 (Federal Reserve, official)
- Secondary / fallback: settings.risk_free_rate_fallback

Limitations (must be communicated in the UI):
- All price data is End-of-Day (EOD). Not suitable for intraday trading.
- yfinance is an unofficial wrapper; Yahoo may change the API without notice.
- Fundamental data (P/E, beta) may lag the official filings by days.

See: ADR-001 — Why yfinance over Polygon.io for the MVP.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
import yfinance as yf

from config.exceptions import DataFetchError, InvalidTickerError, RateLimitError
from config.settings import settings
from data.cache import CacheBackend, get_cache

logger = logging.getLogger(__name__)

# FRED series for the US 10-Year Treasury constant maturity rate.
# Source: https://fred.stlouisfed.org/series/DGS10
_FRED_SERIES = "DGS10"
_FRED_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    f"?id={_FRED_SERIES}&vintage_date="
)


class MarketDataFetcher:
    """Fetches, caches, and validates market data for a given ticker.

    All public methods return clean, validated data or raise a typed
    exception from config.exceptions — never a bare Exception.

    Args:
        cache: Cache backend instance. Defaults to the configured backend
               (JsonFileCache in MVP, Redis in production).

    Example:
        fetcher = MarketDataFetcher()
        prices = fetcher.get_ohlcv("AAPL")
        info   = fetcher.get_fundamental_info("AAPL")
        rf     = fetcher.get_risk_free_rate()
    """

    def __init__(self, cache: CacheBackend | None = None) -> None:
        self._cache = cache or get_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ohlcv(
        self,
        ticker: str,
        period: str | None = None,
        interval: str | None = None,
    ) -> pd.DataFrame:
        """Return OHLCV price history for *ticker*.

        The DataFrame has a DatetimeIndex and columns:
        Open, High, Low, Close, Volume (all float64).

        Args:
            ticker: Yahoo Finance ticker symbol. Append exchange suffix
                    for non-US stocks (e.g. "ASML.AS", "SAN.MC", "7203.T").
            period: yfinance period string ("1y", "2y", "5y", "max", …).
                    Defaults to settings.default_period.
            interval: Bar interval ("1d", "1wk", "1mo").
                      Defaults to settings.default_interval.

        Returns:
            DataFrame with columns [Open, High, Low, Close, Volume].
            Index is timezone-aware UTC DatetimeIndex, sorted ascending.

        Raises:
            InvalidTickerError: If yfinance returns an empty result.
            DataFetchError: For any other download failure.

        Note:
            Data is End-of-Day. The most recent bar is the last *completed*
            trading day — not intraday data.
        """
        period = period or settings.default_period
        interval = interval or settings.default_interval
        cache_key = f"ohlcv:{ticker}:{period}:{interval}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(
                "ohlcv_cache_hit ticker=%s period=%s", ticker, period
            )
            import io
            return pd.read_json(io.StringIO(cached), orient="split")

        logger.info(
            "ohlcv_fetch ticker=%s period=%s interval=%s source=yfinance",
            ticker, period, interval,
        )

        try:
            raw: pd.DataFrame = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception as exc:
            raise DataFetchError(ticker, f"yfinance download raised: {exc}") from exc

        if raw.empty:
            raise InvalidTickerError(ticker)

        df = self._clean_ohlcv(raw, ticker)

        self._cache.set(cache_key, df.to_json(orient="split"), settings.cache_ttl_prices)
        logger.info(
            "ohlcv_fetched ticker=%s rows=%d first=%s last=%s",
            ticker, len(df),
            df.index[0].date() if not df.empty else "N/A",
            df.index[-1].date() if not df.empty else "N/A",
        )
        return df

    def get_fundamental_info(self, ticker: str) -> dict[str, Any]:
        """Return fundamental data for *ticker* from yfinance .info.

        Keys relevant to StockIQ (all others are filtered out to keep
        the contract stable regardless of yfinance version):

            trailingPE, forwardPE, beta, dividendRate,
            dividendYield, marketCap, sector, industry,
            shortName, longName, currency, exchange,
            fiftyTwoWeekHigh, fiftyTwoWeekLow,
            earningsGrowth, revenueGrowth.

        Args:
            ticker: Yahoo Finance ticker symbol.

        Returns:
            Dict with the keys listed above. Missing keys have value None.

        Raises:
            InvalidTickerError: If yfinance returns no info dict.
            DataFetchError: For any other failure.
        """
        cache_key = f"info:{ticker}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("info_cache_hit ticker=%s", ticker)
            return cached  # type: ignore[return-value]

        logger.info("info_fetch ticker=%s source=yfinance", ticker)
        try:
            raw_info: dict[str, Any] = yf.Ticker(ticker).info
        except Exception as exc:
            raise DataFetchError(ticker, f"yfinance .info raised: {exc}") from exc

        if not raw_info or raw_info.get("regularMarketPrice") is None:
            raise InvalidTickerError(ticker)

        info = self._extract_fundamental_fields(raw_info)
        self._cache.set(cache_key, info, settings.cache_ttl_fundamentals)
        logger.info("info_fetched ticker=%s sector=%s", ticker, info.get("sector"))
        return info

    def get_risk_free_rate(self) -> float:
        """Return the current US 10-Year Treasury yield as a decimal.

        Source: FRED series DGS10 (Federal Reserve Bank of St. Louis).
        The yield is returned as a decimal (e.g. 4.5% → 0.045).

        Falls back to settings.risk_free_rate_fallback if FRED is
        unreachable, and logs a warning so the UI can surface it.

        Returns:
            Risk-free rate as a float in [0, 1].

        Note:
            Cached for settings.cache_ttl_risk_free_rate (default 7 days).
            The T-bill rate changes at most weekly in normal conditions.
        """
        cache_key = "macro:risk_free_rate"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("risk_free_rate_cache_hit value=%.4f", cached)
            return float(cached)

        logger.info("risk_free_rate_fetch source=FRED series=%s", _FRED_SERIES)
        rate = self._fetch_fred_rate()
        self._cache.set(cache_key, rate, settings.cache_ttl_risk_free_rate)
        logger.info("risk_free_rate_fetched value=%.4f", rate)
        return rate

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_fred_rate(self) -> float:
        """Download DGS10 from FRED and return as decimal.

        If the request fails for any reason, logs a warning and returns
        settings.risk_free_rate_fallback rather than crashing — the
        CAPM result will still be meaningful with a reasonable fallback.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url = _FRED_URL + today
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 429:
                raise RateLimitError("FRED API rate limit exceeded")
            resp.raise_for_status()

            lines = resp.text.strip().splitlines()
            # CSV format: DATE,VALUE — last row is most recent
            for line in reversed(lines[1:]):
                parts = line.split(",")
                if len(parts) == 2 and parts[1].strip() not in (".", ""):
                    rate_pct = float(parts[1].strip())
                    return round(rate_pct / 100, 6)

            raise DataFetchError("DGS10", "No valid data rows in FRED response")

        except (requests.RequestException, ValueError, DataFetchError) as exc:
            logger.warning(
                "risk_free_rate_fetch_failed error=%s "
                "fallback=%.4f",
                exc, settings.risk_free_rate_fallback,
            )
            return settings.risk_free_rate_fallback

    @staticmethod
    def _clean_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Normalise a raw yfinance DataFrame.

        - Drops rows where Close is NaN (non-trading days).
        - Flattens MultiIndex columns (yfinance >= 0.2 returns them for
          single-ticker downloads when auto_adjust=True).
        - Ensures UTC-aware DatetimeIndex sorted ascending.
        - Casts all price columns to float64.

        Args:
            df: Raw DataFrame from yf.download().
            ticker: Used only for log context.

        Returns:
            Clean DataFrame with columns [Open, High, Low, Close, Volume].
        """
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        keep = ["Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in keep if c in df.columns]].copy()
        df.dropna(subset=["Close"], inplace=True)

        if df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        df.sort_index(inplace=True)
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = df[col].astype("float64")

        logger.debug(
            "ohlcv_cleaned ticker=%s rows_after_clean=%d", ticker, len(df)
        )
        return df

    @staticmethod
    def _extract_fundamental_fields(raw: dict[str, Any]) -> dict[str, Any]:
        """Extract and normalise the subset of yfinance .info we rely on.

        Keeping a fixed contract means a yfinance upgrade that renames
        fields only breaks this method, not every caller.

        Args:
            raw: Full dict from yf.Ticker(ticker).info.

        Returns:
            Dict with a stable set of keys; missing values are None.
        """
        fields = [
            "trailingPE", "forwardPE", "beta",
            "dividendRate", "dividendYield",
            "marketCap", "sector", "industry",
            "shortName", "longName", "currency", "exchange",
            "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
            "earningsGrowth", "revenueGrowth",
            "regularMarketPrice", "regularMarketPreviousClose",
        ]
        return {field: raw.get(field) for field in fields}
