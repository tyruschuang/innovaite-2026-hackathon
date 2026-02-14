"""Eligibility lookup endpoint — queries OpenFEMA for disaster declarations."""

from fastapi import APIRouter, HTTPException

from app.models.inputs import EligibilityRequest
from app.models.outputs import EligibilityResponse
from app.services.eligibility import lookup_eligibility

router = APIRouter()


@router.post("/lookup", response_model=EligibilityResponse)
async def eligibility_lookup(request: EligibilityRequest):
    """
    Look up FEMA disaster declarations for a given county and state.
    Returns matching declarations and available relief programs.
    """
    try:
        result = await lookup_eligibility(
            county=request.county, state=request.state
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to query OpenFEMA API: {str(e)}",
        )

    if not result["declarations"]:
        raise HTTPException(
            status_code=404,
            detail=f"No disaster declarations found for {request.county} County, {request.state}. "
            "Check the county name spelling and try again.",
        )

    return EligibilityResponse(**result)
