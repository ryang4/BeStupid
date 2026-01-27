"""
Biomarker Tracker - Track blood work and health metrics over time.

Track:
- Blood work results (testosterone, cortisol, vitamin D, glucose, etc.)
- Trends and correlations with training/sleep/diet
- Reference ranges and alerts
- Lab test history

Data stored in ~/.bestupid-private/biomarkers.json
"""

import os
import json
from datetime import datetime
from typing import Optional, List

# Configuration
PRIVATE_DIR = os.path.expanduser("~/.bestupid-private")
BIOMARKERS_FILE = os.path.join(PRIVATE_DIR, "biomarkers.json")

# Common biomarkers with reference ranges (male, adjust as needed)
REFERENCE_RANGES = {
    "testosterone_total_ng_dl": {"min": 300, "max": 1000, "optimal": (600, 900)},
    "testosterone_free_pg_ml": {"min": 9, "max": 30, "optimal": (15, 25)},
    "cortisol_morning_ug_dl": {"min": 6, "max": 23, "optimal": (10, 18)},
    "vitamin_d_ng_ml": {"min": 30, "max": 100, "optimal": (50, 80)},
    "glucose_fasting_mg_dl": {"min": 70, "max": 99, "optimal": (75, 90)},
    "hba1c_percent": {"min": 0, "max": 5.6, "optimal": (4.5, 5.3)},
    "triglycerides_mg_dl": {"min": 0, "max": 150, "optimal": (0, 100)},
    "hdl_mg_dl": {"min": 40, "max": 999, "optimal": (60, 999)},
    "ldl_mg_dl": {"min": 0, "max": 100, "optimal": (0, 70)},
    "tsh_uiu_ml": {"min": 0.4, "max": 4.0, "optimal": (1.0, 2.5)},
    "creatinine_mg_dl": {"min": 0.7, "max": 1.3, "optimal": (0.8, 1.2)},
    "alt_u_l": {"min": 7, "max": 56, "optimal": (10, 40)},
    "ast_u_l": {"min": 10, "max": 40, "optimal": (10, 30)},
}


def ensure_directories():
    """Create private directory if needed."""
    if not os.path.exists(PRIVATE_DIR):
        os.makedirs(PRIVATE_DIR)


def load_biomarker_data() -> dict:
    """Load biomarker data from file."""
    if os.path.exists(BIOMARKERS_FILE):
        try:
            with open(BIOMARKERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass

    return {
        "version": "1.0",
        "lab_tests": [],
        "reference_ranges": REFERENCE_RANGES
    }


def save_biomarker_data(data: dict):
    """Save biomarker data to file."""
    ensure_directories()
    data["last_updated"] = datetime.now().isoformat()

    with open(BIOMARKERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    os.chmod(BIOMARKERS_FILE, 0o600)


def log_lab_test(
    test_date: str,
    lab_name: str = "",
    markers: dict = None,
    notes: str = ""
) -> dict:
    """
    Log a lab test with biomarker results.

    Args:
        test_date: Date of test (YYYY-MM-DD)
        lab_name: Lab or provider name
        markers: Dict of {marker_name: value}
        notes: Optional notes

    Returns:
        Lab test entry dict
    """
    data = load_biomarker_data()

    test = {
        "id": len(data.get("lab_tests", [])) + 1,
        "date": test_date,
        "lab_name": lab_name,
        "markers": markers or {},
        "notes": notes,
        "created_at": datetime.now().isoformat()
    }

    # Analyze each marker
    test["analysis"] = analyze_markers(markers or {})

    tests = data.get("lab_tests", [])
    tests.append(test)
    data["lab_tests"] = tests

    save_biomarker_data(data)

    print(f"Logged lab test from {test_date}")
    if test["analysis"]["warnings"]:
        print(f"⚠️  {len(test['analysis']['warnings'])} markers out of range")

    return test


def analyze_markers(markers: dict) -> dict:
    """
    Analyze markers against reference ranges.

    Returns:
        dict with status, warnings, optimal count
    """
    warnings = []
    optimal_count = 0
    in_range_count = 0
    out_of_range_count = 0

    for marker, value in markers.items():
        if marker not in REFERENCE_RANGES:
            continue

        ranges = REFERENCE_RANGES[marker]
        min_val = ranges["min"]
        max_val = ranges["max"]
        optimal = ranges.get("optimal")

        # Check if in range
        if value < min_val:
            warnings.append(f"{marker}: {value} (below min {min_val})")
            out_of_range_count += 1
        elif value > max_val:
            warnings.append(f"{marker}: {value} (above max {max_val})")
            out_of_range_count += 1
        else:
            in_range_count += 1

            # Check if optimal
            if optimal:
                opt_min, opt_max = optimal
                if opt_min <= value <= opt_max:
                    optimal_count += 1

    return {
        "total_markers": len(markers),
        "in_range": in_range_count,
        "out_of_range": out_of_range_count,
        "optimal": optimal_count,
        "warnings": warnings
    }


def get_marker_trends(marker: str, months: int = 6) -> dict:
    """
    Get trends for a specific marker over time.

    Args:
        marker: Marker name
        months: Months to look back

    Returns:
        dict with values, dates, trend direction
    """
    data = load_biomarker_data()
    tests = data.get("lab_tests", [])

    cutoff = datetime.now().timestamp() - (months * 30 * 24 * 3600)

    values = []
    dates = []

    for test in tests:
        try:
            test_date = datetime.fromisoformat(test["date"]).timestamp()
            if test_date < cutoff:
                continue

            if marker in test.get("markers", {}):
                values.append(test["markers"][marker])
                dates.append(test["date"])
        except (ValueError, KeyError):
            continue

    if len(values) < 2:
        return {"trend": "insufficient_data"}

    # Calculate trend
    change = values[-1] - values[0]
    percent_change = (change / values[0] * 100) if values[0] != 0 else 0

    return {
        "marker": marker,
        "values": values,
        "dates": dates,
        "current": values[-1],
        "previous": values[-2] if len(values) > 1 else None,
        "change": round(change, 2),
        "percent_change": round(percent_change, 1),
        "trend": "improving" if change > 0 else "declining" if change < 0 else "stable",
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 2)
    }


def generate_biomarker_nudges() -> List[str]:
    """Generate biomarker-related nudges for daily briefing."""
    nudges = []
    data = load_biomarker_data()
    tests = data.get("lab_tests", [])

    if not tests:
        return nudges

    # Check most recent test
    latest = tests[-1]
    test_date = datetime.strptime(latest["date"], "%Y-%m-%d")
    days_since = (datetime.now() - test_date).days

    if days_since > 180:
        nudges.append(f"Blood work is {days_since}d old - consider scheduling new tests")

    # Check for warnings in latest test
    analysis = latest.get("analysis", {})
    if analysis.get("warnings"):
        nudges.append(f"Latest blood work has {len(analysis['warnings'])} markers out of range")

    return nudges


def format_biomarker_summary() -> str:
    """Format biomarker summary as readable text."""
    data = load_biomarker_data()
    tests = data.get("lab_tests", [])

    lines = []
    lines.append("=== Biomarker Tracker ===\n")

    if not tests:
        lines.append("No lab tests recorded yet.")
        return "\n".join(lines)

    latest = tests[-1]
    lines.append(f"Latest Test: {latest['date']} ({latest.get('lab_name', 'N/A')})")

    analysis = latest.get("analysis", {})
    lines.append(f"Markers: {analysis.get('total_markers', 0)}")
    lines.append(f"In Range: {analysis.get('in_range', 0)}")
    lines.append(f"Optimal: {analysis.get('optimal', 0)}")

    if analysis.get("warnings"):
        lines.append(f"\nWARNINGS:")
        for warning in analysis["warnings"][:5]:
            lines.append(f"  ⚠️  {warning}")

    # Show key markers
    markers = latest.get("markers", {})
    key_markers = ["testosterone_total_ng_dl", "vitamin_d_ng_ml", "glucose_fasting_mg_dl"]

    if any(m in markers for m in key_markers):
        lines.append(f"\nKEY MARKERS:")
        for marker in key_markers:
            if marker in markers:
                value = markers[marker]
                ranges = REFERENCE_RANGES.get(marker, {})
                optimal = ranges.get("optimal", (0, 0))
                status = "✅" if optimal[0] <= value <= optimal[1] else "⚠️"
                lines.append(f"  {status} {marker}: {value}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    ensure_directories()

    if len(sys.argv) < 2:
        print(format_biomarker_summary())

    elif sys.argv[1] == "add":
        # Interactive lab test entry
        date = input("Test Date (YYYY-MM-DD): ") or datetime.now().strftime("%Y-%m-%d")
        lab = input("Lab Name: ")

        print("\nEnter marker values (press Enter to skip):")
        markers = {}

        # Prompt for common markers
        common = [
            "testosterone_total_ng_dl",
            "vitamin_d_ng_ml",
            "glucose_fasting_mg_dl",
            "hdl_mg_dl",
            "ldl_mg_dl",
            "triglycerides_mg_dl"
        ]

        for marker in common:
            val = input(f"{marker}: ").strip()
            if val:
                try:
                    markers[marker] = float(val)
                except ValueError:
                    pass

        notes = input("\nNotes: ")

        log_lab_test(date, lab, markers, notes)

    elif sys.argv[1] == "trend" and len(sys.argv) >= 3:
        marker = sys.argv[2]
        trend = get_marker_trends(marker)

        if trend.get("trend") == "insufficient_data":
            print(f"Insufficient data for {marker}")
        else:
            print(f"\n{marker} Trend:")
            print(f"  Current: {trend['current']}")
            print(f"  Change: {trend['change']} ({trend['percent_change']}%)")
            print(f"  Direction: {trend['trend']}")
            print(f"  Range: {trend['min']} - {trend['max']}")

    elif sys.argv[1] == "nudges":
        nudges = generate_biomarker_nudges()
        print("\n=== Biomarker Nudges ===")
        for nudge in nudges:
            print(f"  - {nudge}")
