"""
Supplement Stack Tracker - Track supplements, timing, and effects.

Track:
- Current supplement stack
- Dosages and timing
- Effects on sleep, energy, recovery
- Cost tracking
- Protocol changes over time

Data stored in ~/.bestupid-private/supplements.json
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List

# Configuration
PRIVATE_DIR = os.path.expanduser("~/.bestupid-private")
SUPPLEMENTS_FILE = os.path.join(PRIVATE_DIR, "supplements.json")


def ensure_directories():
    """Create private directory if needed."""
    if not os.path.exists(PRIVATE_DIR):
        os.makedirs(PRIVATE_DIR)


def load_supplement_data() -> dict:
    """Load supplement data from file."""
    if os.path.exists(SUPPLEMENTS_FILE):
        try:
            with open(SUPPLEMENTS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass

    return {
        "version": "1.0",
        "current_stack": [],
        "protocols": [],
        "daily_logs": []
    }


def save_supplement_data(data: dict):
    """Save supplement data to file."""
    ensure_directories()
    data["last_updated"] = datetime.now().isoformat()

    with open(SUPPLEMENTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def add_supplement(
    name: str,
    dosage: str,
    timing: str = "morning",
    purpose: str = "",
    cost_per_month: float = 0,
    active: bool = True
) -> dict:
    """
    Add or update a supplement in the current stack.

    Args:
        name: Supplement name
        dosage: Dosage (e.g., "5000 IU", "500mg")
        timing: When to take (morning, lunch, dinner, bedtime, pre-workout, post-workout)
        purpose: What it's for
        cost_per_month: Monthly cost
        active: Whether currently taking

    Returns:
        Supplement dict
    """
    data = load_supplement_data()

    stack = data.get("current_stack", [])
    existing = next((s for s in stack if s["name"].lower() == name.lower()), None)

    supplement = {
        "id": existing["id"] if existing else len(stack) + 1,
        "name": name,
        "dosage": dosage,
        "timing": timing,
        "purpose": purpose,
        "cost_per_month": cost_per_month,
        "active": active,
        "added_date": existing["added_date"] if existing else datetime.now().strftime("%Y-%m-%d"),
        "updated_at": datetime.now().isoformat()
    }

    if existing:
        stack.remove(existing)

    stack.append(supplement)
    data["current_stack"] = stack
    save_supplement_data(data)

    print(f"{'Updated' if existing else 'Added'} supplement: {name}")
    return supplement


def log_daily_intake(date: str = None, taken: List[str] = None, notes: str = "") -> dict:
    """
    Log daily supplement intake.

    Args:
        date: Date (YYYY-MM-DD), defaults to today
        taken: List of supplement names taken
        notes: Notes on effects or changes

    Returns:
        Daily log entry
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    data = load_supplement_data()

    log_entry = {
        "date": date,
        "taken": taken or [],
        "notes": notes,
        "created_at": datetime.now().isoformat()
    }

    logs = data.get("daily_logs", [])
    
    # Remove existing log for this date if present
    logs = [l for l in logs if l["date"] != date]
    logs.append(log_entry)
    
    data["daily_logs"] = logs
    save_supplement_data(data)

    print(f"Logged supplement intake for {date}")
    return log_entry


def get_compliance_rate(days: int = 30) -> dict:
    """
    Calculate supplement compliance rate.

    Args:
        days: Days to look back

    Returns:
        dict with compliance stats per supplement
    """
    data = load_supplement_data()
    logs = data.get("daily_logs", [])
    stack = data.get("current_stack", [])

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent_logs = [l for l in logs if l["date"] >= cutoff]

    compliance = {}

    for supplement in stack:
        if not supplement.get("active"):
            continue

        name = supplement["name"]
        times_taken = sum(1 for log in recent_logs if name in log.get("taken", []))
        days_logged = len(recent_logs)

        compliance[name] = {
            "times_taken": times_taken,
            "days_logged": days_logged,
            "compliance_rate": round(times_taken / days_logged * 100, 1) if days_logged > 0 else 0,
            "timing": supplement["timing"]
        }

    return compliance


def save_protocol(name: str, description: str = "") -> dict:
    """
    Save current stack as a protocol.

    Args:
        name: Protocol name
        description: Protocol description

    Returns:
        Protocol dict
    """
    data = load_supplement_data()

    protocol = {
        "id": len(data.get("protocols", [])) + 1,
        "name": name,
        "description": description,
        "stack": data.get("current_stack", []),
        "created_at": datetime.now().isoformat()
    }

    protocols = data.get("protocols", [])
    protocols.append(protocol)
    data["protocols"] = protocols

    save_supplement_data(data)

    print(f"Saved protocol: {name}")
    return protocol


def generate_supplement_nudges() -> List[str]:
    """Generate supplement-related nudges."""
    nudges = []
    data = load_supplement_data()

    # Check compliance
    compliance = get_compliance_rate(7)
    low_compliance = [(name, stats) for name, stats in compliance.items() if stats["compliance_rate"] < 70]

    if low_compliance:
        for name, stats in low_compliance[:2]:
            nudges.append(f"Low compliance on {name}: {stats['compliance_rate']:.0f}% last 7 days")

    # Check if logged today
    today = datetime.now().strftime("%Y-%m-%d")
    logs = data.get("daily_logs", [])
    today_logged = any(log["date"] == today for log in logs)

    if not today_logged and data.get("current_stack"):
        nudges.append("Haven't logged supplement intake today")

    return nudges


def get_timing_groups() -> dict:
    """Group supplements by timing."""
    data = load_supplement_data()
    stack = [s for s in data.get("current_stack", []) if s.get("active")]

    groups = {}
    for supplement in stack:
        timing = supplement.get("timing", "unscheduled")
        if timing not in groups:
            groups[timing] = []
        groups[timing].append(supplement)

    return groups


def format_supplement_summary() -> str:
    """Format supplement summary as readable text."""
    data = load_supplement_data()
    stack = [s for s in data.get("current_stack", []) if s.get("active")]

    lines = []
    lines.append("=== Supplement Stack ===\n")

    if not stack:
        lines.append("No active supplements tracked.")
        return "\n".join(lines)

    # Group by timing
    groups = get_timing_groups()

    for timing in ["morning", "lunch", "dinner", "bedtime", "pre-workout", "post-workout", "unscheduled"]:
        if timing in groups and groups[timing]:
            lines.append(f"\n{timing.upper()}:")
            for supp in groups[timing]:
                lines.append(f"  • {supp['name']} - {supp['dosage']}")
                if supp.get("purpose"):
                    lines.append(f"    ({supp['purpose']})")

    # Total cost
    total_cost = sum(s.get("cost_per_month", 0) for s in stack)
    if total_cost > 0:
        lines.append(f"\nMonthly Cost: ${total_cost:.2f}")

    # Compliance
    compliance = get_compliance_rate(7)
    if compliance:
        avg_compliance = sum(c["compliance_rate"] for c in compliance.values()) / len(compliance)
        lines.append(f"\n7-Day Compliance: {avg_compliance:.0f}%")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    ensure_directories()

    if len(sys.argv) < 2:
        print(format_supplement_summary())

    elif sys.argv[1] == "add":
        # Interactive supplement add
        name = input("Supplement Name: ")
        dosage = input("Dosage: ")
        print("Timing options: morning, lunch, dinner, bedtime, pre-workout, post-workout")
        timing = input("Timing: ") or "morning"
        purpose = input("Purpose: ")
        cost = input("Monthly Cost ($): ").strip()

        add_supplement(
            name, dosage, timing, purpose,
            cost_per_month=float(cost) if cost else 0
        )

    elif sys.argv[1] == "log":
        # Log today's intake
        data = load_supplement_data()
        active = [s["name"] for s in data.get("current_stack", []) if s.get("active")]

        print("\nActive supplements:")
        for i, name in enumerate(active, 1):
            print(f"{i}. {name}")

        taken_input = input("\nWhich did you take? (comma-separated numbers or names): ")
        
        taken = []
        for item in taken_input.split(","):
            item = item.strip()
            if item.isdigit():
                idx = int(item) - 1
                if 0 <= idx < len(active):
                    taken.append(active[idx])
            else:
                taken.append(item)

        notes = input("Notes: ")

        log_daily_intake(taken=taken, notes=notes)

    elif sys.argv[1] == "compliance":
        compliance = get_compliance_rate(30)
        print("\n=== 30-Day Compliance ===")
        for name, stats in compliance.items():
            print(f"{name}: {stats['compliance_rate']:.0f}% ({stats['times_taken']}/{stats['days_logged']} days)")

    elif sys.argv[1] == "nudges":
        nudges = generate_supplement_nudges()
        print("\n=== Supplement Nudges ===")
        for nudge in nudges:
            print(f"  - {nudge}")
