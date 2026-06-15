"""
FastAPI dependency injection for StockIQ.

All shared resources — fetcher, cache, structured logging context —
are provided via FastAPI's dependency system. This means:
    - Every router gets the same fetcher instance (shared cache).
    - Replacing the cache backend (JSON → Redis) is a one-line change here.
    - Request logging is centralised and consistent.

Usage in a router:
    @router.post("/analyze")
    async def analyze(
        request: AnalyzeRequest,
        fetcher: MarketDataFetcher = Depends(get_fetcher),
    ) -> AnalyzeResponse:
        ...
"""

from __future__ import annotations

import logging
import time

import structlog
from fastapi import Request

from data.fetcher import MarketDataFetcher

logger = structlog.get_logger(__name__)

# Module-level singleton — shared across all requests within a process.
# The fetcher holds a reference to the cache backend; sharing it means
# all requests benefit from the same in-process cache.
_fetcher: MarketDataFetcher | None = None


def get_fetcher() -> MarketDataFetcher:
    """Dependency: return the shared MarketDataFetcher instance.

    The fetcher is created on first call and reused for all subsequent
    requests. This ensures the JSON cache is shared across requests
    within the same process.

    In tests, override with:
        app.dependency_overrides[get_fetcher] = lambda: MockFetcher()
    """
    global _fetcher
    if _fetcher is None:
        _fetcher = MarketDataFetcher()
        logger.info("fetcher_initialised cache=json_file")
    return _fetcher


async def log_request(request: Request) -> None:
    """Middleware-style dependency: log every incoming request.

    Structured logging with request metadata. In production, pipe
    these logs to a log aggregator (e.g. Datadog, CloudWatch).

    Attach to any router with:
        @router.post("/endpoint", dependencies=[Depends(log_request)])
    """
    start = time.monotonic()
    logger.info(
        "request_received",
        method=request.method,
        path=request.url.path,
        query=str(request.query_params),
        client=request.client.host if request.client else "unknown",
    )
    # We yield nothing — this is a before-only dependency
    return None
