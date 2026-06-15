"""
Tests for data/fetcher.py.

Design principles:
- All tests run OFFLINE. yfinance and FRED are mocked with pytest-mock.
  The CI pipeline must never depend on external network availability.
- Each test covers one behaviour. Test names follow the pattern:
  test_<method>_<condition>_<expected_outcome>.
- Edge cases are as important as the happy path.

Run with:
    pytest tests/test_fetcher.py -v --cov=data.fetcher
"""

import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from config.exceptions import DataFetchError, InvalidTickerError
from data.cache import JsonFileCache
from data.fetcher import MarketDataFetcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_cache(tmp_path):
    """Return a JsonFileCache backed by a temp directory.

    Using tmp_path (pytest built-in) ensures each test gets a clean cache
    with no cross-test pollution.
    """
    return JsonFileCache(cache_dir=str(tmp_path))


@pytest.fixture()
def fetcher(tmp_cache):
    """Return a MarketDataFetcher wired to the temp cache."""
    return MarketDataFetcher(cache=tmp_cache)


def _make_ohlcv_df(rows: int = 252) -> pd.DataFrame:
    """Build a minimal but realistic OHLCV DataFrame for testing.

    252 bars ≈ one trading year — enough for all technical indicators.
    """
    idx = pd.date_range("2023-01-02", periods=rows, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "Open":   [150.0 + i * 0.1 for i in range(rows)],
            "High":   [152.0 + i * 0.1 for i in range(rows)],
            "Low":    [149.0 + i * 0.1 for i in range(rows)],
            "Close":  [151.0 + i * 0.1 for i in range(rows)],
            "Volume": [50_000_000] * rows,
        },
        index=idx,
    )


def _make_info_dict() -> dict:
    """Minimal yfinance .info dict for a fictional ticker."""
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


# ---------------------------------------------------------------------------
# get_ohlcv — happy path
# ---------------------------------------------------------------------------

class TestGetOhlcv:
    def test_returns_clean_dataframe_on_success(self, fetcher):
        mock_df = _make_ohlcv_df()
        with patch("data.fetcher.yf.download", return_value=mock_df):
            result = fetcher.get_ohlcv("AAPL")

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert len(result) == 252

    def test_index_is_utc_datetime(self, fetcher):
        mock_df = _make_ohlcv_df()
        with patch("data.fetcher.yf.download", return_value=mock_df):
            result = fetcher.get_ohlcv("AAPL")

        assert result.index.tzinfo is not None
        assert str(result.index.tzinfo) == "UTC"

    def test_index_is_sorted_ascending(self, fetcher):
        mock_df = _make_ohlcv_df()
        with patch("data.fetcher.yf.download", return_value=mock_df):
            result = fetcher.get_ohlcv("AAPL")

        assert result.index.is_monotonic_increasing

    def test_result_is_cached_on_first_call(self, fetcher, tmp_cache):
        mock_df = _make_ohlcv_df()
        with patch("data.fetcher.yf.download", return_value=mock_df) as mock_dl:
            fetcher.get_ohlcv("AAPL")
            fetcher.get_ohlcv("AAPL")   # second call — should use cache

        # yfinance should only be called once
        assert mock_dl.call_count == 1

    def test_close_column_is_float64(self, fetcher):
        mock_df = _make_ohlcv_df()
        with patch("data.fetcher.yf.download", return_value=mock_df):
            result = fetcher.get_ohlcv("AAPL")

        assert result["Close"].dtype == "float64"

    # --- Edge cases ---

    def test_raises_invalid_ticker_error_on_empty_dataframe(self, fetcher):
        with patch("data.fetcher.yf.download", return_value=pd.DataFrame()):
            with pytest.raises(InvalidTickerError) as exc_info:
                fetcher.get_ohlcv("NOTAREAL")

        assert "NOTAREAL" in str(exc_info.value)

    def test_raises_data_fetch_error_when_yfinance_throws(self, fetcher):
        with patch("data.fetcher.yf.download", side_effect=Exception("timeout")):
            with pytest.raises(DataFetchError) as exc_info:
                fetcher.get_ohlcv("AAPL")

        assert "AAPL" in str(exc_info.value)
        assert "timeout" in str(exc_info.value)

    def test_handles_multiindex_columns_from_yfinance(self, fetcher):
        """yfinance >= 0.2 sometimes returns MultiIndex columns for single tickers."""
        mock_df = _make_ohlcv_df()
        mock_df.columns = pd.MultiIndex.from_tuples(
            [(c, "AAPL") for c in mock_df.columns]
        )
        with patch("data.fetcher.yf.download", return_value=mock_df):
            result = fetcher.get_ohlcv("AAPL")

        assert "Close" in result.columns

    def test_drops_rows_with_nan_close(self, fetcher):
        mock_df = _make_ohlcv_df(rows=10)
        mock_df.loc[mock_df.index[3], "Close"] = float("nan")
        with patch("data.fetcher.yf.download", return_value=mock_df):
            result = fetcher.get_ohlcv("AAPL")

        assert len(result) == 9
        assert result["Close"].isna().sum() == 0

    def test_non_us_ticker_accepted(self, fetcher):
        """Ticker symbols with exchange suffix (e.g. ASML.AS) must work."""
        mock_df = _make_ohlcv_df()
        with patch("data.fetcher.yf.download", return_value=mock_df):
            result = fetcher.get_ohlcv("ASML.AS")

        assert not result.empty


# ---------------------------------------------------------------------------
# get_fundamental_info
# ---------------------------------------------------------------------------

class TestGetFundamentalInfo:
    def test_returns_expected_keys(self, fetcher):
        mock_ticker = MagicMock()
        mock_ticker.info = _make_info_dict()
        with patch("data.fetcher.yf.Ticker", return_value=mock_ticker):
            info = fetcher.get_fundamental_info("AAPL")

        assert "trailingPE" in info
        assert "beta" in info
        assert "dividendRate" in info
        assert info["shortName"] == "Apple Inc."

    def test_missing_fields_are_none_not_keyerror(self, fetcher):
        """If yfinance omits a field, we return None — never KeyError."""
        sparse_info = {"regularMarketPrice": 100.0}  # most fields missing
        mock_ticker = MagicMock()
        mock_ticker.info = sparse_info
        with patch("data.fetcher.yf.Ticker", return_value=mock_ticker):
            info = fetcher.get_fundamental_info("XYZ")

        assert info["beta"] is None
        assert info["trailingPE"] is None

    def test_raises_invalid_ticker_on_empty_info(self, fetcher):
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        with patch("data.fetcher.yf.Ticker", return_value=mock_ticker):
            with pytest.raises(InvalidTickerError):
                fetcher.get_fundamental_info("FAKE")

    def test_result_is_cached(self, fetcher):
        mock_ticker = MagicMock()
        mock_ticker.info = _make_info_dict()
        with patch("data.fetcher.yf.Ticker", return_value=mock_ticker) as mock_cls:
            fetcher.get_fundamental_info("AAPL")
            fetcher.get_fundamental_info("AAPL")

        assert mock_cls.call_count == 1

    def test_raises_data_fetch_error_on_exception(self, fetcher):
        with patch("data.fetcher.yf.Ticker", side_effect=Exception("network error")):
            with pytest.raises(DataFetchError):
                fetcher.get_fundamental_info("AAPL")


# ---------------------------------------------------------------------------
# get_risk_free_rate
# ---------------------------------------------------------------------------

class TestGetRiskFreeRate:
    def test_returns_decimal_not_percentage(self, fetcher):
        """FRED returns '4.50' (percent); we must return 0.045."""
        csv_body = "DATE,DGS10\n2024-01-15,4.50\n"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_body
        mock_resp.raise_for_status = MagicMock()

        with patch("data.fetcher.requests.get", return_value=mock_resp):
            rate = fetcher.get_risk_free_rate()

        assert rate == pytest.approx(0.045, abs=1e-6)

    def test_falls_back_to_settings_when_fred_unreachable(self, fetcher):
        """Network failure → fallback rate, no crash."""
        import requests as req_lib
        with patch("data.fetcher.requests.get", side_effect=req_lib.RequestException("timeout")):
            rate = fetcher.get_risk_free_rate()

        from config.settings import settings
        assert rate == settings.risk_free_rate_fallback

    def test_result_is_cached(self, fetcher):
        csv_body = "DATE,DGS10\n2024-01-15,4.25\n"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_body
        mock_resp.raise_for_status = MagicMock()

        with patch("data.fetcher.requests.get", return_value=mock_resp) as mock_get:
            fetcher.get_risk_free_rate()
            fetcher.get_risk_free_rate()

        assert mock_get.call_count == 1

    def test_skips_dot_placeholder_rows(self, fetcher):
        """FRED uses '.' for missing values — must be skipped."""
        csv_body = "DATE,DGS10\n2024-01-13,.\n2024-01-14,.\n2024-01-15,4.30\n"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = csv_body
        mock_resp.raise_for_status = MagicMock()

        with patch("data.fetcher.requests.get", return_value=mock_resp):
            rate = fetcher.get_risk_free_rate()

        assert rate == pytest.approx(0.043, abs=1e-6)
