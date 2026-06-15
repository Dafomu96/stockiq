"""
FastAPI dependency injection for StockIQ.

get_fetcher   — shared MarketDataFetcher instance (one per process)
log_request   — structured pre-request logging dependency
"""

from __future__ import annotations

import logging

from fastapi import Request

from data.fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)

_fetcher: MarketDataFetcher | None = None


def get_fetcher() -> MarketDataFetcher:
    """Return the shared MarketDataFetcher instance.

    Created on first call and reused for all subsequent requests.
    All requests share the same JSON cache, so a cache warm from
    one request benefits subsequent requests for the same ticker.

    Override in tests:
        app.dependency_overrides[get_fetcher] = lambda: mock_fetcher
    """
    global _fetcher
    if _fetcher is None:
        _fetcher = MarketDataFetcher()
        logger.info("fetcher_initialised", extra={"cache": "json_file"})
    return _fetcher


async def log_request(request: Request) -> None:
    """Log the incoming request path and method at DEBUG level.

    The full request logging (with timing and status code) happens in
    the middleware — this dependency just records which endpoint was hit,
    before any handler logic runs.

    It is intentionally lightweight: no body parsing, no header inspection.
    """
    logger.debug(
        "endpoint_called",
        extra={
            "method":      request.method,
            "path":        request.url.path,
            "query":       str(request.query_params) or None,
        },
    )
