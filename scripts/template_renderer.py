"""
Template Renderer - Jinja2-based template loading and rendering.

Provides a single source of truth for all markdown templates.
Templates live in /templates/ directory and use Jinja2 syntax.
"""

import os
from jinja2 import Environment, FileSystemLoader

# Template directory relative to project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")

# Initialize Jinja2 environment
_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(template_name: str, **context) -> str:
    """
    Render a template with the given context variables.

    Args:
        template_name: Name of template file (e.g., "daily_log.md")
        **context: Variables to pass to the template

    Returns:
        str: Rendered template content
    """
    template = _env.get_template(template_name)
    return template.render(**context)


def render_daily_log(
    date_str: str,
    workout_type: str,
    planned_workout: str,
    briefing: str,
    todos: list,
    include_strength_log: bool = False,
    cardio_activities: list = None,
    yesterday_macros: dict = None,
) -> str:
    """
    Render daily log template with LLM-generated content.

    Args:
        date_str: Date in YYYY-MM-DD format
        workout_type: One of: strength, swim, bike, run, brick, recovery
        planned_workout: Full workout description
        briefing: AI-generated daily briefing
        todos: List of todo strings (with "- [ ]" prefix)
        include_strength_log: Whether to show strength log section
        cardio_activities: List of cardio types: ["swim", "bike", "run"]
        yesterday_macros: Dict with calories, protein_g, carbs_g, fat_g (or None)

    Returns:
        str: Complete daily log markdown
    """
    cardio_activities = cardio_activities or []

    return render_template(
        "daily_log.md",
        date=date_str,
        workout_type=workout_type,
        planned_workout=planned_workout,
        briefing=briefing,
        todos=todos,
        todos_markdown="\n".join(todos),
        include_strength_log=include_strength_log,
        cardio_activities=cardio_activities,
        has_cardio=bool(cardio_activities),
        yesterday_macros=yesterday_macros,
    )
