"""
Decision Journal - Track major decisions for pattern analysis and learning.

Provides:
- Decision logging with context and reasoning
- Outcome tracking (30/90/365 day follow-ups)
- Decision quality analysis
- Pattern detection in decision-making
- Lessons learned compilation

Data stored in content/decisions/ as markdown files.
Metrics stored in data/decision_metrics.json for analysis.
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
DECISIONS_DIR = os.path.join(PROJECT_ROOT, "content", "decisions")
DECISION_DATA_FILE = os.path.join(SCRIPT_DIR, "data", "decision_metrics.json")

# Decision categories
CATEGORIES = [
    "career", "health", "finance", "relationships", "business",
    "learning", "lifestyle", "technology"
]

# Decision importance levels
IMPORTANCE_LEVELS = ["critical", "major", "moderate", "minor"]

# Outcome review intervals (days)
REVIEW_INTERVALS = [30, 90, 365]


def ensure_directories():
    """Create decision directory structure."""
    if not os.path.exists(DECISIONS_DIR):
        os.makedirs(DECISIONS_DIR)


def create_decision_template(title: str, category: str, importance: str = "moderate") -> str:
    """Create a decision journal entry template."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    template = f'''---
title: "{title}"
date: "{date_str}"
category: "{category}"
importance: "{importance}"
status: "pending"  # pending, decided, reviewing, closed

# Decision Metadata
decision_date: ""
reversible: true
time_pressure: "low"  # low, medium, high, urgent

# Outcome Tracking
outcome_30d: ""
outcome_90d: ""
outcome_365d: ""
final_rating: 0  # 1-10 scale

# Tags for pattern analysis
tags: []
---

# {title}

## Context
<!-- What situation led to this decision? What problem are you solving? -->


## Options Considered

### Option A:
**Pros:**
-

**Cons:**
-

**Effort/Cost:**

---

### Option B:
**Pros:**
-

**Cons:**
-

**Effort/Cost:**

---

### Option C:
**Pros:**
-

**Cons:**
-

**Effort/Cost:**

---

## Decision Criteria
<!-- What factors matter most? Rank them. -->
1.
2.
3.

## Analysis
<!-- How did you weigh the options? What framework did you use? -->


## The Decision
**Chosen Option:**

**Reasoning:**


**What Would Change My Mind:**


## Pre-Mortem
<!-- Imagine this decision failed. What went wrong? -->


## Success Metrics
<!-- How will you know if this was the right decision? -->
-

---

## 30-Day Review
**Date:**

**Outcome So Far:**


**Early Lessons:**


**Adjustments Made:**


---

## 90-Day Review
**Date:**

**Outcome:**


**What I Learned:**


**Would I Decide Differently?**


---

## 365-Day Review / Final Assessment
**Date:**

**Final Outcome:**


**Key Lessons:**


**Rating (1-10):**

**Pattern Notes:**
<!-- Does this connect to other decisions? What does it reveal about your decision-making? -->

'''
    return template


def create_decision(title: str, category: str, importance: str = "moderate") -> str:
    """
    Create a new decision journal entry.

    Args:
        title: Brief title of the decision
        category: Category (career, health, finance, etc.)
        importance: critical, major, moderate, minor

    Returns:
        Path to created file
    """
    ensure_directories()

    if category not in CATEGORIES:
        print(f"Warning: Unknown category '{category}'. Using anyway.")

    if importance not in IMPORTANCE_LEVELS:
        importance = "moderate"

    # Create filename from date and title
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    filename = f"{date_str}-{slug}.md"
    filepath = os.path.join(DECISIONS_DIR, filename)

    if os.path.exists(filepath):
        # Append number if exists
        for i in range(2, 10):
            filepath = os.path.join(DECISIONS_DIR, f"{date_str}-{slug}-{i}.md")
            if not os.path.exists(filepath):
                break

    content = create_decision_template(title, category, importance)

    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Created decision: {filepath}")
    return filepath


def load_decision(filepath: str) -> Optional[dict]:
    """Load a decision from a markdown file."""
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


def get_all_decisions() -> List[dict]:
    """Get all decisions."""
    decisions = []

    if not os.path.exists(DECISIONS_DIR):
        return decisions

    for filename in os.listdir(DECISIONS_DIR):
        if filename.endswith('.md') and not filename.startswith('_'):
            filepath = os.path.join(DECISIONS_DIR, filename)
            decision = load_decision(filepath)
            if decision:
                decisions.append(decision)

    # Sort by date descending
    decisions.sort(key=lambda x: x["metadata"].get("date", ""), reverse=True)

    return decisions


def get_pending_reviews() -> List[dict]:
    """
    Get decisions that need outcome reviews.

    Returns:
        List of decisions needing review with review type
    """
    pending = []
    now = datetime.now()

    for decision in get_all_decisions():
        meta = decision["metadata"]

        # Skip if not decided yet
        if meta.get("status") != "decided":
            continue

        decision_date_str = meta.get("decision_date", meta.get("date", ""))
        if not decision_date_str:
            continue

        try:
            decision_date = datetime.strptime(decision_date_str, "%Y-%m-%d")
        except ValueError:
            continue

        days_since = (now - decision_date).days

        # Check which reviews are due
        for interval in REVIEW_INTERVALS:
            review_key = f"outcome_{interval}d"

            # If within window (interval +/- 7 days) and not yet reviewed
            if interval - 7 <= days_since <= interval + 30:
                if not meta.get(review_key):
                    pending.append({
                        "title": meta.get("title", decision["filename"]),
                        "decision_date": decision_date_str,
                        "days_since": days_since,
                        "review_type": f"{interval}-day",
                        "importance": meta.get("importance", "moderate"),
                        "filepath": decision["filepath"]
                    })
                    break  # Only add once per decision

    # Sort by importance then days since
    importance_order = {"critical": 0, "major": 1, "moderate": 2, "minor": 3}
    pending.sort(key=lambda x: (importance_order.get(x["importance"], 2), -x["days_since"]))

    return pending


def get_decision_stats() -> dict:
    """
    Calculate decision-making statistics.

    Returns:
        dict with counts, ratings, patterns
    """
    decisions = get_all_decisions()

    if not decisions:
        return {"total": 0}

    # Count by category
    by_category = {}
    for d in decisions:
        cat = d["metadata"].get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    # Count by importance
    by_importance = {}
    for d in decisions:
        imp = d["metadata"].get("importance", "moderate")
        by_importance[imp] = by_importance.get(imp, 0) + 1

    # Count by status
    by_status = {}
    for d in decisions:
        status = d["metadata"].get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

    # Average ratings for closed decisions
    ratings = [d["metadata"].get("final_rating", 0) for d in decisions
               if d["metadata"].get("status") == "closed" and d["metadata"].get("final_rating")]
    avg_rating = sum(ratings) / len(ratings) if ratings else None

    # Reversibility stats
    reversible_count = sum(1 for d in decisions if d["metadata"].get("reversible", True))

    # Tag frequency
    tags = {}
    for d in decisions:
        for tag in d["metadata"].get("tags", []):
            tags[tag] = tags.get(tag, 0) + 1

    return {
        "total": len(decisions),
        "by_category": by_category,
        "by_importance": by_importance,
        "by_status": by_status,
        "average_rating": round(avg_rating, 1) if avg_rating else None,
        "reversible_ratio": round(reversible_count / len(decisions), 2),
        "top_tags": sorted(tags.items(), key=lambda x: -x[1])[:10],
        "pending_reviews": len(get_pending_reviews())
    }


def analyze_decision_patterns() -> dict:
    """
    Analyze patterns in decision-making over time.

    Returns:
        dict with pattern analysis
    """
    decisions = get_all_decisions()
    closed = [d for d in decisions if d["metadata"].get("status") == "closed"
              and d["metadata"].get("final_rating")]

    if len(closed) < 5:
        return {"insufficient_data": True}

    # Best and worst decisions
    sorted_by_rating = sorted(closed, key=lambda x: x["metadata"].get("final_rating", 0), reverse=True)
    best = sorted_by_rating[:3]
    worst = sorted_by_rating[-3:]

    # Category performance
    category_ratings = {}
    for d in closed:
        cat = d["metadata"].get("category", "unknown")
        rating = d["metadata"].get("final_rating", 0)
        if cat not in category_ratings:
            category_ratings[cat] = []
        category_ratings[cat].append(rating)

    category_avg = {cat: round(sum(ratings)/len(ratings), 1)
                    for cat, ratings in category_ratings.items()}

    # Time pressure impact
    pressure_ratings = {"low": [], "medium": [], "high": [], "urgent": []}
    for d in closed:
        pressure = d["metadata"].get("time_pressure", "low")
        rating = d["metadata"].get("final_rating", 0)
        if pressure in pressure_ratings:
            pressure_ratings[pressure].append(rating)

    pressure_avg = {p: round(sum(r)/len(r), 1) if r else None
                    for p, r in pressure_ratings.items()}

    # Reversibility impact
    reversible_ratings = [d["metadata"].get("final_rating", 0) for d in closed
                          if d["metadata"].get("reversible", True)]
    irreversible_ratings = [d["metadata"].get("final_rating", 0) for d in closed
                            if not d["metadata"].get("reversible", True)]

    return {
        "sample_size": len(closed),
        "best_decisions": [{"title": d["metadata"].get("title"), "rating": d["metadata"].get("final_rating")}
                          for d in best],
        "worst_decisions": [{"title": d["metadata"].get("title"), "rating": d["metadata"].get("final_rating")}
                           for d in worst],
        "category_performance": category_avg,
        "time_pressure_impact": pressure_avg,
        "reversible_avg": round(sum(reversible_ratings)/len(reversible_ratings), 1) if reversible_ratings else None,
        "irreversible_avg": round(sum(irreversible_ratings)/len(irreversible_ratings), 1) if irreversible_ratings else None
    }


def generate_decision_nudges() -> List[str]:
    """Generate decision-related nudges for daily briefing."""
    nudges = []

    pending = get_pending_reviews()
    if pending:
        first = pending[0]
        nudges.append(f"Decision review due: '{first['title']}' ({first['review_type']} review)")

    # Check for decisions that have been pending too long
    for decision in get_all_decisions():
        if decision["metadata"].get("status") == "pending":
            date_str = decision["metadata"].get("date", "")
            if date_str:
                try:
                    created = datetime.strptime(date_str, "%Y-%m-%d")
                    days_pending = (datetime.now() - created).days
                    if days_pending > 7:
                        nudges.append(f"Pending decision for {days_pending} days: '{decision['metadata'].get('title')}'")
                        break
                except ValueError:
                    pass

    return nudges


def get_decision_summary() -> dict:
    """Get summary for dashboard display."""
    stats = get_decision_stats()
    patterns = analyze_decision_patterns()
    pending = get_pending_reviews()

    return {
        "stats": stats,
        "patterns": patterns if not patterns.get("insufficient_data") else None,
        "pending_reviews": pending[:5],
        "nudges": generate_decision_nudges()
    }


def sync_decision_data():
    """Sync decision data to JSON for analysis."""
    summary = get_decision_summary()

    data_dir = os.path.dirname(DECISION_DATA_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    data = {
        "version": "1.0",
        "synced_at": datetime.now().isoformat(),
        "summary": summary
    }

    with open(DECISION_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Decision data synced to {DECISION_DATA_FILE}")


if __name__ == "__main__":
    import sys

    ensure_directories()

    if len(sys.argv) < 2:
        # Show summary
        stats = get_decision_stats()
        print(f"\n=== Decision Journal Summary ===")
        print(f"Total decisions: {stats['total']}")
        print(f"By status: {stats.get('by_status', {})}")
        print(f"Average rating: {stats.get('average_rating', 'N/A')}")
        print(f"Pending reviews: {stats.get('pending_reviews', 0)}")

        pending = get_pending_reviews()
        if pending:
            print("\nReviews Due:")
            for p in pending[:5]:
                print(f"  - {p['title']} ({p['review_type']} - {p['days_since']} days)")

    elif sys.argv[1] == "create" and len(sys.argv) >= 4:
        title = sys.argv[2]
        category = sys.argv[3]
        importance = sys.argv[4] if len(sys.argv) > 4 else "moderate"
        create_decision(title, category, importance)

    elif sys.argv[1] == "stats":
        stats = get_decision_stats()
        print(json.dumps(stats, indent=2))

    elif sys.argv[1] == "patterns":
        patterns = analyze_decision_patterns()
        print(json.dumps(patterns, indent=2))

    elif sys.argv[1] == "sync":
        sync_decision_data()

    elif sys.argv[1] == "nudges":
        nudges = generate_decision_nudges()
        print("\n=== Decision Nudges ===")
        for nudge in nudges:
            print(f"  - {nudge}")
