"""
Application configuration using Pydantic Settings.

All tuneable values live here. Never hardcode magic numbers in business logic.
Override any value via environment variables or a .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for StockIQ.

    Values can be overridden by environment variables (case-insensitive)
    or by a .env file in the project root.

    Example:
        STOCKIQ_DEFAULT_PERIOD=2y python -m app.streamlit_app
    """

    model_config = SettingsConfigDict(
        env_prefix="STOCKIQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Data fetching ---
    default_period: str = "1y"          # yfinance historical period
    default_interval: str = "1d"        # yfinance bar interval

    # --- Cache TTLs (seconds) ---
    cache_ttl_prices: int = 86_400      # 24 h — prices are EOD, no point refreshing intraday
    cache_ttl_fundamentals: int = 86_400  # 24 h — P/E, beta, dividends change slowly
    cache_ttl_risk_free_rate: int = 604_800  # 7 days — T-bill 10Y changes weekly at most
    cache_dir: str = ".cache"

    # --- Technical analysis thresholds (Murphy, Technical Analysis of the Financial Markets) ---
    rsi_period: int = 14                # Standard RSI window — Murphy p.225
    rsi_overbought: float = 70.0        # Classic overbought threshold — Murphy p.225
    rsi_oversold: float = 30.0          # Classic oversold threshold — Murphy p.225
    sma_short: int = 20                 # Short-term moving average
    sma_medium: int = 50                # Medium-term moving average — Murphy p.193
    sma_long: int = 200                 # Long-term trend filter — Murphy p.193
    bb_window: int = 20                 # Bollinger Bands window — Murphy p.209
    bb_std: float = 2.0                 # Bollinger Bands std deviation

    # --- Fundamental analysis defaults (Shiller) ---
    market_return: float = 0.10         # Historical S&P 500 annualised return ~ 10%
    risk_free_rate_fallback: float = 0.045  # Fallback if FRED is unreachable
    gordon_growth_max: float = 0.09     # g must be strictly below r — cap to avoid absurd values

    # --- Scoring weights ---
    weight_fundamental: float = 0.50
    weight_technical: float = 0.50

    # --- Swensen allocation (Unconventional Success, 2005) ---
    swensen_rebalance_threshold: float = 0.05  # Trigger rebalance when drift > 5 pp

    # --- API ---
    api_rate_limit: str = "10/minute"   # slowapi format


settings = Settings()
