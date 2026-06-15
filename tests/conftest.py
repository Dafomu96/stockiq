"""
Pytest configuration and shared fixtures for StockIQ.

Key design goals:
    1. ALL tests run 100% offline — no yfinance, no FRED, no network.
    2. Fixtures are reusable across test modules via pytest's dependency
       injection — no copy-pasted setup code.
    3. Sample JSON responses in tests/fixtures/sample_responses/ act as
       both test data and living documentation of the API contract.

Fixture hierarchy:
    sample_dir          — path to fixtures/sample_responses/
    analyze_aapl_json   — raw dict of a full /v1/analyze response (AAPL)
    portfolio_json      — raw dict of a /v1/portfolio response (drifted)
    simulate_json       — raw dict of a /v1/simulate response (AAPL + DCA)
    mock_ohlcv_df       — synthetic 252-bar OHLCV DataFrame (1 trading year)
    mock_fundamental_info — minimal yfinance .info dict for AAPL
    mock_risk_free_rate — float fallback rate (no FRED call)
    mock_fetcher        — MagicMock wired to the three fixtures above

Usage in any test file:
    def test_something(mock_fetcher, analyze_aapl_json):
        # mock_fetcher is already configured — no patch needed
        ...
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_responses"


# ---------------------------------------------------------------------------
# JSON sample response fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_dir() -> Path:
    """Return the path to fixtures/sample_responses/."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def analyze_aapl_json() -> dict:
    """Full /v1/analyze response for AAPL.

    Loaded once per session — safe because it is read-only.
    Source: tests/fixtures/sample_responses/analyze_AAPL.json

    Use this fixture when you need realistic analysis output
    without running the full pipeline.
    """
    return json.loads((FIXTURES_DIR / "analyze_AAPL.json").read_text())


@pytest.fixture(scope="session")
def portfolio_json() -> dict:
    """Full /v1/portfolio response for a drifted portfolio.

    Domestic equity overweight (+10pp), real estate underweight (-10pp).
    Source: tests/fixtures/sample_responses/portfolio_drifted.json
    """
    return json.loads((FIXTURES_DIR / "portfolio_drifted.json").read_text())


@pytest.fixture(scope="session")
def simulate_json() -> dict:
    """Full /v1/simulate response for AAPL with DCA.

    10-year horizon, €200/month DCA, CAPM base rate.
    Source: tests/fixtures/sample_responses/simulate_AAPL.json
    """
    return json.loads((FIXTURES_DIR / "simulate_AAPL.json").read_text())


# ---------------------------------------------------------------------------
# DataFrame fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mock_ohlcv_df() -> pd.DataFrame:
    """Synthetic 252-bar OHLCV DataFrame representing one trading year.

    Uses a steady uptrend so that:
    - SMA50 > SMA200 (Golden Cross) is guaranteed
    - RSI lands in neutral zone (~55)
    - MACD histogram is positive
    - OBV rises with price

    All technical indicator tests that need "a realistic looking DataFrame"
    should use this fixture rather than building their own.
    """
    rows = 252
    idx = pd.date_range("2024-01-02", periods=rows, freq="B", tz="UTC")
    closes = [150.0 + i * 0.2 for i in range(rows)]
    return pd.DataFrame(
        {
            "Open":   [c - 0.5 for c in closes],
            "High":   [c + 1.0 for c in closes],
            "Low":    [c - 1.0 for c in closes],
            "Close":  closes,
            "Volume": [50_000_000] * rows,
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# yfinance info fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mock_fundamental_info() -> dict:
    """Minimal yfinance .info dict for AAPL.

    Contains only the fields that MarketDataFetcher._extract_fundamental_fields
    extracts. Missing fields are None — identical to what yfinance returns for
    fields it doesn't have.

    Beta and P/E values are realistic for a large-cap tech stock.
    """
    return {
        "regularMarketPrice": 182.40,
        "regularMarketPreviousClose": 180.12,
        "trailingPE": 28.5,
        "forwardPE": 25.0,
        "beta": 1.24,
        "dividendRate": 0.96,
        "dividendYield": 0.0053,
        "marketCap": 2_800_000_000_000,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "shortName": "Apple Inc.",
        "longName": "Apple Inc.",
        "currency": "USD",
        "exchange": "NMS",
        "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 124.17,
        "earningsGrowth": 0.08,
        "revenueGrowth": 0.05,
    }


@pytest.fixture(scope="session")
def mock_risk_free_rate() -> float:
    """Risk-free rate to use in tests — 4.5% (US 10Y T-bill, mid-2024 range)."""
    return 0.045


# ---------------------------------------------------------------------------
# Mock fetcher fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_fetcher(mock_ohlcv_df, mock_fundamental_info, mock_risk_free_rate):
    """MagicMock wired to the three data fixtures.

    Returns a pre-configured mock of MarketDataFetcher:
        .get_ohlcv()          → mock_ohlcv_df
        .get_fundamental_info() → mock_fundamental_info
        .get_risk_free_rate() → mock_risk_free_rate

    Use this in API integration tests via dependency_overrides:

        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

    Or directly in unit tests that call analysis functions.

    Note: function scope (not session) because tests may reconfigure
    the mock's return values or side_effects independently.
    """
    fetcher = MagicMock()
    fetcher.get_ohlcv.return_value = mock_ohlcv_df
    fetcher.get_fundamental_info.return_value = mock_fundamental_info
    fetcher.get_risk_free_rate.return_value = mock_risk_free_rate
    return fetcher


# ---------------------------------------------------------------------------
# Async mode (required for FastAPI tests)
# ---------------------------------------------------------------------------

# asyncio_mode = "auto" is set in pyproject.toml [tool.pytest.ini_options]
# so all async test functions are handled automatically — no decorator needed.
