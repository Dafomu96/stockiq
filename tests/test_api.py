"""
Integration tests for the FastAPI backend.

All external calls (yfinance, FRED) are mocked — tests run 100% offline.
Uses httpx.AsyncClient with FastAPI's ASGI transport for realistic
request/response testing without starting a server.

Test organisation:
    TestHealth           — GET /health
    TestAnalyzeEndpoint  — POST /v1/analyze (happy path + error cases)
    TestPortfolioEndpoint — POST /v1/portfolio
    TestSimulateEndpoint  — POST /v1/simulate
    TestSchemaValidation — Pydantic request validation
    TestGlobalErrorHandlers — Domain exceptions → HTTP codes
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.main import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    """Fresh FastAPI app instance per test (no shared state)."""
    return create_app()


@pytest_asyncio.fixture()
async def client(app):
    """Async httpx client wired to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


def _make_ohlcv_df(rows: int = 252) -> pd.DataFrame:
    """Minimal OHLCV DataFrame matching MarketDataFetcher output."""
    idx = pd.date_range("2023-01-02", periods=rows, freq="B", tz="UTC")
    closes = [150.0 + i * 0.2 for i in range(rows)]
    return pd.DataFrame(
        {
            "Open": [c - 0.5 for c in closes],
            "High": [c + 1.0 for c in closes],
            "Low": [c - 1.0 for c in closes],
            "Close": closes,
            "Volume": [50_000_000] * rows,
        },
        index=idx,
    )


def _make_info() -> dict:
    return {
        "regularMarketPrice": 182.40,
        "regularMarketPreviousClose": 180.0,
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


# ── Mock patch helper ────────────────────────────────────────────────────────

def _patch_fetcher(mock_df=None, mock_info=None, mock_rf=0.045):
    """Return a context manager that patches all fetcher methods."""
    df = mock_df if mock_df is not None else _make_ohlcv_df()
    info = mock_info if mock_info is not None else _make_info()

    mock = MagicMock()
    mock.get_ohlcv.return_value = df
    mock.get_fundamental_info.return_value = info
    mock.get_risk_free_rate.return_value = mock_rf
    return mock


# ---------------------------------------------------------------------------
# TestHealth
# ---------------------------------------------------------------------------

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_shape(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_docs_accessible(self, client):
        resp = await client.get("/docs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_openapi_schema_accessible(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema
        assert "/v1/analyze" in schema["paths"]


# ---------------------------------------------------------------------------
# TestAnalyzeEndpoint
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:
    @pytest.mark.asyncio
    async def test_valid_request_returns_200(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        assert resp.status_code == 200

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_response_has_required_fields(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        data = resp.json()

        assert "ticker" in data
        assert "composite_score" in data
        assert "signal" in data
        assert "fundamental" in data
        assert "technical" in data
        assert "disclaimer" in data

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_ticker_uppercased_in_response(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "aapl"})
        assert resp.json()["ticker"] == "AAPL"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_composite_score_in_valid_range(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        score = resp.json()["composite_score"]
        assert 0.0 <= score <= 100.0

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_signal_is_valid_value(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        assert resp.json()["signal"] in ("buy", "neutral", "sell")

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_fundamental_only_strategy_accepted(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post(
            "/v1/analyze",
            json={"ticker": "AAPL", "strategy": "fundamental_only"},
        )
        assert resp.status_code == 200
        assert "fundamental" in resp.json()["strategy_name"].lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_invalid_ticker_returns_404(self, client, app):
        from backend.dependencies import get_fetcher
        from config.exceptions import InvalidTickerError

        mock_fetcher = MagicMock()
        mock_fetcher.get_ohlcv.side_effect = InvalidTickerError("NOTREAL")
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "NOTREAL"})
        assert resp.status_code == 404
        assert "detail" in resp.json()  # HTTPException format

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_data_fetch_error_returns_503(self, client, app):
        from backend.dependencies import get_fetcher
        from config.exceptions import DataFetchError

        mock_fetcher = MagicMock()
        mock_fetcher.get_ohlcv.side_effect = DataFetchError("AAPL", "yfinance timeout")
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        assert resp.status_code == 503
        assert "detail" in resp.json()  # HTTPException format

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_response_has_x_process_time_header(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        assert "x-process-time" in resp.headers

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_disclaimer_present_and_non_empty(self, client, app):
        mock_fetcher = _patch_fetcher()
        from backend.dependencies import get_fetcher
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher

        resp = await client.post("/v1/analyze", json={"ticker": "AAPL"})
        disclaimer = resp.json()["disclaimer"]
        assert len(disclaimer) > 50
        assert "financial advice" in disclaimer.lower()

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TestPortfolioEndpoint
# ---------------------------------------------------------------------------

class TestPortfolioEndpoint:
    _valid_payload = {
        "current_allocation": {
            "domestic_equity": 0.30,
            "international_equity": 0.15,
            "emerging_markets": 0.05,
            "real_estate": 0.20,
            "government_bonds": 0.15,
            "inflation_protected": 0.15,
        },
        "total_value": 50_000.0,
    }

    @pytest.mark.asyncio
    async def test_valid_request_returns_200(self, client):
        resp = await client.post("/v1/portfolio", json=self._valid_payload)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_response_has_six_positions(self, client):
        resp = await client.post("/v1/portfolio", json=self._valid_payload)
        assert len(resp.json()["positions"]) == 6

    @pytest.mark.asyncio
    async def test_perfect_portfolio_scores_100(self, client):
        resp = await client.post("/v1/portfolio", json=self._valid_payload)
        score = resp.json()["swensen_score"]
        assert score == pytest.approx(100.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_perfect_portfolio_needs_no_rebalancing(self, client):
        resp = await client.post("/v1/portfolio", json=self._valid_payload)
        assert resp.json()["needs_rebalancing"] is False

    @pytest.mark.asyncio
    async def test_drifted_portfolio_needs_rebalancing(self, client):
        drifted = dict(self._valid_payload)
        drifted["current_allocation"] = {
            "domestic_equity": 0.50,  # +20pp overweight
            "international_equity": 0.15,
            "emerging_markets": 0.05,
            "real_estate": 0.10,      # -10pp underweight
            "government_bonds": 0.10, # -5pp underweight
            "inflation_protected": 0.10,
        }
        resp = await client.post("/v1/portfolio", json=drifted)
        assert resp.json()["needs_rebalancing"] is True
        assert len(resp.json()["rebalancing_actions"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_asset_class_returns_400(self, client):
        bad = dict(self._valid_payload)
        bad["current_allocation"] = {"not_a_real_class": 1.0}
        resp = await client.post("/v1/portfolio", json=bad)
        assert resp.status_code == 422  # Pydantic validation

    @pytest.mark.asyncio
    async def test_projection_has_correct_year_count(self, client):
        payload = dict(self._valid_payload)
        payload["horizon_years"] = 15
        resp = await client.post("/v1/portfolio", json=payload)
        assert len(resp.json()["projection"]["year_by_year"]) == 15

    @pytest.mark.asyncio
    async def test_total_value_zero_returns_422(self, client):
        bad = dict(self._valid_payload)
        bad["total_value"] = 0
        resp = await client.post("/v1/portfolio", json=bad)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestSimulateEndpoint
# ---------------------------------------------------------------------------

class TestSimulateEndpoint:
    _valid_payload = {
        "ticker": "AAPL",
        "initial_investment": 10_000.0,
        "horizon_years": 10,
    }

    @pytest.mark.asyncio
    async def test_valid_request_returns_200(self, client):
        resp = await client.post("/v1/simulate", json=self._valid_payload)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_three_scenarios_returned(self, client):
        resp = await client.post("/v1/simulate", json=self._valid_payload)
        assert len(resp.json()["scenarios"]) == 3

    @pytest.mark.asyncio
    async def test_scenario_labels(self, client):
        resp = await client.post("/v1/simulate", json=self._valid_payload)
        labels = {s["label"] for s in resp.json()["scenarios"]}
        assert labels == {"pessimistic", "base", "optimistic"}

    @pytest.mark.asyncio
    async def test_dca_null_when_no_monthly(self, client):
        resp = await client.post("/v1/simulate", json=self._valid_payload)
        assert resp.json()["dca"] is None

    @pytest.mark.asyncio
    async def test_dca_present_when_monthly_given(self, client):
        payload = dict(self._valid_payload)
        payload["monthly_contribution"] = 200.0
        resp = await client.post("/v1/simulate", json=payload)
        assert resp.json()["dca"] is not None

    @pytest.mark.asyncio
    async def test_capm_rate_used_as_base(self, client):
        payload = dict(self._valid_payload)
        payload["capm_required_return"] = 0.095
        resp = await client.post("/v1/simulate", json=payload)
        base = next(s for s in resp.json()["scenarios"] if s["label"] == "base")
        assert base["annual_rate"] == pytest.approx(0.095, abs=1e-4)

    @pytest.mark.asyncio
    async def test_year_by_year_length(self, client):
        payload = dict(self._valid_payload)
        payload["horizon_years"] = 20
        resp = await client.post("/v1/simulate", json=payload)
        assert len(resp.json()["year_by_year"]) == 20

    @pytest.mark.asyncio
    async def test_risk_metrics_present(self, client):
        resp = await client.post("/v1/simulate", json=self._valid_payload)
        risk = resp.json()["risk"]
        assert "sharpe_ratio" in risk
        assert "value_at_risk_95" in risk
        assert "max_drawdown_estimate" in risk

    @pytest.mark.asyncio
    async def test_zero_investment_returns_422(self, client):
        bad = dict(self._valid_payload)
        bad["initial_investment"] = 0
        resp = await client.post("/v1/simulate", json=bad)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_horizon_above_50_returns_422(self, client):
        bad = dict(self._valid_payload)
        bad["horizon_years"] = 51
        resp = await client.post("/v1/simulate", json=bad)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestSchemaValidation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    @pytest.mark.asyncio
    async def test_missing_ticker_returns_422(self, client):
        resp = await client.post("/v1/analyze", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_period_returns_422(self, client):
        resp = await client.post(
            "/v1/analyze", json={"ticker": "AAPL", "period": "99y"}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_strategy_returns_422(self, client):
        resp = await client.post(
            "/v1/analyze",
            json={"ticker": "AAPL", "strategy": "magic_strategy"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_simulate_missing_investment_returns_422(self, client):
        resp = await client.post("/v1/simulate", json={"ticker": "AAPL"})
        assert resp.status_code == 422
