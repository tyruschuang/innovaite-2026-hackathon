"""Runway calculator endpoint — deterministic financial math."""

from fastapi import APIRouter

from app.models.inputs import RunwayRequest
from app.models.outputs import RunwayResponse
from app.services.runway import calculate_runway

router = APIRouter()


@router.post("/calc", response_model=RunwayResponse)
async def runway_calc(request: RunwayRequest):
    """
    Calculate cash runway days and deferrable savings estimates
    based on the business's financial situation.
    """
    result = calculate_runway(
        monthly_rent=request.monthly_rent,
        monthly_payroll=request.monthly_payroll,
        cash_on_hand=request.cash_on_hand,
        days_closed=request.days_closed,
        num_employees=request.num_employees,
    )
    return RunwayResponse(**result)
