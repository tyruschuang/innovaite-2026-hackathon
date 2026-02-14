"""Letter generation service — template-first with optional AI hardship paragraph.

Uses owned Jinja2 templates with deterministic variable substitution.
Optional AI paragraph is validated by a "letter lint" that blocks
dangerous phrases. Falls back to fully-templated letter on lint failure.
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.services.llm_client import complete_text

logger = logging.getLogger(__name__)

# Set up Jinja2 environment
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "letters"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
)

# Forbidden phrases that trigger lint failure
FORBIDDEN_PHRASES = [
    r"\bguaranteed\b",
    r"\bentitled\b",
    r"\byou must\b",
    r"\byou are required\b",
    r"\blegal action\b",
    r"\bwe will sue\b",
    r"\bwe demand\b",
    r"\bfailure to comply\b",
]

# Compiled regex for lint
LINT_PATTERN = re.compile("|".join(FORBIDDEN_PHRASES), re.IGNORECASE)


def _lint_letter(text: str) -> tuple[bool, list[str]]:
    """
    Scan letter text for forbidden phrases.

    Returns:
        (passes_lint, list_of_violations)
    """
    violations = LINT_PATTERN.findall(text)
    return len(violations) == 0, violations


async def _generate_hardship_paragraph(
    business_name: str,
    business_type: str,
    disaster_title: str,
    days_closed: int,
    num_employees: int,
    monthly_rent: float,
    monthly_payroll: float,
) -> str:
    """Use AI to generate a 2-3 sentence hardship paragraph grounded in user data."""
    prompt = f"""Write a 2-3 sentence hardship paragraph for a disaster relief letter.
The paragraph should be professional, factual, and empathetic.

STRICT RULES:
- Only reference the facts provided below. Do not invent details.
- Do not use the words "guaranteed", "entitled", or make legal claims.
- Keep the tone respectful and professional.

FACTS:
- Business: {business_name} ({business_type})
- Disaster: {disaster_title}
- Days closed: {days_closed}
- Number of employees: {num_employees}
- Monthly rent: ${monthly_rent:,.0f}
- Monthly payroll: ${monthly_payroll:,.0f}

Write only the paragraph, no salutation or closing."""

    try:
        paragraph = await complete_text(prompt, max_tokens=200, temperature=0.3)
        # Lint the AI-generated paragraph
        passes, violations = _lint_letter(paragraph)
        if not passes:
            logger.warning(f"AI hardship paragraph failed lint: {violations}")
            return _fallback_hardship_paragraph(
                business_name, days_closed, num_employees
            )
        return paragraph.strip()
    except Exception as e:
        logger.warning(f"AI hardship paragraph generation failed: {e}")
        return _fallback_hardship_paragraph(
            business_name, days_closed, num_employees
        )


def _fallback_hardship_paragraph(
    business_name: str, days_closed: int, num_employees: int
) -> str:
    """Deterministic fallback paragraph when AI fails or lint fails."""
    return (
        f"As a result of this disaster, {business_name} has been unable to operate "
        f"for {days_closed} days, directly impacting our {num_employees} employees "
        f"and their families. We are working diligently to resume operations and "
        f"are pursuing all available disaster relief resources."
    )


async def render_letter(
    template_name: str,
    variables: dict,
    use_ai_paragraph: bool = True,
) -> str:
    """
    Render a letter from a template with the given variables.

    Args:
        template_name: One of 'landlord_forbearance', 'utility_waiver', 'lender_extension'.
        variables: Dict of template variables.
        use_ai_paragraph: Whether to generate an AI hardship paragraph.

    Returns:
        Rendered letter text.
    """
    # Generate hardship paragraph
    if use_ai_paragraph:
        hardship = await _generate_hardship_paragraph(
            business_name=variables.get("business_name", "Our business"),
            business_type=variables.get("business_type", "small business"),
            disaster_title=variables.get("declaration_title", "the recent disaster"),
            days_closed=variables.get("days_closed", 0),
            num_employees=variables.get("num_employees", 0),
            monthly_rent=variables.get("monthly_rent", 0),
            monthly_payroll=variables.get("monthly_payroll", 0),
        )
    else:
        hardship = _fallback_hardship_paragraph(
            variables.get("business_name", "Our business"),
            variables.get("days_closed", 0),
            variables.get("num_employees", 0),
        )

    # Set defaults for missing variables
    template_vars = {
        "date": datetime.now().strftime("%B %d, %Y"),
        "start_date": datetime.now().strftime("%B %d, %Y"),
        "days_requested": 30,
        "landlord_name": "Property Manager",
        "landlord_address": "",
        "utility_company": "Utility Provider",
        "utility_address": "",
        "lender_name": "Accounts Receivable",
        "lender_address": "",
        "hardship_paragraph": hardship,
        **variables,
    }

    # Render template
    template_file = f"{template_name}.txt"
    template = jinja_env.get_template(template_file)
    rendered = template.render(**template_vars)

    # Final lint check on the entire letter
    passes, violations = _lint_letter(rendered)
    if not passes:
        logger.warning(
            f"Final letter lint failed for {template_name}: {violations}. "
            "Falling back to template without AI paragraph."
        )
        # Re-render with fallback paragraph
        template_vars["hardship_paragraph"] = _fallback_hardship_paragraph(
            template_vars.get("business_name", "Our business"),
            template_vars.get("days_closed", 0),
            template_vars.get("num_employees", 0),
        )
        rendered = template.render(**template_vars)

    return rendered


async def render_all_letters(variables: dict) -> dict[str, str]:
    """
    Render all three letter templates.

    Returns:
        Dict mapping letter name to rendered text.
    """
    letter_types = ["landlord_forbearance", "utility_waiver", "lender_extension"]
    results: dict[str, str] = {}

    for lt in letter_types:
        try:
            text = await render_letter(lt, variables)
            results[lt] = text
        except Exception as e:
            logger.error(f"Failed to render letter {lt}: {e}")
            results[lt] = f"[Letter generation failed: {str(e)}]"

    return results
