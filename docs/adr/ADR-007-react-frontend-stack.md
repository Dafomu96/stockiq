# ADR-007 — React frontend stack decisions

**Status:** Accepted
**Date:** 2025-06-01
**Author:** David Font Muñoz

---

## Context

Phase 5 requires a React frontend. Several technology choices had to be
made simultaneously. This ADR documents them together because they are
interconnected — the choice of bundler affects the CSS approach, which
affects the component strategy.

---

## Decision 1: Vite over Create React App / Next.js

**Chosen: Vite**

| | Vite | Create React App | Next.js |
|---|---|---|---|
| Cold start | ~300ms | ~15s | ~5s |
| Config complexity | Minimal | Hidden (eject = pain) | Significant |
| SSR needed? | No | No | Yes (but adds complexity) |
| Bundle output | Single SPA | Single SPA | SSR/SSG pages |

StockIQ is a dashboard SPA — it has no SEO requirements and no need
for server-side rendering. Next.js would add routing complexity, file-
based page conventions, and server components for zero benefit. Vite
produces a standard `dist/` folder served by nginx, which is the
simplest possible production configuration.

CRA is effectively unmaintained as of 2023. Not a viable choice.

---

## Decision 2: Tailwind CSS over CSS Modules / styled-components

**Chosen: Tailwind CSS v3**

Rationale:

- **No naming problem.** CSS Modules and styled-components both require
  inventing class or component names for every element. Tailwind
  eliminates this for layout and spacing utilities.
- **Design token discipline.** The custom `tailwind.config.js` defines
  the design tokens once (`bg-bg-primary`, `signal-buy`, `font-display`)
  and enforces consistency across all components without a separate
  design system package.
- **Purge at build time.** Tailwind v3's JIT engine includes only the
  classes actually used. The final CSS is 17KB gzipped — smaller than
  most CSS-in-JS runtimes.
- **Familiarity in the industry.** Tailwind is the most commonly used
  CSS approach in React projects as of 2024. Reviewers will recognise it.

The non-standard parts of the design (signal dot animation, page enter
fade, score bar transition) are in `index.css` as explicit `@keyframes`.
Tailwind handles layout; custom CSS handles animation.

---

## Decision 3: Recharts over Plotly / D3 / Chart.js

**Chosen: Recharts**

| | Recharts | Plotly (react-plotly.js) | D3 | Chart.js |
|---|---|---|---|---|
| Bundle size | ~180KB | ~3MB | ~100KB | ~200KB |
| React integration | Native (declarative) | Wrapper (imperative) | Manual | Wrapper |
| Customisation | High | Very high | Unlimited | Medium |
| Learning curve | Low | Medium | Very high | Low |

Plotly was used in the Streamlit app because it is already available
there. In React, the `react-plotly.js` wrapper adds 3MB to the bundle
and its API is imperative — it does not compose naturally with React's
declarative model.

D3 would give maximum control but requires building every chart primitive
from scratch. For this project's charts (area charts, bar charts) that
is unnecessary complexity.

Recharts is built on D3 internally, exposes a declarative React API, and
produces charts that are naturally responsive via `ResponsiveContainer`.
The bundle cost is acceptable given the alternative.

---

## Decision 4: Hooks-only state over Zustand / Redux

**Chosen: React hooks (`useState`, `useCallback`)**

The application has one meaningful piece of global state: the analysis
result from the last `/v1/analyze` call. This is passed via props from
`App.jsx` to each page component.

A global state library (Zustand, Redux) is justified when:
- Multiple unrelated components need the same state without prop drilling
- State mutations happen from many locations
- Time-travel debugging is required

None of these apply. The analysis result flows in one direction:
`useAnalysis` hook → `App.jsx` → page component. Adding Zustand would
introduce an abstraction with no concrete benefit at this scale.

The custom `useAnalysis` hook (`src/hooks/useAnalysis.js`) encapsulates
the API call, loading state, and error state. If the state requirements
grow, this hook is the natural place to introduce a library — the
interface it exposes to components would not change.

---

## Decision 5: react-i18next with inline resources

**Chosen: react-i18next with resources defined in `i18n.js`**

Two alternatives were considered:

- **i18next-http-backend**: loads translation JSON files via HTTP at
  runtime. Adds a loading state before the UI renders, requires the
  server to serve the locale files, and complicates the Docker build.
- **Inline resources in `i18n.js`**: both EN and ES dictionaries are
  bundled with the application. No loading state, no server dependency,
  instant language switching.

At the current scale (85 keys × 2 languages = 170 strings), inlining
adds ~3KB to the bundle. The complexity of HTTP-loaded translations is
not justified until the project supports 5+ languages.

---

## Consequences

- The React build produces a single `dist/` directory served by nginx.
  There is no Node.js process in production.
- `nginx.conf` proxies `/api/` to `http://api:8000/` (the FastAPI
  Docker service). This eliminates CORS entirely in the Docker
  environment — both frontend and backend appear to come from the
  same origin.
- In local development, CORS is handled by FastAPI's `CORSMiddleware`
  (already configured with `allow_origins=["*"]`).
- The Tailwind config's custom tokens (`bg-bg-primary`, `signal-buy`,
  etc.) are the single source of truth for the visual design. Any
  design change starts in `tailwind.config.js`, not in component files.
