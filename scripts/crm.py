"""
Personal CRM - Relationship tracking for life optimization.

Tracks:
- Key relationships (mentors, investors, friends, family, colleagues)
- Last interaction date and notes
- Follow-up reminders
- Birthdays and important dates
- Relationship health score

Data stored in content/relationships/ as markdown files.
Metadata stored in data/crm_metrics.json for analysis.
"""

import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List
import frontmatter

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RELATIONSHIPS_DIR = os.path.join(PROJECT_ROOT, "content", "relationships")
CRM_DATA_FILE = os.path.join(SCRIPT_DIR, "data", "crm_metrics.json")

# Relationship categories
CATEGORIES = ["mentors", "investors", "friends", "family", "colleagues", "clients"]

# Default follow-up intervals by category (days)
DEFAULT_FOLLOWUP_DAYS = {
    "mentors": 14,
    "investors": 30,
    "friends": 21,
    "family": 7,
    "colleagues": 14,
    "clients": 7
}


def ensure_directories():
    """Create relationship directory structure if it doesn't exist."""
    if not os.path.exists(RELATIONSHIPS_DIR):
        os.makedirs(RELATIONSHIPS_DIR)

    for category in CATEGORIES:
        cat_dir = os.path.join(RELATIONSHIPS_DIR, category)
        if not os.path.exists(cat_dir):
            os.makedirs(cat_dir)

    # Create template if it doesn't exist
    template_path = os.path.join(RELATIONSHIPS_DIR, "_template.md")
    if not os.path.exists(template_path):
        create_template()


def create_template():
    """Create the relationship template file."""
    template = '''---
name: "Person Name"
category: "friends"  # mentors, investors, friends, family, colleagues, clients
importance: "high"   # high, medium, low
followup_days: 14    # Days between follow-ups

# Contact Info
email: ""
phone: ""
location: ""
linkedin: ""
twitter: ""

# Important Dates
birthday: ""         # YYYY-MM-DD format
anniversary: ""      # Any recurring important date
met_date: ""         # When you first met

# Relationship Context
how_we_met: ""
their_interests: []
common_ground: []
can_help_with: []    # What they can help you with
you_help_with: []    # What you can help them with

# Current Status
last_interaction: "" # YYYY-MM-DD
last_interaction_type: ""  # call, coffee, dinner, text, email
relationship_health: 5     # 1-10 scale
---

## Notes

<!-- General notes about this person -->

## Interaction Log

<!-- Format: YYYY-MM-DD | type | notes -->
<!-- Example: 2026-01-20 | coffee | Discussed their new startup -->

## Follow-up Items

- [ ]

## Gift Ideas / Thoughtful Actions

-

'''
    template_path = os.path.join(RELATIONSHIPS_DIR, "_template.md")
    with open(template_path, 'w') as f:
        f.write(template)


def load_relationship(filepath: str) -> Optional[dict]:
    """
    Load a relationship from a markdown file.

    Returns:
        dict with metadata and content
    """
    try:
        post = frontmatter.load(filepath)
        return {
            "metadata": dict(post.metadata),
            "content": post.content,
            "filepath": filepath,
            "filename": os.path.basename(filepath)
        }
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def save_relationship(filepath: str, metadata: dict, content: str):
    """Save a relationship to a markdown file."""
    post = frontmatter.Post(content, **metadata)
    with open(filepath, 'w') as f:
        f.write(frontmatter.dumps(post))


def get_all_relationships() -> List[dict]:
    """
    Load all relationships from all categories.

    Returns:
        List of relationship dicts
    """
    relationships = []

    for category in CATEGORIES:
        cat_dir = os.path.join(RELATIONSHIPS_DIR, category)
        if not os.path.exists(cat_dir):
            continue

        for filename in os.listdir(cat_dir):
            if filename.endswith('.md') and not filename.startswith('_'):
                filepath = os.path.join(cat_dir, filename)
                rel = load_relationship(filepath)
                if rel:
                    rel["category"] = category
                    relationships.append(rel)

    return relationships


def calculate_days_since_interaction(last_interaction: str) -> Optional[int]:
    """Calculate days since last interaction."""
    if not last_interaction:
        return None

    try:
        last_date = datetime.strptime(last_interaction, "%Y-%m-%d")
        return (datetime.now() - last_date).days
    except ValueError:
        return None


def get_overdue_followups() -> List[dict]:
    """
    Get relationships that are overdue for follow-up.

    Returns:
        List of relationships sorted by urgency
    """
    overdue = []

    for rel in get_all_relationships():
        meta = rel.get("metadata", {})

        last_interaction = meta.get("last_interaction", "")
        days_since = calculate_days_since_interaction(last_interaction)

        if days_since is None:
            # Never interacted - urgent
            overdue.append({
                "name": meta.get("name", rel["filename"]),
                "category": rel.get("category", meta.get("category", "unknown")),
                "days_overdue": 999,
                "last_interaction": "Never",
                "importance": meta.get("importance", "medium"),
                "filepath": rel["filepath"]
            })
            continue

        followup_days = meta.get("followup_days", DEFAULT_FOLLOWUP_DAYS.get(rel.get("category"), 14))

        if days_since > followup_days:
            overdue.append({
                "name": meta.get("name", rel["filename"]),
                "category": rel.get("category", meta.get("category", "unknown")),
                "days_overdue": days_since - followup_days,
                "days_since": days_since,
                "last_interaction": last_interaction,
                "importance": meta.get("importance", "medium"),
                "filepath": rel["filepath"]
            })

    # Sort by importance then days overdue
    importance_order = {"high": 0, "medium": 1, "low": 2}
    overdue.sort(key=lambda x: (importance_order.get(x["importance"], 1), -x["days_overdue"]))

    return overdue


def get_upcoming_dates(days: int = 30) -> List[dict]:
    """
    Get upcoming birthdays and important dates.

    Args:
        days: Number of days to look ahead

    Returns:
        List of upcoming events
    """
    upcoming = []
    today = datetime.now()

    for rel in get_all_relationships():
        meta = rel.get("metadata", {})
        name = meta.get("name", rel["filename"])

        # Check birthday
        birthday = meta.get("birthday", "")
        if birthday:
            try:
                bday = datetime.strptime(birthday, "%Y-%m-%d")
                # Set to this year
                this_year_bday = bday.replace(year=today.year)
                if this_year_bday < today:
                    this_year_bday = this_year_bday.replace(year=today.year + 1)

                days_until = (this_year_bday - today).days
                if 0 <= days_until <= days:
                    age = today.year - bday.year
                    if this_year_bday.year > today.year:
                        age += 1
                    upcoming.append({
                        "type": "birthday",
                        "name": name,
                        "date": this_year_bday.strftime("%Y-%m-%d"),
                        "days_until": days_until,
                        "details": f"Turning {age}",
                        "category": rel.get("category", "unknown")
                    })
            except ValueError:
                pass

        # Check anniversary
        anniversary = meta.get("anniversary", "")
        if anniversary:
            try:
                ann = datetime.strptime(anniversary, "%Y-%m-%d")
                this_year_ann = ann.replace(year=today.year)
                if this_year_ann < today:
                    this_year_ann = this_year_ann.replace(year=today.year + 1)

                days_until = (this_year_ann - today).days
                if 0 <= days_until <= days:
                    upcoming.append({
                        "type": "anniversary",
                        "name": name,
                        "date": this_year_ann.strftime("%Y-%m-%d"),
                        "days_until": days_until,
                        "details": "Anniversary",
                        "category": rel.get("category", "unknown")
                    })
            except ValueError:
                pass

    upcoming.sort(key=lambda x: x["days_until"])
    return upcoming


def log_interaction(name: str, interaction_type: str, notes: str = "") -> bool:
    """
    Log an interaction with a person.

    Args:
        name: Person's name (partial match supported)
        interaction_type: Type of interaction (call, coffee, dinner, text, email)
        notes: Optional notes about the interaction

    Returns:
        bool: True if successful
    """
    # Find the person
    relationships = get_all_relationships()
    matches = [r for r in relationships if name.lower() in r["metadata"].get("name", "").lower()]

    if not matches:
        print(f"No match found for '{name}'")
        return False

    if len(matches) > 1:
        print(f"Multiple matches found: {[r['metadata'].get('name') for r in matches]}")
        return False

    rel = matches[0]
    meta = rel["metadata"]
    content = rel["content"]

    # Update last interaction
    today = datetime.now().strftime("%Y-%m-%d")
    meta["last_interaction"] = today
    meta["last_interaction_type"] = interaction_type

    # Add to interaction log
    log_entry = f"\n{today} | {interaction_type} | {notes}" if notes else f"\n{today} | {interaction_type}"

    if "## Interaction Log" in content:
        content = content.replace("## Interaction Log", f"## Interaction Log{log_entry}")
    else:
        content += f"\n\n## Interaction Log{log_entry}"

    # Save
    save_relationship(rel["filepath"], meta, content)
    print(f"Logged {interaction_type} with {meta.get('name', name)}")

    return True


def create_relationship(name: str, category: str, **kwargs) -> str:
    """
    Create a new relationship file.

    Args:
        name: Person's name
        category: Category (mentors, investors, friends, family, colleagues, clients)
        **kwargs: Additional metadata fields

    Returns:
        str: Path to created file
    """
    ensure_directories()

    if category not in CATEGORIES:
        raise ValueError(f"Invalid category. Must be one of: {CATEGORIES}")

    # Create filename from name
    filename = name.lower().replace(" ", "_") + ".md"
    filepath = os.path.join(RELATIONSHIPS_DIR, category, filename)

    if os.path.exists(filepath):
        raise ValueError(f"Relationship file already exists: {filepath}")

    # Build metadata
    metadata = {
        "name": name,
        "category": category,
        "importance": kwargs.get("importance", "medium"),
        "followup_days": kwargs.get("followup_days", DEFAULT_FOLLOWUP_DAYS.get(category, 14)),
        "email": kwargs.get("email", ""),
        "phone": kwargs.get("phone", ""),
        "location": kwargs.get("location", ""),
        "linkedin": kwargs.get("linkedin", ""),
        "twitter": kwargs.get("twitter", ""),
        "birthday": kwargs.get("birthday", ""),
        "anniversary": kwargs.get("anniversary", ""),
        "met_date": kwargs.get("met_date", datetime.now().strftime("%Y-%m-%d")),
        "how_we_met": kwargs.get("how_we_met", ""),
        "their_interests": kwargs.get("their_interests", []),
        "common_ground": kwargs.get("common_ground", []),
        "can_help_with": kwargs.get("can_help_with", []),
        "you_help_with": kwargs.get("you_help_with", []),
        "last_interaction": kwargs.get("last_interaction", ""),
        "last_interaction_type": kwargs.get("last_interaction_type", ""),
        "relationship_health": kwargs.get("relationship_health", 5)
    }

    content = """## Notes

<!-- General notes about this person -->

## Interaction Log

<!-- Format: YYYY-MM-DD | type | notes -->

## Follow-up Items

- [ ]

## Gift Ideas / Thoughtful Actions

-

"""

    save_relationship(filepath, metadata, content)
    print(f"Created relationship: {filepath}")

    return filepath


def get_relationship_summary() -> dict:
    """
    Get a summary of all relationships for dashboard display.

    Returns:
        dict with counts, overdue, upcoming dates, health metrics
    """
    relationships = get_all_relationships()
    overdue = get_overdue_followups()
    upcoming = get_upcoming_dates(14)  # Next 2 weeks

    # Count by category
    by_category = {}
    for rel in relationships:
        cat = rel.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    # Count by importance
    by_importance = {"high": 0, "medium": 0, "low": 0}
    for rel in relationships:
        imp = rel.get("metadata", {}).get("importance", "medium")
        by_importance[imp] = by_importance.get(imp, 0) + 1

    # Average health score
    health_scores = [r.get("metadata", {}).get("relationship_health", 5) for r in relationships]
    avg_health = sum(health_scores) / len(health_scores) if health_scores else 0

    # Most neglected
    most_neglected = []
    for rel in relationships:
        meta = rel.get("metadata", {})
        days = calculate_days_since_interaction(meta.get("last_interaction", ""))
        if days is not None:
            most_neglected.append({
                "name": meta.get("name", "Unknown"),
                "days_since": days,
                "category": rel.get("category", "unknown")
            })
    most_neglected.sort(key=lambda x: -x["days_since"])

    return {
        "total_relationships": len(relationships),
        "by_category": by_category,
        "by_importance": by_importance,
        "overdue_count": len(overdue),
        "overdue_high_importance": len([o for o in overdue if o["importance"] == "high"]),
        "upcoming_dates_count": len(upcoming),
        "upcoming_dates": upcoming[:5],
        "average_health": round(avg_health, 1),
        "most_neglected": most_neglected[:5],
        "overdue_followups": overdue[:10]
    }


def generate_daily_nudges() -> List[str]:
    """
    Generate relationship nudges for daily briefing.

    Returns:
        List of nudge strings
    """
    nudges = []

    # Overdue follow-ups
    overdue = get_overdue_followups()
    high_priority = [o for o in overdue if o["importance"] == "high"]

    if high_priority:
        first = high_priority[0]
        nudges.append(f"Reach out to {first['name']} ({first['category']}) - {first['days_overdue']} days overdue")
    elif overdue:
        first = overdue[0]
        nudges.append(f"Consider reaching out to {first['name']} - last contact {first['days_since']} days ago")

    # Upcoming birthdays
    upcoming = get_upcoming_dates(7)  # Next week
    birthdays = [u for u in upcoming if u["type"] == "birthday"]

    for bday in birthdays[:2]:
        if bday["days_until"] == 0:
            nudges.append(f"TODAY: {bday['name']}'s birthday!")
        elif bday["days_until"] == 1:
            nudges.append(f"TOMORROW: {bday['name']}'s birthday")
        else:
            nudges.append(f"{bday['name']}'s birthday in {bday['days_until']} days")

    return nudges


def sync_crm_data():
    """
    Sync relationship data to JSON for analysis and dashboard.
    """
    summary = get_relationship_summary()

    data_dir = os.path.dirname(CRM_DATA_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    data = {
        "version": "1.0",
        "synced_at": datetime.now().isoformat(),
        "summary": summary
    }

    with open(CRM_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"CRM data synced to {CRM_DATA_FILE}")


if __name__ == "__main__":
    import sys

    ensure_directories()

    if len(sys.argv) < 2:
        # Default: show summary
        summary = get_relationship_summary()
        print(f"\n=== Relationship Summary ===")
        print(f"Total: {summary['total_relationships']} relationships")
        print(f"By category: {summary['by_category']}")
        print(f"Average health: {summary['average_health']}/10")
        print(f"\nOverdue follow-ups: {summary['overdue_count']}")
        for o in summary['overdue_followups'][:5]:
            print(f"  - {o['name']} ({o['category']}): {o['days_overdue']} days overdue")
        print(f"\nUpcoming dates:")
        for u in summary['upcoming_dates']:
            print(f"  - {u['name']}: {u['type']} in {u['days_until']} days")

    elif sys.argv[1] == "sync":
        sync_crm_data()

    elif sys.argv[1] == "nudges":
        nudges = generate_daily_nudges()
        print("\n=== Daily Relationship Nudges ===")
        for nudge in nudges:
            print(f"  - {nudge}")

    elif sys.argv[1] == "create" and len(sys.argv) >= 4:
        name = sys.argv[2]
        category = sys.argv[3]
        create_relationship(name, category)

    elif sys.argv[1] == "log" and len(sys.argv) >= 4:
        name = sys.argv[2]
        interaction_type = sys.argv[3]
        notes = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else ""
        log_interaction(name, interaction_type, notes)
