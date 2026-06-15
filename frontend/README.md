# StockIQ — React Frontend

React + Vite frontend for the StockIQ investment analysis platform.
Communicates exclusively with the FastAPI backend via HTTP.

## Stack

- **React 18** + **Vite** — SPA, no SSR needed (ADR-007)
- **Tailwind CSS v3** — utility-first, design tokens in `tailwind.config.js`
- **Recharts** — declarative charts (AreaChart, BarChart)
- **react-i18next** — bilingual EN/ES with inline resources
- **axios** — HTTP client for the FastAPI backend

## Structure

```
src/
├── lib/
│   ├── api.js          # Fetch wrapper for /v1/analyze, /v1/portfolio, /v1/simulate
│   └── i18n.js         # react-i18next setup with EN/ES inline resources
├── hooks/
│   └── useAnalysis.js  # Central state hook — loading, error, result
├── components/
│   ├── ui.jsx          # SignalBadge, ScoreBar, MetricCard, ExplainBox, etc.
│   └── Charts.jsx      # SimulationChart, DriftChart, AllocationBars
└── pages/
    ├── Overview.jsx    # Composite score + key metrics
    ├── Technical.jsx   # RSI, MACD, Bollinger Bands, SMA signal table
    ├── Fundamental.jsx # CAPM, Gordon Growth Model, P/E analysis
    ├── Portfolio.jsx   # Swensen allocation builder + rebalancing
    ├── Simulator.jsx   # P&L projection with DCA and risk metrics
    └── Glossary.jsx    # Bilingual glossary with source citations
```

## Development

```bash
# Requires the FastAPI backend running on http://localhost:8000
cp .env.example .env
npm install
npm run dev         # http://localhost:5173
```

## Production build

```bash
npm run build       # outputs to dist/
# Served by nginx — see nginx.conf
# nginx proxies /api/ → http://api:8000/ (Docker Compose service)
```

## Docker

```bash
# From the project root
docker compose up frontend   # http://localhost:3000
```

The production image is multi-stage: Node 20 builds the bundle, then
nginx:alpine serves the static files. The final image has no Node.js
runtime — just the compiled HTML/CSS/JS.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | FastAPI backend base URL |

In Docker Compose, the nginx proxy handles API routing — `VITE_API_URL`
is not used. In local dev, it must point to your running FastAPI instance.
