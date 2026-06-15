# ADR-004 — FastAPI backend: API design decisions

**Status:** Accepted
**Date:** 2025-06-01
**Author:** David Font Muñoz

---

## Context

Phase 3 requires a REST API that exposes the Phase 1 analysis engine.
Several design decisions were non-obvious.

## Decisions

### 1. Application factory pattern (`create_app()`)

The app is created by a function, not at module level. This allows
tests to call `create_app()` and get a fresh, isolated instance
without side effects from module-level imports.

### 2. Pydantic v2 schemas, not direct dataclass serialisation

FastAPI can serialise Python dataclasses directly, but:
- Our domain dataclasses use `frozen=True` and custom enums that
  don't serialise cleanly without configuration.
- Explicit Pydantic schemas give us OpenAPI documentation, automatic
  validation error messages, and a stable contract separate from the
  domain model.
- The mapper layer (`backend/mappers.py`) converts domain → schema.
  If the domain changes, only the mapper changes.

### 3. Versioned URL prefix (`/v1/`)

All endpoints are under `/v1/`. When breaking changes are needed,
`/v2/` routes can be added without removing `/v1/`, giving clients
time to migrate.

### 4. Rate limiting with slowapi (10 req/min)

yfinance has informal rate limits. The API rate limit (10/min)
prevents a single client from exhausting the data source.
Configurable via `STOCKIQ_API_RATE_LIMIT` env var.

### 5. Global exception handlers for domain exceptions

`InvalidTickerError`, `DataFetchError`, and `ModelAssumptionError`
are caught globally and translated to consistent JSON error responses.
Routers never catch bare `Exception` — they let it propagate to
the global handler, which also logs the event.

### 6. Structured JSON logging with structlog

Every request is logged with method, path, status, and duration.
JSON format makes logs queryable in any log aggregator (Datadog,
CloudWatch, ELK). In tests, structlog output is suppressed.

## Consequences

- The Pydantic schema layer is extra code, but it provides a stable
  API contract independent of internal refactoring.
- The `/v1/` prefix allows future non-breaking evolution.
- Tests must use `httpx.AsyncClient` with `app=create_app()` to get
  a fresh app per test — this is the correct approach.
