"""Deterministic runway calculator — pure math, no AI."""

from app.models.outputs import DeferrableEstimate


def calculate_runway(
    monthly_rent: float,
    monthly_payroll: float,
    cash_on_hand: float,
    days_closed: int,
    num_employees: int,
) -> dict:
    """
    Calculate how many days of cash runway the business has,
    plus heuristic estimates for deferrable savings.

    Returns dict with runway_days, daily_burn, deferrable_estimates.
    """
    # Daily burn rate
    monthly_fixed = monthly_rent + monthly_payroll
    daily_burn = monthly_fixed / 30.0 if monthly_fixed > 0 else 0.0

    # Already-spent burn from days closed
    already_burned = daily_burn * days_closed
    remaining_cash = max(cash_on_hand - already_burned, 0.0)

    # Runway in days
    runway_days = remaining_cash / daily_burn if daily_burn > 0 else float("inf")

    # Deferrable estimates (heuristic savings from letters/actions)
    deferrables: list[DeferrableEstimate] = []

    if monthly_rent > 0:
        rent_days = monthly_rent / daily_burn if daily_burn > 0 else 0
        deferrables.append(
            DeferrableEstimate(
                category="Rent Forbearance",
                estimated_savings_days=round(rent_days, 1),
                description=f"Requesting 30-day rent deferral could free ~${monthly_rent:,.0f}, buying ~{rent_days:.0f} days of runway.",
            )
        )

    if monthly_payroll > 0:
        # Utility waiver is a smaller amount — estimate ~10% of payroll equivalent
        utility_estimate = monthly_rent * 0.15 if monthly_rent > 0 else 200.0
        utility_days = utility_estimate / daily_burn if daily_burn > 0 else 0
        deferrables.append(
            DeferrableEstimate(
                category="Utility Late-Fee Waiver",
                estimated_savings_days=round(utility_days, 1),
                description=f"Waiving utility late fees saves ~${utility_estimate:,.0f}, buying ~{utility_days:.0f} days.",
            )
        )

    # Vendor/lender extension
    vendor_estimate = monthly_fixed * 0.2
    vendor_days = vendor_estimate / daily_burn if daily_burn > 0 else 0
    deferrables.append(
        DeferrableEstimate(
            category="Vendor/Lender Net-Terms Extension",
            estimated_savings_days=round(vendor_days, 1),
            description=f"Extending vendor payment terms by 14-30 days defers ~${vendor_estimate:,.0f}, buying ~{vendor_days:.0f} days.",
        )
    )

    # SBA loan (long latency but large impact)
    sba_estimate = monthly_fixed * 3  # ~3 months operating expenses
    sba_days = sba_estimate / daily_burn if daily_burn > 0 else 0
    deferrables.append(
        DeferrableEstimate(
            category="SBA Disaster Loan (long latency)",
            estimated_savings_days=round(sba_days, 1),
            description=f"SBA disaster loans typically cover ~${sba_estimate:,.0f} in operating expenses (~{sba_days:.0f} days). Application takes 2-3 weeks to process.",
        )
    )

    return {
        "runway_days": round(runway_days, 1),
        "daily_burn": round(daily_burn, 2),
        "deferrable_estimates": deferrables,
    }
