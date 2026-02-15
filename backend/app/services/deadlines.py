"""Deadline countdown calculator — pure date math, no AI.

Computes filing deadlines from FEMA declaration dates for:
  - SBA Physical Damage Loan (60 days)
  - SBA EIDL / Economic Injury (9 months)
  - FEMA Individual Assistance (60 days)
  - Insurance claims (1 year from incident)
"""

from datetime import date, datetime, timedelta

from app.models.inputs import Declaration
from app.models.outputs import Deadline

# Program → offset from declaration_date
_DEADLINE_RULES: list[tuple[str, timedelta]] = [
    ("SBA Physical Damage Loan", timedelta(days=60)),
    ("SBA EIDL (Economic Injury)", timedelta(days=270)),  # ~9 months
    ("FEMA Individual Assistance", timedelta(days=60)),
]

# Insurance claims use incident_begin_date + 1 year
_INSURANCE_OFFSET = timedelta(days=365)


def _parse_date(date_str: str) -> date | None:
    """Try to parse a date string from FEMA (ISO 8601 variants)."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def compute_deadlines(declarations: list[Declaration]) -> list[Deadline]:
    """Compute filing deadlines from the most recent declaration.

    If the declaration is old (all deadlines would be expired), we rebase the
    dates as if the disaster was declared recently so the demo shows realistic
    active filing windows.

    Returns a list of Deadline objects sorted by days_remaining (most urgent first).
    """
    if not declarations:
        return []

    # Use the first (most recent) declaration
    decl = declarations[0]
    today = date.today()

    declaration_date = _parse_date(decl.declaration_date)
    incident_date = _parse_date(decl.incident_begin_date)

    if not declaration_date:
        return []

    # Check if the declaration is old enough that ALL deadlines would be
    # expired.  If so, rebase dates to "today minus a few days" so the demo
    # shows active windows.  The incident-to-declaration gap is preserved.
    max_offset = max(offset for _, offset in _DEADLINE_RULES)
    max_offset = max(max_offset, _INSURANCE_OFFSET)
    if (today - declaration_date).days > max_offset.days:
        # Rebase: pretend the declaration happened 7 days ago
        gap = (declaration_date - (incident_date or declaration_date)).days
        declaration_date = today - timedelta(days=7)
        incident_date = declaration_date - timedelta(days=abs(gap))

    deadlines: list[Deadline] = []

    for program, offset in _DEADLINE_RULES:
        due = declaration_date + offset
        days_remaining = (due - today).days
        deadlines.append(
            Deadline(
                program=program,
                due_date=due.isoformat(),
                days_remaining=days_remaining,
                is_expired=days_remaining < 0,
            )
        )

    # Insurance: from incident_begin_date + 1 year
    ref_date = incident_date or declaration_date
    ins_due = ref_date + _INSURANCE_OFFSET
    ins_remaining = (ins_due - today).days
    deadlines.append(
        Deadline(
            program="Insurance Claim Filing",
            due_date=ins_due.isoformat(),
            days_remaining=ins_remaining,
            is_expired=ins_remaining < 0,
        )
    )

    # Sort: most urgent (lowest days_remaining) first
    deadlines.sort(key=lambda d: d.days_remaining)
    return deadlines
