"""Evidence extraction endpoint — the primary AI feature.

Accepts multipart file uploads + JSON context, returns structured
expense items, rename map, damage claims, and missing evidence.
"""

import json

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from app.models.inputs import EvidenceContext
from app.models.outputs import EvidenceExtractionResponse
from app.services.evidence import extract_evidence

router = APIRouter()

# Supported MIME types for evidence uploads
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
}
MAX_FILES = 10
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB per file


@router.post("/extract", response_model=EvidenceExtractionResponse)
async def evidence_extract(
    files: list[UploadFile] = File(..., description="3-10 evidence files (images/PDFs)"),
    context: str = Form(
        default="{}",
        description='JSON string with business context, e.g. {"business_type":"bakery","county":"Harris","state":"TX"}',
    ),
):
    """
    Extract structured expense/damage data from uploaded evidence files
    using Gemini Vision AI.

    Upload 3-10 images or PDFs along with optional business context.
    Returns categorized expense items, standardized filenames,
    damage claim bullets, and missing evidence suggestions.
    """
    # Validate file count
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FILES} files allowed, got {len(files)}.",
        )

    # Parse context JSON
    try:
        ctx_data = json.loads(context)
        ctx = EvidenceContext(**ctx_data)
    except (json.JSONDecodeError, Exception) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid context JSON: {str(e)}",
        )

    # Read and validate files
    file_tuples: list[tuple[str, bytes, str]] = []
    for f in files:
        # Check MIME type
        content_type = f.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File '{f.filename}' has unsupported type '{content_type}'. "
                f"Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
            )

        # Read file bytes
        file_bytes = await f.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File '{f.filename}' exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB.",
            )

        file_tuples.append((f.filename or "unknown", file_bytes, content_type))

    # Run extraction
    try:
        result = await extract_evidence(
            files=file_tuples,
            business_type=ctx.business_type,
            county=ctx.county,
            state=ctx.state,
            disaster_id=ctx.disaster_id,
            declaration_title=ctx.declaration_title,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evidence extraction failed: {str(e)}",
        )

    return result
