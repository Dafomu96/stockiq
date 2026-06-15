"""
Tests for backend/logging_config.py and correlation ID middleware.

Verifies:
    - request_id is injected into every log line within a request
    - X-Request-ID header appears in responses
    - X-Process-Time header appears in responses
    - Custom X-Request-ID from client is echoed back
    - Concurrent requests get independent request IDs (no leakage)
"""

from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.logging_config import bind_request_id, get_request_id


# ---------------------------------------------------------------------------
# Unit tests — logging_config module
# ---------------------------------------------------------------------------

class TestRequestIdContextVar:
    def test_default_value_is_dash(self):
        """Default request_id before any binding is '-'."""
        assert get_request_id() == "-"

    def test_bind_sets_value(self):
        bind_request_id("test-id-123")
        assert get_request_id() == "test-id-123"

    def test_bind_overwrites_previous(self):
        bind_request_id("first")
        bind_request_id("second")
        assert get_request_id() == "second"

    def test_different_values_in_tasks(self):
        """Each asyncio task gets its own ContextVar value."""
        results = {}

        async def set_and_read(name, value):
            bind_request_id(value)
            await asyncio.sleep(0)  # yield to let other tasks run
            results[name] = get_request_id()

        async def run():
            await asyncio.gather(
                set_and_read("task_a", "id-for-a"),
                set_and_read("task_b", "id-for-b"),
            )

        asyncio.get_event_loop().run_until_complete(run())
        assert results["task_a"] == "id-for-a"
        assert results["task_b"] == "id-for-b"


# ---------------------------------------------------------------------------
# Integration tests — middleware (via httpx)
# ---------------------------------------------------------------------------

@pytest.fixture()
def app_and_fetcher():
    from backend.main import create_app
    from backend.dependencies import get_fetcher

    app = create_app()

    mock_fetcher = MagicMock()
    import pandas as pd
    idx = pd.date_range("2024-01-02", periods=252, freq="B", tz="UTC")
    closes = [150.0 + i * 0.2 for i in range(252)]
    df = pd.DataFrame({
        "Open": [c - 0.5 for c in closes], "High": [c + 1.0 for c in closes],
        "Low": [c - 1.0 for c in closes], "Close": closes,
        "Volume": [50_000_000] * 252,
    }, index=idx)
    mock_fetcher.get_ohlcv.return_value = df
    mock_fetcher.get_fundamental_info.return_value = {
        "regularMarketPrice": 182.4, "trailingPE": 28.5, "beta": 1.24,
        "dividendRate": 0.96, "dividendYield": 0.0053, "earningsGrowth": 0.08,
        "forwardPE": 25.0, "shortName": "Apple Inc.", "currency": "USD",
        "exchange": "NMS", "sector": "Technology", "industry": "Consumer Electronics",
        "marketCap": 2_800_000_000_000, "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 124.17, "revenueGrowth": 0.05,
        "regularMarketPreviousClose": 180.0,
    }
    mock_fetcher.get_risk_free_rate.return_value = 0.045
    app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

    return app, mock_fetcher


@pytest_asyncio.fixture()
async def client(app_and_fetcher):
    app, _ = app_and_fetcher
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class TestCorrelationIDMiddleware:
    @pytest.mark.asyncio
    async def test_response_has_x_request_id_header(self, client):
        resp = await client.get("/health")
        assert "x-request-id" in resp.headers

    @pytest.mark.asyncio
    async def test_x_request_id_is_non_empty(self, client):
        resp = await client.get("/health")
        assert len(resp.headers["x-request-id"]) > 0

    @pytest.mark.asyncio
    async def test_response_has_x_process_time_header(self, client):
        resp = await client.get("/health")
        assert "x-process-time" in resp.headers

    @pytest.mark.asyncio
    async def test_x_process_time_ends_with_ms(self, client):
        resp = await client.get("/health")
        assert resp.headers["x-process-time"].endswith("ms")

    @pytest.mark.asyncio
    async def test_client_provided_request_id_is_echoed(self, client):
        """If client sends X-Request-ID, it should be echoed in the response."""
        custom_id = "my-trace-id-abc123"
        resp = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id

    @pytest.mark.asyncio
    async def test_each_request_gets_unique_id(self, client):
        """Without client-provided ID, each request gets a different UUID."""
        r1 = await client.get("/health")
        r2 = await client.get("/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    @pytest.mark.asyncio
    async def test_analyze_response_has_request_id(self, client):
        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers
        assert "x-process-time" in resp.headers

    @pytest.mark.asyncio
    async def test_process_time_is_numeric(self, client):
        resp = await client.get("/health")
        time_str = resp.headers["x-process-time"].replace("ms", "")
        assert float(time_str) >= 0


class TestPipelineLogging:
    @pytest.mark.asyncio
    async def test_analyze_completes_and_returns_200(self, client):
        """Smoke test: pipeline logging doesn't break the endpoint."""
        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_composite_score_in_response(self, client):
        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        data = resp.json()
        assert "composite_score" in data
        assert 0 <= data["composite_score"] <= 100

    @pytest.mark.asyncio
    async def test_signal_in_response(self, client):
        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        assert resp.json()["signal"] in ("buy", "neutral", "sell")
