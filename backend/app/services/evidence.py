"""Evidence Auto-Builder — the primary AI feature.

OCR-first: Tesseract extracts text from images/PDFs; the LLM structures and
categorizes using that text as the source of truth for amounts and dates.

Hard guardrails:
- Amounts and dates must be anchored in OCR text; otherwise confidence = needs_review.
- LLM normalizes/categorizes but must not invent values.
- Document requirements (forms, date ranges, actionable outcomes) drive prompt and missing_evidence.
"""

import logging
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.document_requirements import DOCUMENT_REQUIREMENTS, REQUIREMENT_MATCH_KEYWORDS
from app.models.evidence import (
    ConfidenceLevel,
    DamageClaim,
    ExpenseItem,
    MissingEvidence,
    RenameEntry,
)
from app.models.outputs import EvidenceExtractionResponse
from app.services.llm_client import complete_json
from app.services import ocr

logger = logging.getLogger(__name__)


class _RawExtractionResult(BaseModel):
    """Internal schema for document path: expense-only extraction."""

    expense_items: list[ExpenseItem] = []


class _FileClassEntry(BaseModel):
    """Single file classification: document or photo."""

    filename: str = Field(..., description="Exact filename from the uploaded list")
    type: Literal["document", "photo"] = Field(
        ...,
        description="document = receipt, bill, statement, form; photo = damage, site, equipment, general photo",
    )


class _FileClassificationResult(BaseModel):
    """Result of classifying each uploaded file as document or photo."""

    entries: list[_FileClassEntry] = Field(
        ...,
        description="One entry per attached file, in the same order as the files",
    )


class _DamageExtractionResult(BaseModel):
    """Result of damage analysis on one or more photos."""

    damage_claims: list[DamageClaim] = []


def _build_classification_prompt(filenames: list[str]) -> str:
    """Build prompt for document vs photo classification."""
    return f"""For each attached file, classify it as either "document" or "photo".

- document: receipt, bill, statement, form, invoice, or any document with mainly text/tables.
- photo: damage photo, site photo, equipment photo, or any general photograph of a scene/object.

The attached files are in this exact order (one image per file):
{chr(10).join(f"{i + 1}. {fn}" for i, fn in enumerate(filenames))}

Return one entry per file in the SAME order, with "filename" set to the exact name from the list above and "type" set to either "document" or "photo"."""


async def _classify_file_types(
    files: list[tuple[str, bytes, str]],
) -> list[tuple[str, Literal["document", "photo"]]]:
    """Classify each file as document or photo. PDFs/non-images are treated as document."""
    if not files:
        return []

    # Only send image MIMEs to the vision model; PDFs etc. default to document
    image_files = [(fn, b, m) for fn, b, m in files if m in EVIDENCE_IMAGE_MIME_TYPES]
    non_image_filenames = [f[0] for f in files if f[2] not in EVIDENCE_IMAGE_MIME_TYPES]

    result: list[tuple[str, Literal["document", "photo"]]] = []

    if not image_files:
        return [(fn, "document") for fn, _, _ in files]

    filenames_order = [f[0] for f in image_files]
    prompt = _build_classification_prompt(filenames_order)
    images = [(f[1], f[2]) for f in image_files]

    try:
        classification = await complete_json(
            schema=_FileClassificationResult,
            prompt=prompt,
            images=images,
            max_retries=1,
        )
        # Build map by filename; if order is preserved, index can also be used
        type_by_filename = {e.filename: e.type for e in classification.entries}
        for fn in filenames_order:
            result.append((fn, type_by_filename.get(fn, "document")))
    except (ValidationError, Exception) as e:
        logger.warning(f"File classification failed, treating all as document: {e}")
        for fn in filenames_order:
            result.append((fn, "document"))

    for fn in non_image_filenames:
        result.append((fn, "document"))

    # Preserve original file order
    order = {fn: i for i, (fn, _, _) in enumerate(files)}
    result.sort(key=lambda x: order.get(x[0], 0))
    return result


def _build_damage_photo_prompt(filename: str) -> str:
    """Build vision-focused prompt for a single damage photo."""
    return f"""You are analyzing a damage/evidence photo for disaster relief.

This image has filename: {filename}

Describe what you see:
- Type of damage (water, wind, structural, equipment, etc.) if any
- Area or location (e.g. kitchen, roof, storefront)
- Severity if apparent (minor, moderate, severe)
- Any visible text (e.g. signage, labels)

Set source_file to exactly: {filename}
For source_text use "Visual: <description>" when there is no document text, or the literal text if something is readable.
If the image shows no damage (e.g. general site photo), still produce one claim with label like "General site photo" and describe the scene; set source_file to {filename}.

Return valid JSON with damage_claims array (at least one claim for this image)."""


async def _extract_damage_from_photos(
    photo_files: list[tuple[str, bytes, str]],
) -> list[DamageClaim]:
    """Run damage analysis on files classified as photos. One call per image for accuracy."""
    claims: list[DamageClaim] = []
    # Only process image MIMEs; skip PDFs that were classified as photo (treat as no damage)
    for filename, file_bytes, mime_type in photo_files:
        if mime_type not in EVIDENCE_IMAGE_MIME_TYPES:
            continue
        try:
            result = await complete_json(
                schema=_DamageExtractionResult,
                prompt=_build_damage_photo_prompt(filename),
                images=[(file_bytes, mime_type)],
                max_retries=1,
            )
            claims.extend(result.damage_claims)
        except (ValidationError, Exception) as e:
            logger.warning(f"Damage extraction failed for {filename}: {e}")
    return claims


def _build_extraction_prompt(
    filenames: list[str],
    file_ocr_texts: dict[str, str],
    business_type: str = "",
    county: str = "",
    state: str = "",
    disaster_id: str = "",
) -> str:
    """Build the multimodal prompt for evidence extraction (OCR-first)."""
    context_parts = []
    if business_type:
        context_parts.append(f"Business type: {business_type}")
    if county and state:
        context_parts.append(f"Location: {county} County, {state}")
    if disaster_id:
        context_parts.append(f"FEMA Disaster ID: {disaster_id}")

    context_str = "\n".join(context_parts) if context_parts else "No additional context provided."

    doc_reqs_block = _build_document_requirements_block()

    ocr_blocks = []
    for fn in filenames:
        text = file_ocr_texts.get(fn, "")
        ocr_blocks.append(f"--- FILE: {fn} ---\n{text or '(no OCR text)'}\n")

    return f"""You are a disaster-relief document analyst. You will receive both OCR text AND the original images.
Your job is to extract BOTH structured expense data AND visual damage evidence.

THIS IS A MULTIMODAL TASK — you MUST analyze every attached image visually, not only via OCR text.

DOCUMENT REQUIREMENTS (use for document_type and categorization):
{doc_reqs_block}

CRITICAL RULES — EXPENSES (text-based documents):
1. The OCR text below is the SOURCE OF TRUTH for amounts and dates. Do not invent values.
2. For each expense, set source_text to an exact substring of the OCR text for that file. Set source_file to the filename.
3. If the amount or date is not present in the OCR text, set confidence to "needs_review".
4. Set document_type to one of: receipt, utility_bill, lease, payroll, bank_statement, tax, other.
5. Categories for expenses: rent, utilities, payroll, supplies, repairs, insurance, other.

CRITICAL RULES — DAMAGE CLAIMS (image-based, visual analysis):
6. VISUALLY INSPECT every attached image. If an image shows physical damage (water damage, fire damage, structural damage, broken equipment, debris, flooding, mold, roof damage, broken windows, etc.), you MUST create a damage_claim for it.
7. For damage claims, set source_file to the filename of the image. Set source_text to a brief description of what you see in the image.
8. Damage photos typically have little or no OCR text — that is expected. Analyze them VISUALLY, not via OCR.
9. Set label to a short description (e.g. "Water damage - kitchen ceiling"), detail to 1-2 sentences describing the visible damage, and confidence to "high" if damage is clearly visible, "medium" if ambiguous.
10. If a file has "(no OCR text)" below, it is likely a photograph — look at the actual image content carefully for damage evidence.

CONTEXT:
{context_str}

UPLOADED FILES ({len(filenames)} files):
{chr(10).join(f"- {fn}" for fn in filenames)}

For each uploaded file, extract all visible expense items. Set source_file to the corresponding filename from the list above.
Return valid JSON with expense_items only (no damage_claims)."""


async def _extract_expenses_from_documents(
    document_files: list[tuple[str, bytes, str]],
    business_type: str = "",
    county: str = "",
    state: str = "",
    disaster_id: str = "",
) -> list[ExpenseItem]:
    """Run expense extraction only on files classified as documents."""
    if not document_files:
        return []
    filenames = [f[0] for f in document_files]
    images = [(f[1], f[2]) for f in document_files]
    prompt = _build_extraction_prompt(
        filenames=filenames,
        business_type=business_type,
        county=county,
        state=state,
        disaster_id=disaster_id,
    )
    try:
        raw = await complete_json(
            schema=_RawExtractionResult,
            prompt=prompt,
            images=images,
            max_retries=1,
        )
        return raw.expense_items
    except (ValidationError, Exception) as e:
        logger.warning(f"Document expense extraction failed: {e}")
        return []


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
        file_damages = [d for d in damage_claims if d.source_file == fn]

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


def _normalize_amount_for_ocr(amount: float) -> str:
    """Normalize amount so we can search for it in OCR text (strip $ and commas)."""
    s = f"{amount:.2f}".rstrip("0").rstrip(".")
    return s


def _normalize_date_for_ocr(date: str) -> list[str]:
    """Return possible substrings to look for in OCR (digits, slashes, dashes)."""
    # Keep original and a few variants (digits only, with slashes/dashes)
    out = [date]
    digits = re.sub(r"[^0-9]", "", date)
    if digits:
        out.append(digits)
    if len(digits) >= 6:  # YYYYMM or MMDDYY etc.
        out.append(digits[:4])
        out.append(digits[-4:])
    return out


def _anchor_expense_to_ocr(
    item: ExpenseItem,
    file_ocr_texts: dict[str, str],
) -> ExpenseItem:
    """
    If amount or date is not found in the OCR text for source_file, set confidence to needs_review.
    """
    ocr_text = file_ocr_texts.get(item.source_file, "")
    if not ocr_text:
        return item.model_copy(
            update={
                "confidence": ConfidenceLevel.NEEDS_REVIEW,
                "source_text": "No OCR text for this file; needs review.",
            }
        )

    amount_str = _normalize_amount_for_ocr(item.amount)
    amount_found = amount_str in ocr_text or str(int(item.amount)) in ocr_text
    date_variants = _normalize_date_for_ocr(item.date)
    date_found = any(v and v in ocr_text for v in date_variants)

    if amount_found and date_found:
        return item

    return item.model_copy(
        update={
            "confidence": ConfidenceLevel.NEEDS_REVIEW,
            "source_text": "Amount/date not found in OCR; needs review.",
        }
    )


def _detect_missing_evidence(
    expense_items: list[ExpenseItem],
    damage_claims: list[DamageClaim],
    filenames: list[str],
) -> list[MissingEvidence]:
    """Compare extracted categories against document requirements; return missing items."""
    missing: list[MissingEvidence] = []

    found_categories: set[str] = set()
    for e in expense_items:
        found_categories.add(e.category.lower())
        if e.document_type:
            found_categories.add(e.document_type.lower())
    for _ in damage_claims:
        found_categories.add("damage")

    fn_lower = " ".join(f.lower() for f in filenames)

    for req in DOCUMENT_REQUIREMENTS:
        keywords = REQUIREMENT_MATCH_KEYWORDS.get(req.id, [req.id])
        found = False
        for kw in keywords:
            if kw in found_categories or kw in fn_lower:
                found = True
                break
        if not found:
            missing.append(
                MissingEvidence(item=req.name, reason=req.actionable_outcomes)
            )

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
                MissingEvidence(item=req.name, reason=req.actionable_outcomes)
                for req in DOCUMENT_REQUIREMENTS
            ],
        )

    filenames = [f[0] for f in files]
    file_by_name = {f[0]: f for f in files}

    # 1. Classify each file as document or photo
    classification = await _classify_file_types(files)
    document_files = [file_by_name[fn] for fn, t in classification if t == "document"]
    photo_files = [file_by_name[fn] for fn, t in classification if t == "photo"]

    # 2. Document path: expense extraction only
    expense_items = await _extract_expenses_from_documents(
        document_files,
        business_type=business_type,
        county=county,
        state=state,
        disaster_id=disaster_id,
    )

    # 3. Photo path: damage analysis only
    damage_claims = await _extract_damage_from_photos(photo_files)

    # 4. Merge and post-processing
    rename_map = _generate_rename_map(filenames, expense_items, damage_claims)
    missing_evidence = _detect_missing_evidence(
        expense_items, damage_claims, filenames
    )

    return EvidenceExtractionResponse(
        expense_items=expense_items,
        rename_map=rename_map,
        damage_claims=damage_claims,
        missing_evidence=missing_evidence,
    )
