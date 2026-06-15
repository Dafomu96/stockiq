# ADR-001 — Data source: yfinance vs Polygon.io for the MVP

**Status:** Accepted  
**Date:** 2025-06-01  
**Author:** David Font Muñoz

---

## Context

StockIQ requires reliable OHLCV price history and basic fundamental data
(P/E, beta, dividends) for any globally-traded ticker. Two candidates
were evaluated for the MVP:

| Criterion | yfinance | Polygon.io (free tier) |
|---|---|---|
| API key required | No | Yes |
| Global tickers | Yes | Partial (US-heavy) |
| Free tier limits | Unofficial, no hard cap | 5 req/min, EOD only |
| Fundamentals | Via `.info` dict | Separate paid endpoint |
| Maintenance | Community (unofficial) | Official, versioned |
| Setup friction | `pip install yfinance` | Key signup + env var |

## Decision

Use **yfinance** as the primary source for the MVP (Phases 1–2).

## Rationale

1. **Zero onboarding friction.** The project should be cloneable and
   runnable with `pip install -r requirements.txt` and no account setup.
   This matters for portfolio reviewers and for the Streamlit Cloud deploy.

2. **Global coverage.** Swensen's model requires ETFs across multiple
   exchanges (VTI, VXUS, VWO, VNQ). Polygon's free tier is US-centric.

3. **Fundamentals included.** `yf.Ticker(ticker).info` provides P/E,
   beta, and dividends in a single call. Polygon requires a separate
   (paid) fundamentals endpoint.

## Consequences

- The `MarketDataFetcher` is written against a `CacheBackend` interface
  (not yfinance directly), so swapping the source later touches only
  `fetcher.py`, not any caller.
- The UI must display a disclaimer: data is **unofficial and EOD only**,
  not suitable for intraday trading decisions.
- If Yahoo changes their internal API (has happened before), yfinance
  may break until the community releases a fix. Polygon.io is the
  designated Phase 3 replacement.

## Revisit trigger

Switch to Polygon.io when: (a) the project moves to production with real
users, or (b) yfinance breaks and the fix takes > 48 hours.
