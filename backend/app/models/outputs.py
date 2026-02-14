"""Response Pydantic models for all API endpoints."""

from pydantic import BaseModel, Field
from app.models.evidence import ExpenseItem, RenameEntry, DamageClaim, MissingEvidence
from app.models.actions import ChecklistItem
from app.models.inputs import Declaration


class EligibilityResponse(BaseModel):
    disaster_id: str = Field(..., description="Primary FEMA disaster declaration number")
    declarations: list[Declaration]
    programs: list[str] = Field(
        ...,
        description="Available program flags, e.g. ['Individual and Households', 'Public Assistance']",
    )
    county: str
    state: str


class DeferrableEstimate(BaseModel):
    category: str
    estimated_savings_days: float
    description: str


class RunwayResponse(BaseModel):
    runway_days: float = Field(..., description="Days of cash remaining at current burn")
    daily_burn: float = Field(..., description="Estimated daily cash outflow")
    deferrable_estimates: list[DeferrableEstimate] = Field(
        ..., description="Potential runway gains from forbearance/waivers"
    )


class EvidenceExtractionResponse(BaseModel):
    expense_items: list[ExpenseItem] = []
    rename_map: list[RenameEntry] = []
    damage_claims: list[DamageClaim] = []
    missing_evidence: list[MissingEvidence] = []


class PacketResponse(BaseModel):
    download_url: str = Field(
        ..., description="URL to download the generated ZIP packet"
    )
    files_included: list[str] = Field(
        ..., description="List of files in the ZIP"
    )


class PlanResponse(BaseModel):
    checklist: list[ChecklistItem]
