# Changelog

All notable changes to StockIQ are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [Unreleased]

### Planned
- Redis cache backend (replaces JSON file cache for production)
- Polygon.io as secondary data source fallback for yfinance
- AWS deployment guide (ECS + ALB)

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
- `docs/adr/ADR-006-two-frontends.md`: Rationale for Streamlit MVP + React production (two frontends)
- `docs/adr/ADR-007-react-frontend-stack.md`: Vite vs CRA/Next.js, Recharts vs Plotly, Tailwind vs CSS Modules, hooks-only state

### Design
- Typography: Syne (display) + DM Sans (body) + JetBrains Mono (numbers/tickers)
- Palette: near-black background (#040812), green/amber/red signal colours, blue accent
- Animations: CSS fadeUp stagger on page enter, score bar transitions (700ms), pulsing signal dot

---

## [0.4.0] — 2025-06-01 — Phase 4: Docker + CI/CD

### Added
- `Dockerfile`: Multi-stage build (builder with gcc/g++ → runtime without build tools, non-root user)
- `Dockerfile.streamlit`: Identical structure, starts with `streamlit run` instead of `uvicorn`
- `docker-compose.yml`: `api` (port 8000) + `streamlit` (port 8501) sharing a named volume for cache
- `.dockerignore`: Excludes `__pycache__`, tests, `.env`, `node_modules` from Docker context
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

### Changed
- CI pipeline updated to include async test mode (`--asyncio-mode=auto`)

---

## [0.2.0] — 2025-06-01 — Phase 2: Streamlit MVP

### Added
- `app/streamlit_app.py`: Main app with sidebar navigation, language toggle,
  ticker input, analysis pipeline, and session state management
- `app/i18n.py`: Translation helper (`t(key)`) with EN/ES JSON dictionaries
- `app/components.py`: Reusable components (signal badge, score gauge,
  metric card, signal row, explain box, data warnings, disclaimer footer)
- `app/charts.py`: Plotly chart builders (price + indicators, allocation
  donuts, simulation projection, drift bar chart)
- `app/pages/overview.py`: Overview page (badge, gauges, metrics, quick chart)
- `app/pages/technical.py`: Technical analysis page with signal table
- `app/pages/fundamental.py`: Fundamental analysis page (CAPM, Gordon, P/E)
- `app/pages/portfolio.py`: Swensen portfolio builder with rebalancing UI
- `app/pages/simulator.py`: P&L simulator with DCA and risk metrics
- `app/pages/glossary.py`: Bilingual interactive glossary (13 terms, Murphy/Shiller/Swensen)
- `i18n/en.json`, `i18n/es.json`: 85 UI string keys in English and Spanish

---

## [0.1.0] — 2025-06-01 — Phase 1: Core Python engine

### Added
- `config/settings.py`: Pydantic Settings — all configuration in one place
- `config/exceptions.py`: Typed exception hierarchy (DataFetchError, InvalidTickerError,
  ModelAssumptionError, InsufficientDataError)
- `data/cache.py`: Abstract `CacheBackend` + `JsonFileCache` (ADR-002)
- `data/fetcher.py`: `MarketDataFetcher` — yfinance + FRED, with cache and graceful fallback
- `analysis/fundamentals.py`: CAPM, Gordon Growth Model, PDV, P/E analysis, fundamental score
- `analysis/technical.py`: RSI, MACD, Bollinger Bands, SMA/EMA, OBV, ADX, technical score
- `analysis/scoring.py`: Strategy Pattern composite scorer (WeightedAverageStrategy,
  FundamentalOnlyStrategy), `CompositeResult` output contract
- `analysis/swensen.py`: 6-asset Swensen allocation, drift analysis, rebalancing,
  ETF recommendations with UCITS alternatives, growth projection
- `simulation/simulator.py`: P&L simulation (3 scenarios, DCA, VaR, Sharpe, break-even)
- `tests/`: 283 tests, 96.4% coverage — 100% offline
- `docs/adr/`: ADR-001 through ADR-003

---

[Unreleased]: https://github.com/Dafomu96/stockiq/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/Dafomu96/stockiq/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Dafomu96/stockiq/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Dafomu96/stockiq/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Dafomu96/stockiq/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Dafomu96/stockiq/releases/tag/v0.1.0
