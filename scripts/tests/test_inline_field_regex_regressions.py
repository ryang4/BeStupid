import os
import sys
import types
from textwrap import dedent


SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

# Keep tests isolated from optional runtime dependencies that aren't needed here.
if "frontmatter" not in sys.modules:
    try:
        import frontmatter  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        frontmatter_stub = types.ModuleType("frontmatter")
        frontmatter_stub.load = lambda *args, **kwargs: None
        sys.modules["frontmatter"] = frontmatter_stub

if "dotenv" not in sys.modules:
    try:
        import dotenv  # type: ignore  # noqa: F401
    except ModuleNotFoundError:
        dotenv_stub = types.ModuleType("dotenv")
        dotenv_stub.load_dotenv = lambda *args, **kwargs: None
        sys.modules["dotenv"] = dotenv_stub

from calorie_estimator import get_inline_total, upsert_inline_total
from daily_checkins import read_inline_total
from weekly_planner import _parse_inline_field


def test_weekly_parse_blank_weight_does_not_capture_sleep():
    content = dedent(
        """\
        ## Quick Log
        Weight::
        Sleep:: 8.08
        """
    )

    assert _parse_inline_field(content, "Weight") is None
    assert _parse_inline_field(content, "Sleep") == "8.08"


def test_calorie_parse_blank_calories_does_not_capture_next_macro():
    content = dedent(
        """\
        ## Fuel Log
        calories_so_far::
        protein_so_far:: 120
        carbs_so_far:: 80
        """
    )

    assert get_inline_total(content, "calories_so_far") == 0
    assert get_inline_total(content, "protein_so_far") == 120
    assert get_inline_total(content, "carbs_so_far") == 80


def test_calorie_upsert_blank_calories_updates_only_target_line():
    content = dedent(
        """\
        ## Fuel Log
        calories_so_far::
        protein_so_far:: 120
        carbs_so_far:: 80
        """
    )

    updated = upsert_inline_total(content, "calories_so_far", 950)

    assert updated == dedent(
        """\
        ## Fuel Log
        calories_so_far:: 950
        protein_so_far:: 120
        carbs_so_far:: 80
        """
    )


def test_daily_checkins_blank_calories_does_not_capture_next_metric():
    content = dedent(
        """\
        calories_so_far::
        protein_so_far:: 140
        """
    )

    assert read_inline_total(content, "calories_so_far") == 0
    assert read_inline_total(content, "protein_so_far") == 140
