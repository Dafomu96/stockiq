# ADR-005 — Docker and CI strategy

**Status:** Accepted
**Date:** 2025-06-01
**Author:** David Font Muñoz

---

## Context

Phase 4 requires containerisation and a CI pipeline that a recruiter
or HM can inspect to verify production-readiness.

## Decisions

### 1. Multi-stage Dockerfile (not single-stage)

A single-stage build would include gcc, g++, pip, and all build
artefacts in the final image. Multi-stage:
- Stage 1 (builder): gcc, g++, compiles C extensions
- Stage 2 (runtime): only the venv + app code

Result: final image ~40% smaller, no build tools available to an
attacker who gains container access.

### 2. Non-root user in runtime

`useradd appuser` in the runtime stage. Running as root inside a
container is a security anti-pattern — if the container is
compromised, the attacker has root on the host (with some caveats).
Minimal containers never run as root.

### 3. Named volume for the JSON cache

`cache_data:/app/.cache` in docker-compose.yml. Without this, every
`docker compose restart` clears the cache and the first request
re-fetches all data from yfinance. A named volume persists the cache
across restarts while keeping it isolated from the host filesystem.

### 4. CI job order: quality → tests → docker

- `quality` and `tests` run in parallel — neither depends on the other.
- `docker` requires both to pass first.
- Docker builds only run on pushes to `main` — not on every PR commit.
  Building Docker images is slow (2–5 min); the fast quality+test gate
  is the appropriate check for PR validation.

### 5. Smoke test in CI

The CI pipeline starts the API container and calls `/health` to verify
the image actually runs. A Dockerfile that builds but crashes on start
is worthless — the smoke test catches this.

### 6. pre-commit mirrors CI

The same ruff + black + mypy checks that run in CI also run locally
as pre-commit hooks. This eliminates the "fails in CI, works locally"
feedback loop.

### 7. concurrency: cancel-in-progress

If two pushes land on the same branch within seconds, the older CI
run is cancelled. This prevents stale runs from consuming minutes and
giving misleading results.

## Consequences

- `docker compose up` starts both the API and Streamlit with one command.
- The CI pipeline is a hard gate: merges to main require lint + type
  check + tests + 85% coverage + Docker smoke test.
- The pre-commit config ensures these checks run before every commit.
