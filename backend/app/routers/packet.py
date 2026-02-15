"""Packet builder endpoint — generates and returns the submission ZIP as JSON with base64 ZIP and results summary."""

import base64

from fastapi import APIRouter, HTTPException

from app.models.inputs import PacketBuildRequest
from app.models.outputs import PacketBuildResponse
from app.services.packet import build_packet

router = APIRouter()


def _safe_filename(business_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in (business_name or "submission"))
    safe = safe.strip().replace(" ", "_")[:50] or "submission"
    return f"Remedy_{safe}_packet.zip"


@router.post("/build", response_model=PacketBuildResponse)
async def packet_build(request: PacketBuildRequest):
    """
    Build a complete submission packet ZIP containing:
    - CoverSheet.pdf
    - DamageSummary.pdf
    - ExpenseLedger.csv + ExpenseLedger.pdf
    - EvidenceChecklist.pdf
    - Evidence/ folder with standardized filenames
    - Letters/ folder with ready-to-send PDFs

    Returns JSON with zip_base64, filename, results_summary, files_included.
    """
    try:
        zip_bytes, files_included, results_summary = await build_packet(request)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build packet: {str(e)}",
        )

    filename = _safe_filename(request.user_info.business_name)
    zip_base64 = base64.standard_b64encode(zip_bytes).decode("ascii")
    return PacketBuildResponse(
        zip_base64=zip_base64,
        filename=filename,
        results_summary=results_summary,
        files_included=files_included,
    )
