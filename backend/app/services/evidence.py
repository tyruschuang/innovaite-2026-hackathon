"""Evidence Auto-Builder — the primary AI feature.

Uses Google Gemini Vision to extract structured expense/damage data
from uploaded images and PDFs in a single multimodal pass.

Hard guardrails:
- Every extracted amount/date must reference visible source text.
- LLM normalizes/categorizes but must not invent values.
- Strict Pydantic validation with retry-once semantics.
"""

import logging
import re
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.models.evidence import (
    ConfidenceLevel,
    DamageClaim,
    ExpenseItem,
    MissingEvidence,
    RenameEntry,
)
from app.models.outputs import EvidenceExtractionResponse
from app.services.llm_client import complete_json

logger = logging.getLogger(__name__)

# Evidence categories we expect for a complete submission
EXPECTED_EVIDENCE_CATEGORIES = [
    ("Lease agreement or rent statement", "Required for rent forbearance and SBA loan application"),
    ("Insurance policy or declaration page", "Required for insurance claim and SBA processing"),
    ("Payroll records (last 3 months)", "Required for SBA disaster loan application"),
    ("Utility bills (recent)", "Needed for utility waiver request and expense documentation"),
    ("Damage photographs", "Visual evidence for insurance and FEMA claims"),
    ("Bank statements (last 3 months)", "Required for SBA loan and financial verification"),
    ("Tax returns (most recent year)", "Required for SBA disaster loan application"),
    ("Business license or registration", "Proof of business operation for relief applications"),
]


class _RawExtractionResult(BaseModel):
    """Internal schema sent to Gemini for structured extraction."""

    expense_items: list[ExpenseItem] = []
    damage_claims: list[DamageClaim] = []


def _build_extraction_prompt(
    filenames: list[str],
    business_type: str = "",
    county: str = "",
    state: str = "",
    disaster_id: str = "",
) -> str:
    """Build the multimodal prompt for evidence extraction."""
    context_parts = []
    if business_type:
        context_parts.append(f"Business type: {business_type}")
    if county and state:
        context_parts.append(f"Location: {county} County, {state}")
    if disaster_id:
        context_parts.append(f"FEMA Disaster ID: {disaster_id}")

    context_str = "\n".join(context_parts) if context_parts else "No additional context provided."

    return f"""You are a disaster-relief document analyst. Extract structured expense and damage data from the uploaded images/documents.

CRITICAL RULES:
1. Every amount and date you extract MUST reference visible text in the image. Set source_text to the LITERAL text snippet you read.
2. NEVER invent or estimate values — only extract what is clearly visible.
3. If text is unclear or partially visible, set confidence to "needs_review".
4. For each expense item, identify: vendor name, date, dollar amount, and category.
5. For damage claims, describe what damage is visible in photos with specific details.
6. Categories for expenses: rent, utilities, payroll, supplies, repairs, insurance, other.

CONTEXT:
{context_str}

UPLOADED FILES ({len(filenames)} files):
{chr(10).join(f"- {fn}" for fn in filenames)}

For each uploaded file, extract all visible expense items and damage evidence.
Set source_file to the corresponding filename from the list above.
Return valid JSON matching the schema exactly."""


def _generate_rename_map(
    filenames: list[str],
    expense_items: list[ExpenseItem],
    damage_claims: list[DamageClaim],
) -> list[RenameEntry]:
    """Generate standardized filenames from extraction results."""
    rename_map: list[RenameEntry] = []

    for fn in filenames:
        # Find expense items associated with this file
        file_expenses = [e for e in expense_items if e.source_file == fn]
        file_damages = [d for d in damage_claims if fn in (d.source_text or "")]

        ext = Path(fn).suffix.lower() or ".jpg"
        base = Path(fn).stem

        if file_expenses:
            # Use the first expense to generate the name
            e = file_expenses[0]
            vendor_clean = re.sub(r"[^a-zA-Z0-9]", "_", e.vendor.lower())[:20]
            date_clean = e.date.replace("/", "-").replace(" ", "")[:10]
            recommended = f"receipt_{vendor_clean}_{date_clean}_{e.amount:.2f}{ext}"
            confidence = e.confidence
        elif file_damages:
            d = file_damages[0]
            label_clean = re.sub(r"[^a-zA-Z0-9]", "_", d.label.lower())[:30]
            recommended = f"damage_{label_clean}{ext}"
            confidence = d.confidence
        else:
            recommended = f"evidence_{base}{ext}"
            confidence = ConfidenceLevel.NEEDS_REVIEW

        rename_map.append(
            RenameEntry(
                original_filename=fn,
                recommended_filename=recommended,
                confidence=confidence,
            )
        )

    return rename_map


def _detect_missing_evidence(
    expense_items: list[ExpenseItem],
    damage_claims: list[DamageClaim],
    filenames: list[str],
) -> list[MissingEvidence]:
    """Compare extracted categories against expected evidence checklist."""
    missing: list[MissingEvidence] = []

    # Track what categories we found
    found_categories: set[str] = set()
    for e in expense_items:
        found_categories.add(e.category.lower())
    for d in damage_claims:
        found_categories.add("damage")

    # Check for common filename patterns
    fn_lower = " ".join(f.lower() for f in filenames)

    category_mapping = {
        "Lease agreement or rent statement": ["rent", "lease"],
        "Insurance policy or declaration page": ["insurance"],
        "Payroll records (last 3 months)": ["payroll"],
        "Utility bills (recent)": ["utilities", "utility"],
        "Damage photographs": ["damage"],
        "Bank statements (last 3 months)": ["bank", "statement"],
        "Tax returns (most recent year)": ["tax"],
        "Business license or registration": ["license", "registration"],
    }

    for item_name, reason in EXPECTED_EVIDENCE_CATEGORIES:
        keywords = category_mapping.get(item_name, [])
        found = False
        for kw in keywords:
            if kw in found_categories or kw in fn_lower:
                found = True
                break
        if not found:
            missing.append(MissingEvidence(item=item_name, reason=reason))

    return missing


async def extract_evidence(
    files: list[tuple[str, bytes, str]],
    business_type: str = "",
    county: str = "",
    state: str = "",
    disaster_id: str = "",
    declaration_title: str = "",
) -> EvidenceExtractionResponse:
    """
    Main entry point for evidence extraction.

    Args:
        files: List of (filename, file_bytes, mime_type) tuples.
        business_type: Type of business.
        county: County name.
        state: State code.
        disaster_id: FEMA disaster declaration ID.
        declaration_title: Title of the disaster declaration.

    Returns:
        EvidenceExtractionResponse with extracted data.
    """
    if not files:
        return EvidenceExtractionResponse(
            expense_items=[],
            rename_map=[],
            damage_claims=[],
            missing_evidence=[
                MissingEvidence(item=name, reason=reason)
                for name, reason in EXPECTED_EVIDENCE_CATEGORIES
            ],
        )

    filenames = [f[0] for f in files]
    images = [(f[1], f[2]) for f in files]

    # Build prompt
    prompt = _build_extraction_prompt(
        filenames=filenames,
        business_type=business_type,
        county=county,
        state=state,
        disaster_id=disaster_id,
    )

    # Call Gemini Vision for extraction
    try:
        raw_result = await complete_json(
            schema=_RawExtractionResult,
            prompt=prompt,
            images=images,
            max_retries=1,
        )
        expense_items = raw_result.expense_items
        damage_claims = raw_result.damage_claims
    except (ValidationError, Exception) as e:
        logger.error(f"Evidence extraction failed: {e}")
        # Degrade gracefully: return empty extraction with all missing
        expense_items = []
        damage_claims = []

    # Post-processing
    rename_map = _generate_rename_map(filenames, expense_items, damage_claims)
    missing_evidence = _detect_missing_evidence(expense_items, damage_claims, filenames)

    return EvidenceExtractionResponse(
        expense_items=expense_items,
        rename_map=rename_map,
        damage_claims=damage_claims,
        missing_evidence=missing_evidence,
    )
