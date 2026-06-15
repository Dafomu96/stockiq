# Changelog

All notable changes to StockIQ are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

### Planned
- Rebalancing alerts (email/webhook when drift exceeds 5pp) — requires scheduler + notification infrastructure
- Redis cache backend (replaces JSON file cache for production)
- Polygon.io as secondary data source fallback for yfinance
- React frontend tests: Overview, Technical, Fundamental, Portfolio, Simulator pages

---

## [0.6.0] — 2025-06-15 — Features, logging, and frontend tests

### Added
- `frontend/src/hooks/useWatchlist.js`: Persistent ticker watchlist via localStorage.
  Add/remove/toggle/clear. Deduplication. Max 20 tickers. Case-insensitive `isWatched`.
- `frontend/src/pages/Watchlist.jsx`: Watchlist page with score cards, last-known scores
  cached per ticker, and one-click re-analyse that navigates to Overview.
- `backend/logging_config.py`: Structured JSON logging with `configure_logging()`,
  correlation ID via `ContextVar` (async-safe, no leakage between concurrent requests),
  and `bind_request_id()` / `get_request_id()` utilities.
- `backend/routers/analyze.py`: Per-step pipeline timing logs — `fetch_ohlcv_ms`,
  `fetch_info_ms`, `indicators_ms`, `fundamental_ms`, `technical_ms`, `scoring_ms`,
  `total_ms`. Cache hit/miss visible in every log line.
- `backend/schemas_compare.py`: `CompareRequest`, `ScoreSummary`, `WinnerVerdict`,
  `CompareResponse` — Pydantic schemas for the compare endpoint.
- `backend/routers/compare.py`: `POST /v1/compare` — concurrent analysis of two tickers
  via `asyncio.gather` + `run_in_executor`. Programmatic verdict with margin, winner,
  and human-readable reason. ~half the wall time of two sequential `/analyze` calls.
- `frontend/src/pages/Compare.jsx`: Side-by-side comparison page with verdict banner,
  score columns, metric table (green/red per metric based on `higherIsBetter` flag),
  and educational ExplainBox.
- `frontend/src/hooks/useHistory.js`: Persistent analysis history via localStorage.
  Newest first. Replaces previous entry for same ticker. Max 20 entries.
- `frontend/src/pages/History.jsx`: History page with score bars, signal badge,
  CAPM return, Gordon upside, re-analyse button, and clear-all.
- `frontend/src/hooks/useAnalysis.js`: Updated — `run()` now returns the result data
  so callers can push to history/watchlist cache without extra effects.
- `frontend/vitest.config.js`: Vitest configuration with jsdom environment, coverage
  thresholds (70% lines/functions), and setup file.
- `frontend/src/__tests__/setup.js`: Global test setup — `@testing-library/jest-dom`,
  localStorage clear before each test, `crypto.randomUUID` stub for jsdom.
- `frontend/src/__tests__/hooks/useWatchlist.test.js`: 18 tests — add, remove, toggle,
  isWatched (case-insensitive), clear, localStorage persistence, max-20 cap.
- `frontend/src/__tests__/hooks/useHistory.test.js`: 14 tests — push, deduplication,
  newest-first ordering, max-20 cap, remove by id, clear, localStorage persistence.
- `frontend/src/__tests__/components/ui.test.jsx`: 23 tests — `SignalBadge`,
  `ScoreBar`, `MetricCard`, `ExplainBox`, `EmptyState`, `ErrorState`, `scoreColor`.
- `frontend/src/__tests__/pages/Glossary.test.jsx`: 9 tests — search filter,
  category filter, combined filter, zero-results state, CAPM term visibility.
- `tests/test_logging.py`: 11 tests — `X-Request-ID` header echoed from client,
  unique UUIDs per request, `X-Process-Time` header, concurrent context isolation.
- `tests/test_compare.py`: 15 tests — valid comparison, uppercase normalisation,
  same-ticker 422, score range, verdict structure, tied result when same data.
- `tests/conftest.py`: Shared pytest fixtures — `mock_fetcher`, `mock_ohlcv_df`,
  `mock_fundamental_info`, `mock_risk_free_rate`. All tests 100% offline.
- `tests/fixtures/sample_responses/`: Realistic JSON responses for `analyze_AAPL.json`,
  `portfolio_drifted.json`, `simulate_AAPL.json` — living documentation of the API.
- `Makefile`: `make setup`, `make test`, `make lint`, `make run-api`, `make docker`.
- `setup.ps1`: One-command project setup for Windows PowerShell.
- `setup.sh`: One-command project setup for Mac/Linux.
- `docs/adr/ADR-006-two-frontends.md`: Why Streamlit MVP + React production.
- `docs/adr/ADR-007-react-frontend-stack.md`: Vite, Tailwind, Recharts, hooks state,
  react-i18next with inline resources.

### Changed
- `backend/main.py`: Correlation ID middleware — every request gets a UUID injected
  into all log lines via `ContextVar`. `X-Request-ID` and `X-Process-Time` response headers.
  Global exception handlers log structured events before returning JSON errors.
- `backend/main.py`: Added `compare.router` to the application.
- `frontend/src/App.jsx`: Added Watchlist, Compare, History pages to navigation.
  Star button (★/☆) next to analyse button for quick watchlist toggle.
  Watchlist and History nav items show count badges.
  `handleAnalyse` is now async and pushes results to history automatically.

### Frontend test summary
```
64 tests · 4 test files · 3.55s · 0 failures
  useWatchlist.test.js    18 tests
  useHistory.test.js      14 tests
  ui.test.jsx             23 tests
  Glossary.test.jsx        9 tests
```

### Backend test summary (cumulative)
```
383 tests · 8 test files · ~30s · 0 failures · 96% coverage
```

---

## [0.5.0] — 2025-06-01 — Phase 5: React frontend

### Added
- `frontend/src/lib/api.js`: Fetch-based API client with dev logging and normalised error shape
- `frontend/src/lib/i18n.js`: react-i18next setup with inline EN/ES resources
- `frontend/src/hooks/useAnalysis.js`: Central state hook — loading, error, result, caching
- `frontend/src/components/ui.jsx`: `SignalBadge` (pulsing dot), `ScoreBar`, `MetricCard`,
  `SignalRow`, `ExplainBox` (with bibliographic source), `DataWarnings`, `EmptyState`, `ErrorState`
- `frontend/src/components/Charts.jsx`: `SimulationChart` (AreaChart with gradient bands),
  `DriftChart` (horizontal bar with ±5pp threshold lines), `AllocationBars`
- `frontend/src/pages/`: Overview · Technical · Fundamental · Portfolio · Simulator · Glossary
- `frontend/nginx.conf`: Serves React SPA, proxies `/api/` to FastAPI backend
- `frontend/Dockerfile`: Multi-stage (Node 20 build → nginx:alpine runtime)
- `docker-compose.yml`: Added `frontend` service on port 3000
- `docs/adr/ADR-006-two-frontends.md`: Rationale for Streamlit MVP + React production
- `docs/adr/ADR-007-react-frontend-stack.md`: Vite, Tailwind, Recharts, hooks state, i18n

### Design
- Typography: Syne (display) + DM Sans (body) + JetBrains Mono (numbers/tickers)
- Palette: near-black background (#040812), green/amber/red signal colours, blue accent
- Animations: CSS fadeUp stagger on page enter, score bar transitions (700ms), pulsing signal dot

---

## [0.4.0] — 2025-06-01 — Phase 4: Docker + CI/CD

### Added
- `Dockerfile`: Multi-stage build (builder with gcc/g++ → runtime without build tools, non-root user)
- `Dockerfile.streamlit`: Identical structure, starts with `streamlit run`
- `docker-compose.yml`: `api` (port 8000) + `streamlit` (port 8501) sharing a named volume
- `.dockerignore`: Excludes `__pycache__`, tests, `.env`, `node_modules`
- `.env.example`: All configurable env vars documented with defaults
- `.github/workflows/ci.yml`: Three-job pipeline — `quality` (ruff + black + mypy) →
  `tests` (pytest + coverage ≥85%) → `docker` (build + smoke test, main branch only)
- `.pre-commit-config.yaml`: ruff, black, trailing-whitespace, no-commit-to-branch on main
- `CONTRIBUTING.md`: Conventional Commits guide, branch strategy, PR checklist
- `docs/adr/ADR-005-docker-ci-strategy.md`: Rationale for multi-stage, non-root, smoke test

### CI features
- `concurrency: cancel-in-progress` — stale runs cancelled on new push
- Docker layer caching with `type=gha` — faster rebuilds
- Smoke test: starts the API container and calls `/health` to verify the image runs

---

## [0.3.0] — 2025-06-01 — Phase 3: FastAPI backend

### Added
- `backend/main.py`: FastAPI application factory with rate limiting (slowapi),
  CORS middleware, request timing header, and global exception handlers
- `backend/schemas.py`: Pydantic v2 request/response schemas for all endpoints
- `backend/mappers.py`: Pure mapping layer (domain dataclasses → Pydantic schemas)
- `backend/routers/analyze.py`: `POST /v1/analyze` — full Shiller + Murphy analysis
- `backend/routers/portfolio.py`: `POST /v1/portfolio` — Swensen portfolio analysis
- `backend/routers/simulate.py`: `POST /v1/simulate` — P&L scenario simulation
- `backend/dependencies.py`: Shared fetcher instance via FastAPI dependency injection
- `tests/test_api.py`: 36 integration tests (100% offline, httpx + dependency_overrides)
- `docs/adr/ADR-004-api-design.md`: API design decisions (versioning, schemas, error handling)

---

## [0.2.0] — 2025-06-01 — Phase 2: Streamlit MVP

### Added
- `app/streamlit_app.py`: Main app with sidebar navigation, language toggle,
  ticker input, analysis pipeline, and session state management
- `app/i18n.py`: Translation helper (`t(key)`) with EN/ES JSON dictionaries
- `app/components.py`: Reusable components (signal badge, score gauge, metric card,
  signal row, explain box, data warnings, disclaimer footer)
- `app/charts.py`: Plotly chart builders (price + indicators, allocation donuts,
  simulation projection, drift bar chart)
- `app/pages/`: overview · technical · fundamental · portfolio · simulator · glossary
- `i18n/en.json`, `i18n/es.json`: 85 UI string keys in English and Spanish

---

## [0.1.0] — 2025-06-01 — Phase 1: Core Python engine

### Added
- `config/settings.py`: Pydantic Settings — all configuration in one place
- `config/exceptions.py`: Typed exception hierarchy
- `data/cache.py`: Abstract `CacheBackend` + `JsonFileCache` (ADR-002)
- `data/fetcher.py`: `MarketDataFetcher` — yfinance + FRED, cached, graceful fallback
- `analysis/fundamentals.py`: CAPM, Gordon Growth Model, PDV, P/E analysis, fundamental score
- `analysis/technical.py`: RSI, MACD, Bollinger Bands, SMA/EMA, OBV, ADX, technical score
- `analysis/scoring.py`: Strategy Pattern composite scorer, `CompositeResult` output contract
- `analysis/swensen.py`: 6-asset Swensen allocation, drift, rebalancing, ETF mapping
- `simulation/simulator.py`: P&L simulation — 3 scenarios, DCA, VaR, Sharpe, break-even
- `tests/`: 283 tests, 96.4% coverage — 100% offline
- `docs/adr/`: ADR-001 through ADR-003

---

[Unreleased]: https://github.com/Dafomu96/stockiq/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/Dafomu96/stockiq/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Dafomu96/stockiq/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Dafomu96/stockiq/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Dafomu96/stockiq/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Dafomu96/stockiq/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Dafomu96/stockiq/releases/tag/v0.1.0
