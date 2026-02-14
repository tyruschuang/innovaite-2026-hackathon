"""Packet builder endpoint — generates and returns the submission ZIP."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.inputs import PacketBuildRequest
from app.services.packet import build_packet

router = APIRouter()


@router.post("/build")
async def packet_build(request: PacketBuildRequest):
    """
    Build a complete submission packet ZIP containing:
    - CoverSheet.pdf
    - DamageSummary.pdf
    - ExpenseLedger.csv + ExpenseLedger.pdf
    - EvidenceChecklist.pdf
    - Evidence/ folder with standardized filenames
    - Letters/ folder with ready-to-send PDFs

    Returns the ZIP file as a downloadable attachment.
    """
    try:
        zip_bytes, files_included = await build_packet(request)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build packet: {str(e)}",
        )

    # Determine filename
    business_name = request.user_info.business_name or "submission"
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in business_name)
    safe_name = safe_name.strip().replace(" ", "_")[:50] or "submission"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="ReliefBridge_{safe_name}_packet.zip"',
            "X-Files-Included": str(len(files_included)),
        },
    )
