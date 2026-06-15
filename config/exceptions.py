"""
Custom exception hierarchy for StockIQ.

Typed exceptions let callers handle specific failure modes without
catching bare Exception. Each error carries enough context to log
or surface a meaningful message to the user.

Design principle: fail loudly with context, never silently.
"""


class StockIQError(Exception):
    """Base class for all StockIQ domain errors."""


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

class DataFetchError(StockIQError):
    """Raised when all data sources fail for a given ticker.

    Args:
        ticker: The ticker symbol that could not be fetched.
        reason: Human-readable explanation of the failure.

    Example:
        raise DataFetchError("INVALID", "yfinance returned empty DataFrame")
    """

    def __init__(self, ticker: str, reason: str) -> None:
        self.ticker = ticker
        self.reason = reason
        super().__init__(f"Failed to fetch data for '{ticker}': {reason}")


class CacheError(StockIQError):
    """Raised when the cache layer cannot read or write."""


class RateLimitError(StockIQError):
    """Raised when an external API returns a rate-limit response."""


# ---------------------------------------------------------------------------
# Analysis layer
# ---------------------------------------------------------------------------

class InsufficientDataError(StockIQError):
    """Raised when there are not enough data points to compute an indicator.

    Args:
        indicator: Name of the indicator that could not be computed.
        required: Minimum bars required.
        available: Actual bars available.

    Example:
        raise InsufficientDataError("SMA200", required=200, available=90)
    """

    def __init__(self, indicator: str, required: int, available: int) -> None:
        self.indicator = indicator
        self.required = required
        self.available = available
        super().__init__(
            f"Cannot compute {indicator}: need {required} bars, got {available}"
        )


class ModelAssumptionError(StockIQError):
    """Raised when a financial model's assumptions are violated.

    Typical case: Gordon Growth Model requires g < r.
    Surfaced as a user-facing warning rather than a crash.

    Args:
        model: Name of the model (e.g. 'Gordon Growth Model').
        violation: Description of the broken assumption.

    Example:
        raise ModelAssumptionError(
            "Gordon Growth Model",
            "growth rate g=0.12 must be strictly less than discount rate r=0.10"
        )
    """

    def __init__(self, model: str, violation: str) -> None:
        self.model = model
        self.violation = violation
        super().__init__(f"{model} assumption violated: {violation}")


class InvalidTickerError(StockIQError):
    """Raised when a ticker symbol is not recognised by the data source.

    Args:
        ticker: The unrecognised symbol.
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        super().__init__(
            f"Ticker '{ticker}' was not found. "
            "Check the symbol and the exchange suffix (e.g. 'ASML.AS' for Euronext)."
        )
