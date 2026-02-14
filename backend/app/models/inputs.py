"""Request body Pydantic models for all API endpoints."""

from pydantic import BaseModel, Field
from app.models.evidence import ExpenseItem, DamageClaim, RenameEntry, MissingEvidence


class EligibilityRequest(BaseModel):
    county: str = Field(..., description="County name, e.g. 'Harris'")
    state: str = Field(
        ..., min_length=2, max_length=2, description="Two-letter state code, e.g. 'TX'"
    )


class RunwayRequest(BaseModel):
    business_type: str = Field(..., description="e.g. 'bakery', 'nonprofit', 'retail'")
    num_employees: int = Field(..., ge=0)
    monthly_rent: float = Field(..., ge=0)
    monthly_payroll: float = Field(..., ge=0)
    cash_on_hand: float = Field(..., ge=0)
    days_closed: int = Field(
        ..., ge=0, description="Days closed so far or estimated days until reopen"
    )


class EvidenceContext(BaseModel):
    """Context sent alongside file uploads for evidence extraction."""

    business_type: str = ""
    county: str = ""
    state: str = ""
    disaster_id: str = ""
    declaration_title: str = ""


class Declaration(BaseModel):
    disaster_number: str
    declaration_title: str
    incident_type: str
    ih_program: bool = False
    ia_program: bool = False
    pa_program: bool = False
    hm_program: bool = False
    declaration_date: str = ""
    incident_begin_date: str = ""
    incident_end_date: str = ""


class UserInfo(BaseModel):
    business_name: str = ""
    owner_name: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""


class PacketBuildRequest(BaseModel):
    """Full context needed to build the submission packet ZIP."""

    user_info: UserInfo
    eligibility: EligibilityRequest
    disaster_id: str = ""
    declarations: list[Declaration] = []
    runway: RunwayRequest
    runway_days: float = 0.0
    daily_burn: float = 0.0
    expense_items: list[ExpenseItem] = []
    damage_claims: list[DamageClaim] = []
    rename_map: list[RenameEntry] = []
    missing_evidence: list[MissingEvidence] = []
    # Base64-encoded evidence files for inclusion in the packet
    evidence_files: dict[str, str] = Field(
        default_factory=dict,
        description="Map of original_filename -> base64 encoded file content",
    )


class PlanGenerateRequest(BaseModel):
    """Context for generating the 30-minute action plan."""

    business_type: str
    num_employees: int = 0
    monthly_rent: float = 0.0
    monthly_payroll: float = 0.0
    cash_on_hand: float = 0.0
    days_closed: int = 0
    runway_days: float = 0.0
    daily_burn: float = 0.0
    disaster_id: str = ""
    has_landlord: bool = True
    has_utilities: bool = True
    has_lender: bool = True
    has_insurance: bool = True
