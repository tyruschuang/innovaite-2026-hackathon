"""Deterministic action sequencer — rules-based, no AI.

Builds a library of canonical Action objects, scores them, and returns
an ordered 3-6 step action plan optimized for maximum runway gain in
the first 48 hours.
"""

from app.models.actions import Action, ActionType, ChecklistItem


def _build_action_library(
    monthly_rent: float,
    monthly_payroll: float,
    daily_burn: float,
    runway_days: float,
    disaster_id: str,
    has_landlord: bool = True,
    has_utilities: bool = True,
    has_lender: bool = True,
    has_insurance: bool = True,
) -> list[Action]:
    """Build the full library of possible actions based on user situation."""
    actions: list[Action] = []

    # --- RUNWAY_NOW actions (letters) ---
    if has_landlord and monthly_rent > 0:
        rent_days = monthly_rent / daily_burn if daily_burn > 0 else 30
        actions.append(
            Action(
                id="landlord_forbearance",
                title="Send landlord forbearance request",
                type=ActionType.RUNWAY_NOW,
                time_to_execute_min=5,
                runway_gain_days=round(rent_days, 1),
                success_prob=0.7,
                requires=["landlord contact info"],
                produces=["landlord_forbearance_letter.pdf"],
                copy_text="Use the attached letter. Send via email and certified mail.",
            )
        )

    if has_utilities:
        utility_days = (monthly_rent * 0.15 / daily_burn) if daily_burn > 0 else 7
        actions.append(
            Action(
                id="utility_waiver",
                title="Request utility late-fee waiver",
                type=ActionType.RUNWAY_NOW,
                time_to_execute_min=5,
                runway_gain_days=round(utility_days, 1),
                success_prob=0.8,
                requires=["utility account number"],
                produces=["utility_waiver_letter.pdf"],
                copy_text="Call your utility provider and reference the disaster declaration. Follow up with the attached letter.",
            )
        )

    if has_lender:
        vendor_days = (monthly_rent + monthly_payroll) * 0.2 / daily_burn if daily_burn > 0 else 14
        actions.append(
            Action(
                id="lender_extension",
                title="Request lender/vendor net-terms extension",
                type=ActionType.RUNWAY_NOW,
                time_to_execute_min=10,
                runway_gain_days=round(vendor_days, 1),
                success_prob=0.6,
                requires=["lender/vendor contact info"],
                produces=["lender_extension_letter.pdf"],
                copy_text="Send the attached letter to each vendor/lender requesting 14-30 day payment extension.",
            )
        )

    # --- LONG_LATENCY actions ---
    if disaster_id:
        sba_days = (monthly_rent + monthly_payroll) * 3 / daily_burn if daily_burn > 0 else 90
        actions.append(
            Action(
                id="sba_application",
                title="Start SBA disaster loan application",
                type=ActionType.LONG_LATENCY,
                time_to_execute_min=15,
                runway_gain_days=round(sba_days, 1),
                success_prob=0.5,
                requires=["FEMA disaster ID", "business financials", "tax returns"],
                produces=["SBA application started"],
                copy_text=f"Go to https://disasterloanassistance.sba.gov/ and start your application. Reference disaster declaration {disaster_id}.",
            )
        )

        actions.append(
            Action(
                id="fema_registration",
                title="Register with FEMA for individual/business assistance",
                type=ActionType.LONG_LATENCY,
                time_to_execute_min=10,
                runway_gain_days=round(sba_days * 0.3, 1),
                success_prob=0.6,
                requires=["FEMA disaster ID"],
                produces=["FEMA registration confirmation"],
                copy_text=f"Register at https://www.disasterassistance.gov/ or call 1-800-621-3362. Reference disaster {disaster_id}.",
            )
        )

    if has_insurance:
        insurance_days = monthly_rent * 2 / daily_burn if daily_burn > 0 else 60
        actions.append(
            Action(
                id="insurance_claim",
                title="File insurance claim with documentation",
                type=ActionType.LONG_LATENCY,
                time_to_execute_min=15,
                runway_gain_days=round(insurance_days, 1),
                success_prob=0.6,
                requires=["insurance policy number", "damage photos", "expense receipts"],
                produces=["Insurance claim filed"],
                copy_text="Call your insurance agent. Have your policy number, damage photos, and the expense ledger from your packet ready.",
            )
        )

    # --- ADMIN actions ---
    actions.append(
        Action(
            id="document_damage",
            title="Document all damage with photos and notes",
            type=ActionType.ADMIN,
            time_to_execute_min=10,
            runway_gain_days=0,
            success_prob=1.0,
            requires=["camera/phone"],
            produces=["damage photos", "damage notes"],
            copy_text="Take photos of all damage. Note dates, descriptions, and estimated costs. Upload to ReliefBridge for processing.",
        )
    )

    actions.append(
        Action(
            id="gather_financials",
            title="Gather financial records (3 months statements)",
            type=ActionType.ADMIN,
            time_to_execute_min=10,
            runway_gain_days=0,
            success_prob=1.0,
            requires=["bank access", "accounting records"],
            produces=["financial statements"],
            copy_text="Download your last 3 months of bank statements and any P&L reports. These are needed for SBA and insurance applications.",
        )
    )

    return actions


def _score_action(action: Action) -> float:
    """Score an action: (runway_gain_days * success_prob) / time_to_execute_min."""
    if action.time_to_execute_min == 0:
        return float("inf")
    return (action.runway_gain_days * action.success_prob) / action.time_to_execute_min


def generate_plan(
    business_type: str,
    monthly_rent: float,
    monthly_payroll: float,
    daily_burn: float,
    runway_days: float,
    disaster_id: str,
    has_landlord: bool = True,
    has_utilities: bool = True,
    has_lender: bool = True,
    has_insurance: bool = True,
) -> list[ChecklistItem]:
    """
    Generate an ordered 3-6 step action plan.

    Hard constraints:
    - Always include 'Start SBA application' in top N (if disaster_id exists).
    - Always include at least 2 RUNWAY_NOW actions (letters).
    """
    actions = _build_action_library(
        monthly_rent=monthly_rent,
        monthly_payroll=monthly_payroll,
        daily_burn=daily_burn,
        runway_days=runway_days,
        disaster_id=disaster_id,
        has_landlord=has_landlord,
        has_utilities=has_utilities,
        has_lender=has_lender,
        has_insurance=has_insurance,
    )

    # Score and sort
    scored = sorted(actions, key=_score_action, reverse=True)

    # Apply hard constraints
    selected: list[Action] = []
    remaining = list(scored)

    # 1) Ensure at least 2 RUNWAY_NOW actions
    runway_now_count = 0
    for a in list(remaining):
        if a.type == ActionType.RUNWAY_NOW and runway_now_count < 2:
            selected.append(a)
            remaining.remove(a)
            runway_now_count += 1

    # 2) Ensure SBA application is included (if present)
    for a in list(remaining):
        if a.id == "sba_application":
            selected.append(a)
            remaining.remove(a)
            break

    # 3) Fill remaining slots (up to 6 total) by score
    for a in remaining:
        if len(selected) >= 6:
            break
        selected.append(a)

    # Re-sort selected by score for final ordering
    selected.sort(key=_score_action, reverse=True)

    # Build checklist items
    checklist: list[ChecklistItem] = []
    for i, action in enumerate(selected, start=1):
        why = _generate_why(action, daily_burn)
        checklist.append(
            ChecklistItem(
                step_number=i,
                title=action.title,
                why=why,
                time_estimate_min=action.time_to_execute_min,
                copy_text=action.copy_text,
                attached_file=action.produces[0] if action.produces else None,
            )
        )

    return checklist


def _generate_why(action: Action, daily_burn: float) -> str:
    """Generate a human-readable 'why' string for a checklist item."""
    if action.runway_gain_days > 0:
        dollar_value = action.runway_gain_days * daily_burn
        return (
            f"Buys ~{action.runway_gain_days:.0f} days of runway "
            f"(~${dollar_value:,.0f}). "
            f"Success rate: ~{action.success_prob * 100:.0f}%."
        )
    return f"Essential preparation step. ~{action.time_to_execute_min} min to complete."
