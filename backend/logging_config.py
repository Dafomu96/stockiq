"""
Structured logging configuration for StockIQ.

Uses structlog to produce JSON log lines that are queryable in any
log aggregator (Datadog, CloudWatch, ELK, Loki).

Every log line produced by StockIQ includes:
    timestamp   ISO-8601 UTC
    level       debug / info / warning / error
    logger      module name (e.g. "backend.routers.analyze")
    request_id  UUID per HTTP request — links all log lines for one request
    event       human-readable description of what happened

Additional fields per event type:
    ticker, duration_ms, cache_hit, score, signal, confidence ...

Design:
    - structlog is configured once at import time via configure_logging().
    - call_next middleware in main.py injects request_id into every
      log line produced during that request via contextvars.
    - All analysis modules use standard logging.getLogger(__name__) —
      structlog intercepts stdlib logging and adds the structured context.

Usage in any module:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("cache_hit", extra={"ticker": "AAPL", "ttl": 86400})

In middleware (main.py):
    from backend.logging_config import bind_request_id
    bind_request_id(request_id)
"""

from __future__ import annotations

import logging
import logging.config
import uuid
from contextvars import ContextVar

import structlog

# ── Context variable that holds the current request ID ─────────────────────────
# ContextVar is safe under async concurrency — each request gets its own value
# without leaking into other concurrent requests.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    """Return the request ID bound to the current async context."""
    return _request_id_var.get()


def bind_request_id(request_id: str) -> None:
    """Bind a request ID to the current async context.

    Call this once per request, before any logging happens.
    The value is automatically available in all log lines produced
    during this request, including from called functions and dependencies.
    """
    _request_id_var.set(request_id)


def _add_request_id(
    logger: object,
    method: str,
    event_dict: dict,
) -> dict:
    """structlog processor: inject request_id from ContextVar."""
    event_dict["request_id"] = _request_id_var.get()
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog and stdlib logging for StockIQ.

    Call once at application startup (in main.py lifespan).

    Produces JSON lines in production:
        {"timestamp": "...", "level": "info", "logger": "...",
         "request_id": "...", "event": "...", ...extra fields}

    In development (log_level=DEBUG), adds prettier console output.

    Args:
        log_level: Minimum log level. "DEBUG" for dev, "INFO" for prod.
    """
    shared_processors = [
        # Add log level as a string field
        structlog.stdlib.add_log_level,
        # Add logger name (module) as "logger" field
        structlog.stdlib.add_logger_name,
        # Add ISO timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Inject request_id from ContextVar
        _add_request_id,
        # Format exceptions as structured dicts, not tracebacks
        structlog.processors.format_exc_info,
        # Stack info if needed
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors + [
            # Bridge: pass stdlib log records through structlog pipeline
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure the stdlib formatter to render as JSON
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    for noisy in ("yfinance", "peewee", "urllib3", "requests", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
