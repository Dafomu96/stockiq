# StockIQ

![CI](https://github.com/Dafomu96/stockiq/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/Dafomu96/stockiq/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)
![React](https://img.shields.io/badge/React-18-61DAFB)
![License](https://img.shields.io/badge/license-MIT-green)

Long-term investment analysis tool combining three intellectual frameworks:

| Framework | Question answered | Models |
|---|---|---|
| **Shiller** | Is this asset fairly valued? | CAPM · Gordon Growth Model · P/E · PDV |
| **Murphy** | When is a good technical entry? | RSI · MACD · Bollinger Bands · SMA/EMA · OBV · ADX |
| **Swensen** | What should I own and in what proportions? | 6-class allocation · drift detection · rebalancing |

> **Disclaimer:** StockIQ is an educational tool. Nothing here constitutes
> financial advice. All data is End-of-Day (EOD) — not suitable for intraday
> trading. Past performance does not guarantee future results.

---

## Features

- **Composite scoring engine** (0–100): weighted average of fundamental and technical scores, configurable via the Strategy Pattern (ADR-003)
- **Swensen portfolio analyser**: 6-asset allocation, 5pp drift detection, rebalancing actions, ETF recommendations with UCITS alternatives for EU investors
- **P&L simulator**: 3-scenario projections (pessimistic/base/optimistic), DCA, VaR (95%), Sharpe ratio, margin of safety
- **Bilingual UI** (English / Spanish) — both Streamlit and React frontends
- **Educational glossary**: 13 terms with source citations (Murphy, Shiller, Swensen, Bodie)
- **Global ticker support**: Yahoo Finance format, exchange suffixes (ASML.AS, 7203.T, SAN.MC)
- **REST API** (FastAPI): `/v1/analyze`, `/v1/portfolio`, `/v1/simulate` with OpenAPI docs
- **React frontend**: Vite + Tailwind + Recharts, served via nginx, proxies the FastAPI backend

---

## Architecture

```
stockiq/
├── config/
│   ├── settings.py        # Pydantic Settings — all config, never hardcoded
│   └── exceptions.py      # Typed exception hierarchy
├── data/
│   ├── fetcher.py         # yfinance + FRED, cached, graceful degradation
│   └── cache.py           # Abstract CacheBackend + JsonFileCache (ADR-002)
├── analysis/
│   ├── fundamentals.py    # CAPM, Gordon Growth Model, P/E, PDV
│   ├── technical.py       # RSI, MACD, Bollinger Bands, SMA, OBV, ADX
│   ├── scoring.py         # Strategy Pattern composite scorer (ADR-003)
│   └── swensen.py         # 6-asset allocation, rebalancing, ETF mapping
├── simulation/
│   └── simulator.py       # P&L projections, DCA, VaR, Sharpe, break-even
├── backend/               # FastAPI REST API (Phase 3)
│   ├── main.py            # App factory, middleware, error handlers
│   ├── schemas.py         # Pydantic request/response contracts
│   ├── mappers.py         # Domain → schema translation layer
│   └── routers/           # analyze · portfolio · simulate
├── app/                   # Streamlit MVP (Phase 2)
│   ├── streamlit_app.py   # Entry point, sidebar, routing
│   ├── components.py      # Reusable UI components
│   ├── charts.py          # Plotly chart builders
│   └── pages/             # overview · technical · fundamental · portfolio · simulator · glossary
├── frontend/              # React + Vite frontend (Phase 5)
│   ├── src/
│   │   ├── lib/           # api.js · i18n.js
│   │   ├── hooks/         # useAnalysis.js
│   │   ├── components/    # ui.jsx · Charts.jsx
│   │   └── pages/         # Overview · Technical · Fundamental · Portfolio · Simulator · Glossary
│   ├── nginx.conf         # Serves build + proxies /api/ to FastAPI
│   └── Dockerfile         # Multi-stage: Node build → nginx:alpine runtime
├── i18n/
│   ├── en.json            # 85 English UI strings
│   └── es.json            # 85 Spanish UI strings
├── tests/                 # 319 tests, 96% coverage, 100% offline
└── docs/adr/              # ADR-001 through ADR-005
```

---

## Quick start

```bash
git clone https://github.com/Dafomu96/stockiq.git
cd stockiq
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Verify everything works
pytest tests/ --asyncio-mode=auto -q

# Streamlit app (Phase 2 MVP)
streamlit run app/streamlit_app.py

# FastAPI backend + Swagger UI at http://localhost:8000/docs
uvicorn backend.main:app --reload --port 8000

# React frontend (Phase 5) — requires the API running on :8000
cd frontend && npm install && npm run dev
```

### Docker Compose (all three services)

```bash
docker compose up
# React frontend: http://localhost:3000
# API + Docs:     http://localhost:8000/docs
# Streamlit MVP:  http://localhost:8501
```

---

## API reference

Three endpoints, all documented at `/docs` (Swagger UI) and `/redoc`:

**POST /v1/analyze**
```json
{ "ticker": "ASML.AS", "period": "1y", "strategy": "weighted_average" }
```

**POST /v1/portfolio**
```json
{
  "current_allocation": {
    "domestic_equity": 0.40, "international_equity": 0.15,
    "emerging_markets": 0.05, "real_estate": 0.15,
    "government_bonds": 0.15, "inflation_protected": 0.10
  },
  "total_value": 50000
}
```

**POST /v1/simulate**
```json
{
  "ticker": "AAPL",
  "initial_investment": 10000,
  "horizon_years": 10,
  "monthly_contribution": 200,
  "capm_required_return": 0.098
}
```

---

## Testing

```bash
pytest tests/ --asyncio-mode=auto -v          # full suite
pytest tests/ --asyncio-mode=auto --cov=.     # with coverage
pytest tests/test_api.py --asyncio-mode=auto  # API tests only
```

Coverage is enforced at ≥85% in CI. All 319 tests run offline — no network calls.

---

## Architecture Decision Records

| ADR | Decision |
|---|---|
| [ADR-001](docs/adr/ADR-001-data-source.md) | yfinance over Polygon.io for the MVP |
| [ADR-002](docs/adr/ADR-002-cache-strategy.md) | JSON file cache with Redis-compatible interface |
| [ADR-003](docs/adr/ADR-003-scoring-strategy-pattern.md) | Strategy Pattern for the composite scoring engine |
| [ADR-004](docs/adr/ADR-004-api-design.md) | FastAPI API design (versioning, schemas, error handling) |
| [ADR-005](docs/adr/ADR-005-docker-ci-strategy.md) | Docker multi-stage build and CI strategy |
| [ADR-006](docs/adr/ADR-006-two-frontends.md) | Two frontends: Streamlit MVP + React production |
| [ADR-007](docs/adr/ADR-007-react-frontend-stack.md) | React stack: Vite, Tailwind, Recharts, hooks state |

---

## Roadmap

- [x] **Phase 1** — Core Python engine (data, fundamentals, technical, scoring, Swensen, simulator)
- [x] **Phase 2** — Streamlit MVP with bilingual UI (6 pages, EN/ES, interactive charts)
- [x] **Phase 3** — FastAPI backend (3 REST endpoints, rate limiting, structured logging, 36 API tests)
- [x] **Phase 4** — Docker + CI/CD (multi-stage builds, compose, pre-commit, GitHub Actions)
- [x] **Phase 5** — React + Vite frontend (Recharts, react-i18next, nginx, Docker)

---

## References

- Shiller, R.J. (2000). *Irrational Exuberance*. Princeton University Press.
- Murphy, J.J. (1999). *Technical Analysis of the Financial Markets*. NYIF.
- Swensen, D.F. (2005). *Unconventional Success*. Free Press.
- Bodie, Z., Kane, A., Marcus, A.J. (2014). *Investments* (10th ed.). McGraw-Hill.
- Sharpe, W.F. (1994). The Sharpe Ratio. *Journal of Portfolio Management*, 21(1).

## License

MIT
