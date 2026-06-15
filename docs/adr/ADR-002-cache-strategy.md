# ADR-002 — Cache strategy: JSON files (MVP) with Redis interface

**Status:** Accepted  
**Date:** 2025-06-01  
**Author:** David Font Muñoz

---

## Context

StockIQ makes network calls to yfinance and FRED that are slow (~1–3s)
and rate-limited. Responses must be cached. Three options were considered:

| Option | Pros | Cons |
|---|---|---|
| No cache | Simplest code | Every request hits the network; rate-limit risk |
| JSON files | Zero deps, human-readable, debuggable | Not concurrent; slow for large datasets |
| Redis | Fast, concurrent, TTL native | Requires Docker or external service for dev |

## Decision

Implement a **`CacheBackend` abstract interface** with a **`JsonFileCache`
concrete implementation** for the MVP. The interface is designed so
`RedisCache` can replace it in Phase 3 by changing one line in the
factory function `get_cache()`.

## Rationale

1. **The interface is the important decision.** Callers (`fetcher.py`,
   future `fundamentals.py`) depend on `CacheBackend`, not on the
   storage technology. This is the Dependency Inversion Principle in
   practice.

2. **JSON files are good enough for a single-user MVP.** Race conditions
   are irrelevant when one person is using the app. The files are
   human-readable — useful when debugging unexpected cache hits.

3. **Deferred complexity.** Redis adds a daemon, Docker Compose, and
   connection pooling. That complexity belongs in Phase 3, not Phase 1.

## TTL strategy

| Data type | TTL | Reasoning |
|---|---|---|
| OHLCV prices | 24 hours | EOD data — refreshes once per trading day |
| Fundamentals | 24 hours | P/E, beta update at most daily |
| Risk-free rate | 7 days | T-bill 10Y changes weekly at most |

## Consequences

- `data/cache.py` exports `CacheBackend` (ABC) and `JsonFileCache`.
- All tests inject `JsonFileCache(tmp_path)` — never the default path —
  so CI runs leave no artefacts on disk.
- Phase 3 migration: implement `RedisCache(CacheBackend)` and update
  `get_cache()`. Zero changes to `fetcher.py` or analysis modules.
