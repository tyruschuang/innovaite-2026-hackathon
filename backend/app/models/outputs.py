"""Response Pydantic models for all API endpoints."""

from enum import Enum

from pydantic import BaseModel, Field
from app.models.evidence import ExpenseItem, RenameEntry, DamageClaim, MissingEvidence
from app.models.actions import ChecklistItem
from app.models.inputs import Declaration


class UrgencyLevel(str, Enum):
    CRITICAL = "critical"
    URGENT = "urgent"
    MODERATE = "moderate"


class InsightUrgency(str, Enum):
    CRITICAL = "critical"
    ACTION_NEEDED = "action_needed"
    INFORMATIONAL = "informational"


class KeyInsight(BaseModel):
    """A single AI-generated insight surfaced on the results page."""

    title: str = Field(..., description="Short headline, e.g. 'Payroll deadline in 8 days'")
    detail: str = Field(..., description="1-2 sentence explanation")
    urgency: InsightUrgency = Field(
        default=InsightUrgency.INFORMATIONAL,
        description="Urgency tag for color-coding in the UI",
    )


# ---------------------------------------------------------------------------
# Deadline Countdowns
# ---------------------------------------------------------------------------

class Deadline(BaseModel):
    """A single filing/application deadline computed from declaration date."""

    program: str = Field(..., description="Program name, e.g. 'SBA Physical Damage Loan'")
    due_date: str = Field(..., description="ISO date string YYYY-MM-DD")
    days_remaining: int = Field(..., description="Days until deadline (negative = expired)")
    is_expired: bool = Field(False, description="True if the deadline has passed")


# ---------------------------------------------------------------------------
# SBA / FEMA Historical Benchmarks
# ---------------------------------------------------------------------------

class DisasterBenchmark(BaseModel):
    """Aggregate FEMA stats for the matched disaster — from FemaWebDisasterSummaries."""

    disaster_number: str = ""
    disaster_title: str = ""
    total_amount_ihp_approved: float | None = Field(
        None, description="Total Individual & Households Program $ approved"
    )
    total_amount_ha_approved: float | None = Field(
        None, description="Total Housing Assistance $ approved"
    )
    total_amount_ona_approved: float | None = Field(
        None, description="Total Other Needs Assistance $ approved"
    )
    total_applicants: int | None = Field(
        None, description="Total number of applicants"
    )
    total_approved_ihp: int | None = Field(
        None, description="Total number of IHP approvals"
    )
    state: str = ""
    declaration_date: str = ""
    incident_type: str = ""
    available: bool = Field(True, description="False if the API returned no data")


# ---------------------------------------------------------------------------
# Packet Completeness Score
# ---------------------------------------------------------------------------

class CompletenessItem(BaseModel):
    """A single item in the completeness checklist."""

    item: str = Field(..., description="Document/evidence type name")
    present: bool = Field(False, description="Whether the item is present in the packet")
    weight: int = Field(1, description="Relative importance weight (1-3)")
    reason: str = Field("", description="Why it's missing, if missing")


class CompletenessScore(BaseModel):
    """Overall completeness assessment of the submission packet."""

    score: int = Field(..., description="0-100 completeness percentage")
    items: list[CompletenessItem] = Field(default_factory=list)
    present_count: int = 0
    missing_count: int = 0
    summary: str = Field("", description="One-line summary of completeness")


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


class PacketFileEntry(BaseModel):
    path: str = Field(..., description="Path of the file in the ZIP")
    description: str = Field(..., description="Short description for UI display")


class ResultsSummary(BaseModel):
    damage_claim_count: int = Field(..., description="Number of damage claims in the packet")
    expense_count: int = Field(..., description="Number of expense items in the packet")
    letter_count: int = Field(..., description="Number of letter documents (e.g. 3 letter types x 2 formats)")
    runway_days: float = Field(..., description="Estimated runway in days")
    business_name: str = Field(..., description="Business name from the packet")
    disaster_id: str = Field(..., description="FEMA disaster declaration ID")
    one_line_summary: str = Field(
        ...,
        description="Template-based one-line summary for the results page",
    )
    key_insights: list[KeyInsight] = Field(
        default_factory=list,
        description="3-5 AI-generated headline insights for the results page",
    )
    urgency_level: str = Field(
        default="moderate",
        description="Overall urgency classification: critical / urgent / moderate",
    )
    deadlines: list[Deadline] = Field(
        default_factory=list,
        description="Filing deadline countdowns computed from declaration date",
    )
    benchmark: DisasterBenchmark | None = Field(
        None, description="Historical FEMA aggregate data for this disaster"
    )
    completeness: CompletenessScore | None = Field(
        None, description="Packet completeness assessment"
    )


class PacketBuildResponse(BaseModel):
    zip_base64: str = Field(..., description="ZIP file content as base64")
    filename: str = Field(..., description="Suggested download filename")
    results_summary: ResultsSummary
    files_included: list[PacketFileEntry]


class PacketResponse(BaseModel):
    download_url: str = Field(
        ..., description="URL to download the generated ZIP packet"
    )
    files_included: list[str] = Field(
        ..., description="List of files in the ZIP"
    )


class PlanResponse(BaseModel):
    checklist: list[ChecklistItem]
