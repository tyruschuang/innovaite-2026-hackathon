"""OpenFEMA Disaster Declarations lookup service."""

import httpx
from app.config import get_settings
from app.models.inputs import Declaration


async def lookup_eligibility(county: str, state: str) -> dict:
    """
    Query the OpenFEMA Disaster Declarations Summaries API to find
    matching disaster declarations for a given county and state.

    Returns dict with disaster_id, declarations list, programs list.
    """
    settings = get_settings()
    base_url = f"{settings.fema_api_base}/DisasterDeclarationsSummaries"

    # Build OData-style filter
    # designatedArea contains the county name (e.g. "Harris (County)")
    # state is the 2-letter state abbreviation
    filter_str = f"state eq '{state.upper()}' and designatedArea eq '{county.title()} (County)'"

    params = {
        "$filter": filter_str,
        "$orderby": "declarationDate desc",
        "$top": 20,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

    summaries = data.get("DisasterDeclarationsSummaries", [])

    if not summaries:
        # Try without "(County)" suffix as some entries differ
        filter_str = f"state eq '{state.upper()}' and contains(designatedArea, '{county.title()}')"
        params["$filter"] = filter_str

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

        summaries = data.get("DisasterDeclarationsSummaries", [])

    if not summaries:
        return {
            "disaster_id": "",
            "declarations": [],
            "programs": [],
            "county": county,
            "state": state,
        }

    # Build declarations list
    declarations: list[Declaration] = []
    programs_set: set[str] = set()
    primary_disaster_id = ""

    for s in summaries:
        disaster_num = str(s.get("disasterNumber", ""))
        if not primary_disaster_id:
            primary_disaster_id = disaster_num

        decl = Declaration(
            disaster_number=disaster_num,
            declaration_title=s.get("declarationTitle") or "",
            incident_type=s.get("incidentType") or "",
            ih_program=bool(s.get("ihProgramDeclared")),
            ia_program=bool(s.get("iaProgramDeclared")),
            pa_program=bool(s.get("paProgramDeclared")),
            hm_program=bool(s.get("hmProgramDeclared")),
            declaration_date=s.get("declarationDate") or "",
            incident_begin_date=s.get("incidentBeginDate") or "",
            incident_end_date=s.get("incidentEndDate") or "",
        )
        declarations.append(decl)

        # Collect program flags
        if s.get("ihProgramDeclared"):
            programs_set.add("Individual and Households")
        if s.get("iaProgramDeclared"):
            programs_set.add("Individual Assistance")
        if s.get("paProgramDeclared"):
            programs_set.add("Public Assistance")
        if s.get("hmProgramDeclared"):
            programs_set.add("Hazard Mitigation")

    return {
        "disaster_id": primary_disaster_id,
        "declarations": declarations,
        "programs": sorted(programs_set),
        "county": county,
        "state": state,
    }
