"""Historical disaster benchmarking via OpenFEMA FemaWebDisasterSummaries.

Fetches aggregate FEMA stats (total $ approved, total applicants) for
the matched disaster number, giving users real context on how others fared.
"""

import logging

import httpx

from app.config import get_settings
from app.models.outputs import DisasterBenchmark

logger = logging.getLogger(__name__)

# The FemaWebDisasterSummaries endpoint (v1)
_ENDPOINT = "https://www.fema.gov/api/open/v1/FemaWebDisasterSummaries"


async def fetch_disaster_benchmarks(disaster_number: str) -> DisasterBenchmark:
    """Query OpenFEMA for aggregate disaster stats.

    Returns a DisasterBenchmark — with available=False if the API
    returned no matching data.
    """
    if not disaster_number:
        return DisasterBenchmark(available=False)

    params = {
        "$filter": f"disasterNumber eq {disaster_number}",
        "$top": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json()

        summaries = data.get("FemaWebDisasterSummaries", [])
        if not summaries:
            logger.info("No FemaWebDisasterSummaries for disaster %s", disaster_number)
            return DisasterBenchmark(disaster_number=disaster_number, available=False)

        s = summaries[0]

        return DisasterBenchmark(
            disaster_number=str(s.get("disasterNumber", disaster_number)),
            disaster_title=s.get("declarationTitle") or "",
            total_amount_ihp_approved=_safe_float(s.get("totalAmountIhpApproved")),
            total_amount_ha_approved=_safe_float(s.get("totalAmountHaApproved")),
            total_amount_ona_approved=_safe_float(s.get("totalAmountOnaApproved")),
            total_applicants=_safe_int(s.get("totalNumberIaApproved")),
            total_approved_ihp=_safe_int(s.get("totalApprovedIhpAmount")),
            state=s.get("state") or "",
            declaration_date=s.get("declarationDate") or "",
            incident_type=s.get("incidentType") or "",
            available=True,
        )

    except Exception as e:
        logger.warning("Failed to fetch disaster benchmarks for %s: %s", disaster_number, e)
        return DisasterBenchmark(disaster_number=disaster_number, available=False)


def _safe_float(val) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """Safely convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
