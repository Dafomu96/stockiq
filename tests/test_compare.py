"""
Tests for POST /v1/compare.

All tests run offline — yfinance and FRED are mocked via dependency_overrides.
The mock fetcher returns the same DataFrame and info dict for both tickers,
which is fine because we're testing the comparison logic, not the data layer.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture()
def app():
    from backend.main import create_app
    return create_app()


@pytest.fixture()
def mock_fetcher_for_compare():
    """Mock fetcher returning realistic data for any ticker."""
    rows = 252
    idx = pd.date_range("2024-01-02", periods=rows, freq="B", tz="UTC")
    closes = [150.0 + i * 0.2 for i in range(rows)]
    df = pd.DataFrame({
        "Open": [c - 0.5 for c in closes], "High": [c + 1.0 for c in closes],
        "Low": [c - 1.0 for c in closes], "Close": closes,
        "Volume": [50_000_000] * rows,
    }, index=idx)

    mock = MagicMock()
    mock.get_ohlcv.return_value = df
    mock.get_fundamental_info.return_value = {
        "regularMarketPrice": 182.4, "trailingPE": 28.5, "beta": 1.24,
        "dividendRate": 0.96, "dividendYield": 0.0053, "earningsGrowth": 0.08,
        "forwardPE": 25.0, "shortName": "Test Inc.", "currency": "USD",
        "exchange": "NMS", "sector": "Technology", "industry": "Software",
        "marketCap": 2_000_000_000_000, "fiftyTwoWeekHigh": 199.0,
        "fiftyTwoWeekLow": 120.0, "revenueGrowth": 0.05,
        "regularMarketPreviousClose": 180.0,
    }
    mock.get_risk_free_rate.return_value = 0.045
    return mock


@pytest_asyncio.fixture()
async def client(app, mock_fetcher_for_compare):
    from backend.dependencies import get_fetcher
    app.dependency_overrides[get_fetcher] = lambda: mock_fetcher_for_compare
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


class TestCompareEndpoint:
    @pytest.mark.asyncio
    async def test_valid_request_returns_200(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_has_ticker_a_and_b(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        data = resp.json()
        assert "ticker_a" in data
        assert "ticker_b" in data
        assert data["ticker_a"]["ticker"] == "AAPL"
        assert data["ticker_b"]["ticker"] == "MSFT"

    @pytest.mark.asyncio
    async def test_response_has_verdict(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        verdict = resp.json()["verdict"]
        assert "winner" in verdict
        assert "margin" in verdict
        assert "reason" in verdict
        assert "is_tied" in verdict

    @pytest.mark.asyncio
    async def test_scores_in_valid_range(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        data = resp.json()
        for ticker_key in ["ticker_a", "ticker_b"]:
            score = data[ticker_key]["composite_score"]
            assert 0.0 <= score <= 100.0, f"{ticker_key} score {score} out of range"

    @pytest.mark.asyncio
    async def test_signals_are_valid(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        data = resp.json()
        for ticker_key in ["ticker_a", "ticker_b"]:
            assert data[ticker_key]["signal"] in ("buy", "neutral", "sell")

    @pytest.mark.asyncio
    async def test_verdict_margin_is_non_negative(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        assert resp.json()["verdict"]["margin"] >= 0

    @pytest.mark.asyncio
    async def test_winner_is_ticker_a_or_b_or_none(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        winner = resp.json()["verdict"]["winner"]
        assert winner in ("AAPL", "MSFT", None)

    @pytest.mark.asyncio
    async def test_same_ticker_returns_422(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "AAPL"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_lowercase_tickers_uppercased(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "aapl", "ticker_b": "msft"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker_a"]["ticker"] == "AAPL"
        assert data["ticker_b"]["ticker"] == "MSFT"

    @pytest.mark.asyncio
    async def test_missing_ticker_b_returns_422(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_period_returns_422(self, client):
        resp = await client.post("/v1/compare", json={
            "ticker_a": "AAPL", "ticker_b": "MSFT", "period": "99y"
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_response_has_disclaimer(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        assert "disclaimer" in resp.json()

    @pytest.mark.asyncio
    async def test_response_has_analysed_at(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        assert "analysed_at" in resp.json()

    @pytest.mark.asyncio
    async def test_both_tickers_have_technical_signals(self, client):
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        data = resp.json()
        for ticker_key in ["ticker_a", "ticker_b"]:
            t = data[ticker_key]
            assert "rsi_signal" in t
            assert "macd_signal" in t
            assert "golden_cross" in t

    @pytest.mark.asyncio
    async def test_tied_result_when_same_data(self, client):
        """When both tickers get identical data, scores should be equal → tied."""
        resp = await client.post("/v1/compare", json={"ticker_a": "AAPL", "ticker_b": "MSFT"})
        data = resp.json()
        score_a = data["ticker_a"]["composite_score"]
        score_b = data["ticker_b"]["composite_score"]
        # Same mock data → same score → should be tied
        assert abs(score_a - score_b) < 2.0
        assert data["verdict"]["is_tied"] is True
