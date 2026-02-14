"""Plan generation endpoint — wraps the deterministic sequencer."""

from fastapi import APIRouter

from app.models.inputs import PlanGenerateRequest
from app.models.outputs import PlanResponse
from app.services.sequencer import generate_plan

router = APIRouter()


@router.post("/generate", response_model=PlanResponse)
async def plan_generate(request: PlanGenerateRequest):
    """
    Generate a 30-minute action plan with 3-6 ordered steps,
    optimized for maximum runway gain in the first 48 hours.
    """
    checklist = generate_plan(
        business_type=request.business_type,
        monthly_rent=request.monthly_rent,
        monthly_payroll=request.monthly_payroll,
        daily_burn=request.daily_burn,
        runway_days=request.runway_days,
        disaster_id=request.disaster_id,
        has_landlord=request.has_landlord,
        has_utilities=request.has_utilities,
        has_lender=request.has_lender,
        has_insurance=request.has_insurance,
    )
    return PlanResponse(checklist=checklist)
