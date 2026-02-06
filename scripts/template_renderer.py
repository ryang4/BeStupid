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
    briefing,
    todos: list,
    command_engine: dict = None,
    include_strength_log: bool = False,
    strength_exercises: list = None,
    cardio_activities: list = None,
    yesterday_macros: dict = None,
    habits: list = None,
) -> str:
    """
    Render daily log template with LLM-generated content.

    Args:
        date_str: Date in YYYY-MM-DD format
        workout_type: One of: strength, swim, bike, run, brick, recovery
        planned_workout: Full workout description
        briefing: AI-generated daily briefing dict with:
                  - focus: str (today's main focus)
                  - tips: list of str (actionable tips)
                  - warnings: list of str (alerts, can be empty)
        todos: List of todo strings (with "- [ ]" prefix)
        command_engine: Dict with:
                  - workload_tier: str
                  - capacity_score: int (2-5)
                  - signals: list[str]
                  - must_win: list[str]
                  - can_do: list[str]
                  - not_today: list[str]
        include_strength_log: Whether to show strength log section
        strength_exercises: List of dicts with exercise, sets, reps, weight
        cardio_activities: List of cardio types: ["swim", "bike", "run"]
        yesterday_macros: Dict with calories, protein_g, carbs_g, fat_g (or None)
        habits: List of habit dicts with id and name (from habits.md config)

    Returns:
        str: Complete daily log markdown
    """
    cardio_activities = cardio_activities or []
    habits = habits or []
    strength_exercises = strength_exercises or []
    command_engine = command_engine or {
        "workload_tier": "focused",
        "capacity_score": 3,
        "signals": [],
        "must_win": [],
        "can_do": [],
        "not_today": [],
    }

    # Handle backwards compatibility if briefing is still a string
    if isinstance(briefing, str):
        briefing = {
            "focus": briefing,
            "tips": [],
            "warnings": []
        }

    return render_template(
        "daily_log.md",
        date=date_str,
        workout_type=workout_type,
        planned_workout=planned_workout,
        briefing=briefing,
        todos=todos,
        command_engine=command_engine,
        todos_markdown="\n".join(todos),
        include_strength_log=include_strength_log,
        strength_exercises=strength_exercises,
        cardio_activities=cardio_activities,
        has_cardio=bool(cardio_activities),
        yesterday_macros=yesterday_macros,
        habits=habits,
    )
