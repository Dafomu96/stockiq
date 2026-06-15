"""
StockIQ FastAPI application — entry point for Phase 3.

Run with:
    uvicorn backend.main:app --reload --port 8000

Or via Docker Compose (Phase 4):
    docker compose up

Architecture:
    - Application factory pattern: create_app() returns a configured
      FastAPI instance. This makes the app testable without side effects.
    - All routers are registered here with their prefix.
    - Rate limiting (slowapi), CORS, and structured logging middleware
      are configured here — not in individual routers.
    - Global exception handlers translate domain exceptions to HTTP
      responses with consistent JSON shape.

See: ADR-004 — API design decisions.
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.routers import analyze, portfolio, simulate
from backend.schemas import HealthResponse
from config.exceptions import DataFetchError, InvalidTickerError, ModelAssumptionError
from config.settings import settings

# ── Ensure project root is on path (when running from project root) ──────────
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Structured logging setup ──────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)

# ── Rate limiter (slowapi) ────────────────────────────────────────────────────

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.api_rate_limit],  # "10/minute" from settings
)


# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(
        "stockiq_api_starting",
        rate_limit=settings.api_rate_limit,
        cache_dir=settings.cache_dir,
    )
    yield
    logger.info("stockiq_api_shutting_down")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Separating creation from instantiation allows tests to call
    create_app() without triggering module-level side effects.

    Returns:
        Configured FastAPI instance ready to serve requests.
    """
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
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "health", "description": "API health check"},
            {"name": "analysis", "description": "Stock analysis (Shiller + Murphy)"},
            {"name": "portfolio", "description": "Portfolio analysis (Swensen)"},
            {"name": "simulation", "description": "P&L simulation"},
        ],
    )

    # ── Rate limiting ─────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # ── CORS ──────────────────────────────────────────────────────────────
    # In production, replace "*" with the actual frontend origin.
    # Phase 4: "http://localhost:5173" (Vite dev) and the deployed URL.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Accept"],
    )

    # ── Request timing middleware ─────────────────────────────────────────
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        """Add X-Process-Time header to every response."""
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.1f}ms"
        logger.debug(
            "request_complete",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        return response

    # ── Global exception handlers ─────────────────────────────────────────
    @app.exception_handler(InvalidTickerError)
    async def invalid_ticker_handler(request: Request, exc: InvalidTickerError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "ticker_not_found",
                "ticker": exc.ticker,
                "detail": str(exc),
            },
        )

    @app.exception_handler(DataFetchError)
    async def data_fetch_handler(request: Request, exc: DataFetchError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "data_source_unavailable",
                "ticker": exc.ticker,
                "detail": exc.reason,
            },
        )

    @app.exception_handler(ModelAssumptionError)
    async def model_assumption_handler(request: Request, exc: ModelAssumptionError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "model_assumption_violated",
                "model": exc.model,
                "detail": exc.violation,
            },
        )

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "detail": "An unexpected error occurred. Please try again.",
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(analyze.router)
    app.include_router(portfolio.router)
    app.include_router(simulate.router)

    # ── Health endpoint ───────────────────────────────────────────────────
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="API health check",
    )
    async def health() -> HealthResponse:
        """Returns API status and version. Used by Docker healthcheck."""
        return HealthResponse(
            status="ok",
            version="0.2.0",
            message="StockIQ API is running. See /docs for the full API reference.",
        )

    return app


# ── Module-level app instance (used by uvicorn) ───────────────────────────────
app = create_app()
