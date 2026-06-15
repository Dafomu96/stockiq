"""
POST /v1/portfolio — Swensen portfolio analysis endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from analysis.swensen import AssetClass, analyse_portfolio
from backend.dependencies import log_request
from backend.mappers import to_portfolio_response
from backend.schemas import PortfolioRequest, PortfolioResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["portfolio"])


@router.post(
    "/portfolio",
    response_model=PortfolioResponse,
    summary="Analyse portfolio against Swensen model",
    description=(
        "Compares a current portfolio allocation against the Swensen 6-asset "
        "model. Returns drift analysis, rebalancing actions when drift > 5pp, "
        "a Swensen alignment score (0–100), and a 10-year growth projection. "
        "\n\nAll projections are gross nominal returns. Taxes and costs not included."
    ),
)
async def portfolio(
    body: PortfolioRequest,
    _log: None = Depends(log_request),
) -> PortfolioResponse:
    """Analyse a portfolio allocation against the Swensen framework.

    The request maps asset class string keys to decimal weights.
    Missing classes are treated as 0%. Weights are normalised if
    they don't sum to 1.0.
    """
    logger.info(
        "portfolio_start total_value=%.0f horizon=%dy",
        body.total_value, body.horizon_years,
    )

    # Convert string keys → AssetClass enum
    try:
        current_alloc = {
            AssetClass(key): weight
            for key, weight in body.current_allocation.items()
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid asset class key: {exc}",
        ) from exc

    try:
        result = analyse_portfolio(
            current_allocation=current_alloc,
            total_value=body.total_value,
            horizon_years=body.horizon_years,
            rebalance_threshold=body.rebalance_threshold,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info(
        "portfolio_complete score=%.1f needs_rebalancing=%s actions=%d",
        result.swensen_score, result.needs_rebalancing,
        len(result.rebalancing_actions),
    )

    return to_portfolio_response(result)
