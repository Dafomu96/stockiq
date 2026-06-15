"""
StockIQ FastAPI application — entry point for Phase 3.

Changes from the original version:
    - Structured JSON logging via logging_config.configure_logging()
    - Correlation ID middleware: every request gets a UUID injected into
      all log lines produced during that request via ContextVar
    - Pipeline timing: X-Process-Time header + logged duration_ms
    - X-Request-ID response header so clients can correlate log lines
      with specific requests (useful in production debugging)

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.logging_config import bind_request_id, configure_logging
from backend.routers import analyze, portfolio, simulate
from backend.schemas import HealthResponse
from config.exceptions import DataFetchError, InvalidTickerError, ModelAssumptionError
from config.settings import settings

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.api_rate_limit],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(log_level="INFO")
    logger.info(
        "stockiq_api_starting",
        extra={
            "rate_limit": settings.api_rate_limit,
            "cache_dir": settings.cache_dir,
            "version": "0.6.0",
        },
    )
    yield
    logger.info("stockiq_api_shutting_down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="StockIQ API",
        description=(
            "Long-term investment analysis API combining Shiller (fundamental), "
            "Murphy (technical), and Swensen (portfolio) frameworks.\n\n"
            "**Data notice:** All price data is End-of-Day (EOD). "
            "Not suitable for intraday trading decisions.\n\n"
            "**Disclaimer:** This API is for educational purposes only and does "
            "not constitute financial advice."
        ),
        version="0.6.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "health",     "description": "API health check"},
            {"name": "analysis",   "description": "Stock analysis (Shiller + Murphy)"},
            {"name": "portfolio",  "description": "Portfolio analysis (Swensen)"},
            {"name": "simulation", "description": "P&L simulation"},
        ],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Accept", "X-Request-ID"],
    )

    # ── Correlation ID + timing middleware ─────────────────────────────────────
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        """Inject a correlation ID and log every request with timing.

        The request_id is:
        1. Read from the incoming X-Request-ID header if provided by the client.
           This allows end-to-end tracing when the client also logs request IDs.
        2. Generated as a UUID4 if not provided.

        The ID is:
        - Bound to the async ContextVar so all log lines within this request
          automatically include it (via _add_request_id processor).
        - Added to the response as X-Request-ID so the client can correlate
          the response with their own logs.
        - Logged at the start and end of every request with timing.
        """
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        bind_request_id(request_id)

        start = time.monotonic()

        logger.info(
            "request_started",
            extra={
                "method":  request.method,
                "path":    request.url.path,
                "client":  request.client.host if request.client else "unknown",
            },
        )

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        response.headers["X-Process-Time"] = f"{duration_ms}ms"
        response.headers["X-Request-ID"]   = request_id

        logger.info(
            "request_completed",
            extra={
                "method":      request.method,
                "path":        request.url.path,
                "status":      response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response

    # ── Global exception handlers ──────────────────────────────────────────────

    @app.exception_handler(InvalidTickerError)
    async def invalid_ticker_handler(request: Request, exc: InvalidTickerError):
        logger.warning(
            "invalid_ticker",
            extra={"ticker": exc.ticker, "path": request.url.path},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error":  "ticker_not_found",
                "ticker": exc.ticker,
                "detail": str(exc),
            },
        )

    @app.exception_handler(DataFetchError)
    async def data_fetch_handler(request: Request, exc: DataFetchError):
        logger.error(
            "data_fetch_failed",
            extra={"ticker": exc.ticker, "reason": exc.reason},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error":  "data_source_unavailable",
                "ticker": exc.ticker,
                "detail": exc.reason,
            },
        )

    @app.exception_handler(ModelAssumptionError)
    async def model_assumption_handler(request: Request, exc: ModelAssumptionError):
        logger.warning(
            "model_assumption_violated",
            extra={"model": exc.model, "violation": exc.violation},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error":     "model_assumption_violated",
                "model":     exc.model,
                "detail":    exc.violation,
            },
        )

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            extra={
                "path":     request.url.path,
                "exc_type": type(exc).__name__,
                "error":    str(exc),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error":  "internal_server_error",
                "detail": "An unexpected error occurred. Please try again.",
            },
        )

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(analyze.router)
    app.include_router(portfolio.router)
    app.include_router(simulate.router)

    # ── Health ─────────────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["health"],
             summary="API health check")
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version="0.6.0",
            message="StockIQ API is running. See /docs for the full API reference.",
        )

    return app


app = create_app()
