"""
POST /v1/simulate — P&L simulation endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import log_request
from backend.mappers import to_simulate_response
from backend.schemas import SimulateRequest, SimulateResponse
from simulation.simulator import simulate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["simulation"])


@router.post(
    "/simulate",
    response_model=SimulateResponse,
    summary="Run P&L simulation",
    description=(
        "Projects portfolio value under three return scenarios (pessimistic, "
        "base, optimistic), optionally with monthly DCA contributions. "
        "Returns risk metrics (Sharpe ratio, VaR 95%, max drawdown) and, "
        "if Gordon fair value is provided, a margin of safety analysis. "
        "\n\nAll projections assume constant annual returns. Real markets are "
        "volatile. Results are gross nominal and do not include taxes or costs."
    ),
)
async def simulate_endpoint(
    body: SimulateRequest,
    _log: None = Depends(log_request),
) -> SimulateResponse:
    """Run a P&L simulation for a given ticker and investment amount.

    Provide capm_required_return from a prior /analyze call to get
    a personalised base rate instead of the default Swensen 7.2%.
    """
    logger.info(
        "simulate_start ticker=%s investment=%.0f horizon=%dy monthly=%.0f",
        body.ticker, body.initial_investment,
        body.horizon_years, body.monthly_contribution,
    )

    try:
        result = simulate(
            ticker=body.ticker,
            initial_investment=body.initial_investment,
            horizon_years=body.horizon_years,
            monthly_contribution=body.monthly_contribution,
            annual_volatility=body.annual_volatility,
            capm_required_return=body.capm_required_return,
            gordon_fair_value=body.gordon_fair_value,
            current_price=body.current_price,
            risk_free_rate=body.risk_free_rate,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info(
        "simulate_complete ticker=%s base_final=%.0f sharpe=%.2f",
        body.ticker,
        result.scenarios[1].final_value,
        result.risk.sharpe_ratio,
    )

    return to_simulate_response(result)
