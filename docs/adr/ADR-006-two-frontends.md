# ADR-006 — Two frontends: Streamlit MVP + React production build

**Status:** Accepted
**Date:** 2025-06-01
**Author:** David Font Muñoz

---

## Context

StockIQ needs a user interface. After completing the core Python engine
(Phase 1) and the FastAPI backend (Phase 3), two frontend options were
considered:

**Option A** — Build only Streamlit. Ship it, done.

**Option B** — Build Streamlit first as an MVP, then React as the
production frontend. Two codebases, more work.

**Option C** — Skip Streamlit, build only React from the start.

## Decision

**Option B: Streamlit first, React second.**

## Rationale

### Why not Option A (Streamlit only)

Streamlit is excellent for data scientists prototyping analysis tools.
It is not a production frontend framework. Limitations that matter here:

- **No custom routing** — URL does not reflect the current page, so
  sharing a link to the Technical Analysis page is impossible.
- **Layout constraints** — Streamlit's column system is a wrapper around
  CSS grid. Complex layouts (sidebar + multi-panel charts + signal table)
  require fighting the framework rather than expressing intent directly.
- **Performance** — every widget interaction triggers a full Python
  re-run. For an analysis dashboard with 6 charts, this is noticeable.
- **Portfolio signal** — a Streamlit-only project signals a data science
  background. A React + FastAPI + Docker project signals full-stack
  engineering capability. The target audience for this portfolio is
  ML/AI Engineer roles that require backend and frontend awareness.

### Why not Option C (React only, skip Streamlit)

Streamlit is the right tool for rapid UI validation. Building the
Streamlit MVP took ~1 week and revealed several UX problems
(information hierarchy, which metrics matter most, how to present
the educational notes) before committing to the React architecture.
Discovering those problems in React would have cost 3–4x more time.

The Streamlit app is also a legitimate deliverable: it can be deployed
to Streamlit Cloud for free with a public URL, giving the project a
live demo from Phase 2 onwards without waiting for the React build.

### Why Option B is correct

The two frontends are not redundant — they serve different purposes:

| | Streamlit (Phase 2) | React (Phase 5) |
|---|---|---|
| Purpose | Rapid prototyping, live demo | Production frontend |
| Audience | Data scientists, recruiters | End users |
| Deploy | Streamlit Cloud (free, instant) | nginx + Docker |
| State | Python session_state | React hooks |
| Routing | Page modules | Client-side (hash) |
| Charts | Plotly | Recharts |

The Streamlit app remains in the repository because it demonstrates
the ability to deliver working software quickly, which is a distinct
engineering skill from building a polished production system.

## Consequences

- Two `requirements.txt` consumers: the Python backend and the Streamlit
  app both depend on the same `requirements.txt`. This is intentional —
  the Streamlit app imports from `analysis/` and `simulation/` directly.
- The React frontend talks exclusively to the FastAPI backend via HTTP.
  It has no direct Python dependency.
- `docker-compose.yml` has three services: `api`, `streamlit`, `frontend`.
  Running all three is optional — `docker compose up api frontend` is
  the production configuration.
- The Streamlit app is a maintenance burden going forward. If the project
  grows significantly, the Streamlit pages should be deprecated in favour
  of the React frontend. The trigger for that decision: when the React
  frontend has feature parity with Streamlit.
