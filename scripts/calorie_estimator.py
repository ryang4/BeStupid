"""
Calorie Estimator - On-demand macro estimation for food items.

Standalone script for real-time calorie/macro tracking via:
- iOS Shortcuts (via GitHub Actions workflow_dispatch)
- Command line for testing
- Direct API calls

Returns structured macro breakdown and optionally appends to daily log.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from llm_client import estimate_macros

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOGS_DIR = os.path.join(PROJECT_ROOT, "content", "logs")


def estimate_food(food_description: str) -> dict:
    """
    Estimate calories and macros for a food description.

    Args:
        food_description: Text description of food (e.g., "2 eggs with toast")

    Returns:
        dict with:
            - success: bool
            - food: original description
            - calories: int
            - protein_g: int
            - carbs_g: int
            - fat_g: int
            - fiber_g: int
            - line_items: list of individual items if multiple foods
            - error: str (only if success=False)
    """
    if not food_description or len(food_description.strip()) < 3:
        return {
            "success": False,
            "food": food_description,
            "error": "Food description too short"
        }

    try:
        result = estimate_macros(food_description)

        if result is None:
            return {
                "success": False,
                "food": food_description,
                "error": "LLM estimation failed"
            }

        return {
            "success": True,
            "food": food_description,
            "calories": result.get("calories", 0),
            "protein_g": result.get("protein_g", 0),
            "carbs_g": result.get("carbs_g", 0),
            "fat_g": result.get("fat_g", 0),
            "fiber_g": result.get("fiber_g", 0),
            "line_items": result.get("line_items", [])
        }

    except Exception as e:
        return {
            "success": False,
            "food": food_description,
            "error": str(e)
        }


def get_running_total(date_str: str = None) -> dict:
    """
    Get running calorie total from today's log.

    Args:
        date_str: Date in YYYY-MM-DD format (defaults to today)

    Returns:
        dict with:
            - calories_so_far: int
            - protein_so_far: int
            - entries_count: int
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    log_path = os.path.join(LOGS_DIR, f"{date_str}.md")

    if not os.path.exists(log_path):
        return {
            "calories_so_far": 0,
            "protein_so_far": 0,
            "entries_count": 0
        }

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for running total in frontmatter or inline field
        # Format: calories_so_far:: 1200
        import re

        calories_match = re.search(r'calories_so_far::\s*(\d+)', content)
        protein_match = re.search(r'protein_so_far::\s*(\d+)', content)

        return {
            "calories_so_far": int(calories_match.group(1)) if calories_match else 0,
            "protein_so_far": int(protein_match.group(1)) if protein_match else 0,
            "entries_count": content.count("- **") if "## Fuel Log" in content else 0
        }

    except Exception:
        return {
            "calories_so_far": 0,
            "protein_so_far": 0,
            "entries_count": 0
        }


def append_to_fuel_log(food_description: str, macros: dict, date_str: str = None) -> bool:
    """
    Append a food entry to today's Fuel Log section.

    Args:
        food_description: Original food text
        macros: Dict with calories, protein_g, etc.
        date_str: Date in YYYY-MM-DD format (defaults to today)

    Returns:
        bool: True if successfully appended
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    log_path = os.path.join(LOGS_DIR, f"{date_str}.md")

    if not os.path.exists(log_path):
        return False

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if "## Fuel Log" not in content:
            return False

        # Create the entry line
        time_str = datetime.now().strftime("%I:%M%p").lower().lstrip("0")
        entry = f"- **{time_str}**: {food_description} (~{macros['calories']} cal, {macros['protein_g']}g protein)"

        # Find Fuel Log section and append
        fuel_idx = content.index("## Fuel Log")
        next_section = content.find("\n## ", fuel_idx + 1)

        if next_section == -1:
            # Fuel Log is the last section
            content = content.rstrip() + "\n" + entry + "\n"
        else:
            # Insert before next section
            # Find last non-empty line before next section
            section_content = content[fuel_idx:next_section]
            lines = section_content.rstrip().split("\n")

            # Append entry
            new_section = "\n".join(lines) + "\n" + entry + "\n\n"
            content = content[:fuel_idx] + new_section + content[next_section:]

        # Update running totals (inline fields)
        running = get_running_total(date_str)
        new_calories = running["calories_so_far"] + macros["calories"]
        new_protein = running["protein_so_far"] + macros["protein_g"]

        # Update or add running totals
        import re
        if "calories_so_far::" in content:
            content = re.sub(r'calories_so_far::\s*\d+', f'calories_so_far:: {new_calories}', content)
        if "protein_so_far::" in content:
            content = re.sub(r'protein_so_far::\s*\d+', f'protein_so_far:: {new_protein}', content)

        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True

    except Exception as e:
        print(f"Error appending to fuel log: {e}", file=sys.stderr)
        return False


def format_result_for_display(result: dict, running_total: dict = None) -> str:
    """
    Format estimation result for display (iOS notification, terminal).

    Args:
        result: Dict from estimate_food()
        running_total: Optional dict with running totals

    Returns:
        str: Human-readable formatted result
    """
    if not result.get("success"):
        return f"Error: {result.get('error', 'Unknown error')}"

    lines = [
        f"Food: {result['food']}",
        f"Calories: {result['calories']}",
        f"Protein: {result['protein_g']}g",
        f"Carbs: {result['carbs_g']}g",
        f"Fat: {result['fat_g']}g"
    ]

    if result.get("fiber_g"):
        lines.append(f"Fiber: {result['fiber_g']}g")

    if running_total and running_total.get("calories_so_far"):
        new_total = running_total["calories_so_far"] + result["calories"]
        lines.append("")
        lines.append(f"Today's total: {new_total} cal")

    return "\n".join(lines)


def main():
    """Command-line interface for calorie estimation."""
    parser = argparse.ArgumentParser(
        description="Estimate calories and macros for food items"
    )
    parser.add_argument(
        "food",
        nargs="?",
        help="Food description to estimate"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (for API/automation)"
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to today's fuel log"
    )
    parser.add_argument(
        "--date",
        help="Date for fuel log (YYYY-MM-DD, defaults to today)"
    )
    parser.add_argument(
        "--running-total",
        action="store_true",
        help="Include running total in output"
    )

    args = parser.parse_args()

    # Get food description from args or stdin
    if args.food:
        food = args.food
    elif not sys.stdin.isatty():
        food = sys.stdin.read().strip()
    else:
        # Interactive mode
        print("Enter food description:")
        food = input().strip()

    if not food:
        print("Error: No food description provided", file=sys.stderr)
        sys.exit(1)

    # Estimate macros
    result = estimate_food(food)

    # Get running total if requested
    running = None
    if args.running_total or args.append:
        running = get_running_total(args.date)

    # Append to log if requested
    if args.append and result.get("success"):
        appended = append_to_fuel_log(food, result, args.date)
        result["appended_to_log"] = appended

    # Output
    if args.json:
        if running:
            result["running_total"] = running
        print(json.dumps(result, indent=2))
    else:
        print(format_result_for_display(result, running if args.running_total else None))


if __name__ == "__main__":
    main()
