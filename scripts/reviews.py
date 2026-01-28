"""
Quarterly/Annual Review System - Strategic goal tracking with OKRs.

Provides:
- Life area scoring (Health, Wealth, Relationships, Growth, Purpose)
- OKR tracking with weekly check-ins
- Quarterly reviews with trend analysis
- Annual review and planning templates
- Goal progress visualization data

Data stored in content/reviews/ as markdown files.
Metrics stored in data/review_metrics.json for analysis.
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
REVIEWS_DIR = os.path.join(PROJECT_ROOT, "content", "reviews")
REVIEW_DATA_FILE = os.path.join(PROJECT_ROOT, "data", "review_metrics.json")

# Life areas for holistic review
LIFE_AREAS = [
    {"id": "health", "name": "Health", "description": "Physical fitness, nutrition, sleep, energy"},
    {"id": "wealth", "name": "Wealth", "description": "Income, savings, investments, financial security"},
    {"id": "relationships", "name": "Relationships", "description": "Family, friends, romantic, professional"},
    {"id": "growth", "name": "Growth", "description": "Learning, skills, personal development"},
    {"id": "purpose", "name": "Purpose", "description": "Meaning, contribution, legacy, fulfillment"}
]


def ensure_directories():
    """Create review directory structure."""
    if not os.path.exists(REVIEWS_DIR):
        os.makedirs(REVIEWS_DIR)

    # Create subdirectories
    for subdir in ["quarterly", "annual", "weekly"]:
        path = os.path.join(REVIEWS_DIR, subdir)
        if not os.path.exists(path):
            os.makedirs(path)


def get_current_quarter() -> tuple[int, int]:
    """Get current year and quarter number."""
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return now.year, quarter


def get_quarter_dates(year: int, quarter: int) -> tuple[datetime, datetime]:
    """Get start and end dates for a quarter."""
    start_month = (quarter - 1) * 3 + 1
    start = datetime(year, start_month, 1)

    if quarter == 4:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, start_month + 3, 1) - timedelta(days=1)

    return start, end


def create_quarterly_review_template(year: int, quarter: int) -> str:
    """Create a quarterly review template."""
    start, end = get_quarter_dates(year, quarter)

    template = f'''---
type: quarterly
year: {year}
quarter: {quarter}
period: "{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
created: "{datetime.now().strftime('%Y-%m-%d')}"
status: draft

# Life Area Scores (1-10)
life_areas:
  health: 0
  wealth: 0
  relationships: 0
  growth: 0
  purpose: 0

# Quarter Summary Metrics
metrics:
  weeks_tracked: 0
  goals_completed: 0
  goals_total: 0
  habits_completion_rate: 0
  average_mood: 0
  average_energy: 0
---

# Q{quarter} {year} Review

## Life Area Assessment

### Health (Score: /10)
**Current State:**

**Wins:**
-

**Challenges:**
-

**Next Quarter Focus:**
-

---

### Wealth (Score: /10)
**Current State:**

**Wins:**
-

**Challenges:**
-

**Next Quarter Focus:**
-

---

### Relationships (Score: /10)
**Current State:**

**Wins:**
-

**Challenges:**
-

**Next Quarter Focus:**
-

---

### Growth (Score: /10)
**Current State:**

**Wins:**
-

**Challenges:**
-

**Next Quarter Focus:**
-

---

### Purpose (Score: /10)
**Current State:**

**Wins:**
-

**Challenges:**
-

**Next Quarter Focus:**
-

---

## OKRs Review

### Objective 1:
**Key Results:**
1. [ ] KR1:
2. [ ] KR2:
3. [ ] KR3:

**Progress Notes:**


### Objective 2:
**Key Results:**
1. [ ] KR1:
2. [ ] KR2:
3. [ ] KR3:

**Progress Notes:**


### Objective 3:
**Key Results:**
1. [ ] KR1:
2. [ ] KR2:
3. [ ] KR3:

**Progress Notes:**


---

## Quarter Highlights

### Biggest Wins
1.
2.
3.

### Biggest Lessons
1.
2.
3.

### What Would I Do Differently?


### Gratitude List
-
-
-

---

## Next Quarter Planning

### Top 3 Priorities
1.
2.
3.

### New OKRs

#### Objective 1:
**Key Results:**
1.
2.
3.

#### Objective 2:
**Key Results:**
1.
2.
3.

### Habits to Start/Stop/Continue
**Start:**
-

**Stop:**
-

**Continue:**
-

---

## Notes

'''
    return template


def create_annual_review_template(year: int) -> str:
    """Create an annual review template."""
    template = f'''---
type: annual
year: {year}
created: "{datetime.now().strftime('%Y-%m-%d')}"
status: draft

# Annual Scores (1-10)
life_areas:
  health: 0
  wealth: 0
  relationships: 0
  growth: 0
  purpose: 0

# Year Summary
summary:
  goals_completed: 0
  goals_total: 0
  habits_formed: 0
  books_read: 0
  major_milestones: []
---

# {year} Annual Review

## Year at a Glance

**Theme of the Year:**

**One-Sentence Summary:**

---

## Life Area Deep Dive

### Health Journey
**Where I Started:**

**Where I Ended:**

**Key Milestones:**
-

**Lessons Learned:**
-

---

### Wealth Journey
**Where I Started:**

**Where I Ended:**

**Key Milestones:**
-

**Lessons Learned:**
-

---

### Relationships Journey
**Where I Started:**

**Where I Ended:**

**Key Milestones:**
-

**Lessons Learned:**
-

---

### Growth Journey
**Where I Started:**

**Where I Ended:**

**Key Milestones:**
-

**Lessons Learned:**
-

---

### Purpose Journey
**Where I Started:**

**Where I Ended:**

**Key Milestones:**
-

**Lessons Learned:**
-

---

## Yearly Highlights

### Top 10 Moments
1.
2.
3.
4.
5.
6.
7.
8.
9.
10.

### Biggest Accomplishments
-

### Biggest Failures/Lessons
-

### Books/Content That Changed Me
-

### People Who Made a Difference
-

---

## By the Numbers

| Metric | Start of Year | End of Year | Change |
|--------|---------------|-------------|--------|
| Weight | | | |
| Net Worth | | | |
| Relationships Maintained | | | |
| Skills Acquired | | | |
| Books Read | | | |

---

## Next Year Vision

### Theme for {year + 1}:

### Annual Goals
1.
2.
3.

### Who Do I Want to Become?

### What Habits Will Get Me There?
-

### What Must I Stop Doing?
-

---

## Letter to Future Self

Dear {year + 1} Ryan,

...

'''
    return template


def create_weekly_checkin_template() -> str:
    """Create a weekly check-in template."""
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    year, week_num = now.isocalendar()[:2]

    template = f'''---
type: weekly_checkin
year: {year}
week: {week_num}
period: "{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
created: "{now.strftime('%Y-%m-%d')}"

# Quick Scores (1-10)
scores:
  energy: 0
  focus: 0
  mood: 0
  progress: 0

# OKR Progress
okr_progress:
  - objective: ""
    kr1_percent: 0
    kr2_percent: 0
    kr3_percent: 0
---

# Week {week_num} Check-in

## Quick Pulse (1-10)
- Energy: /10
- Focus: /10
- Mood: /10
- Progress: /10

## OKR Progress

### Objective 1:
- [ ] KR1: % (target: %)
- [ ] KR2: % (target: %)
- [ ] KR3: % (target: %)

**What moved the needle?**


**What blocked progress?**


---

## Week Wins
1.
2.
3.

## Week Challenges
1.
2.
3.

## Key Learnings
-

## Next Week Focus
1.
2.
3.

## Notes

'''
    return template


def create_review(review_type: str, year: int = None, quarter: int = None) -> str:
    """
    Create a new review file.

    Args:
        review_type: 'quarterly', 'annual', or 'weekly'
        year: Year for the review
        quarter: Quarter number (1-4) for quarterly reviews

    Returns:
        Path to created file
    """
    ensure_directories()

    now = datetime.now()
    if year is None:
        year = now.year

    if review_type == "quarterly":
        if quarter is None:
            quarter = (now.month - 1) // 3 + 1
        filename = f"{year}-Q{quarter}.md"
        content = create_quarterly_review_template(year, quarter)
        subdir = "quarterly"

    elif review_type == "annual":
        filename = f"{year}.md"
        content = create_annual_review_template(year)
        subdir = "annual"

    elif review_type == "weekly":
        week_num = now.isocalendar()[1]
        filename = f"{year}-W{week_num:02d}.md"
        content = create_weekly_checkin_template()
        subdir = "weekly"

    else:
        raise ValueError(f"Invalid review type: {review_type}")

    filepath = os.path.join(REVIEWS_DIR, subdir, filename)

    if os.path.exists(filepath):
        print(f"Review already exists: {filepath}")
        return filepath

    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Created review: {filepath}")
    return filepath


def load_review(filepath: str) -> Optional[dict]:
    """Load a review from a markdown file."""
    try:
        post = frontmatter.load(filepath)
        return {
            "metadata": dict(post.metadata),
            "content": post.content,
            "filepath": filepath
        }
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def get_all_reviews(review_type: str = None) -> List[dict]:
    """Get all reviews, optionally filtered by type."""
    reviews = []

    subdirs = [review_type] if review_type else ["quarterly", "annual", "weekly"]

    for subdir in subdirs:
        path = os.path.join(REVIEWS_DIR, subdir)
        if not os.path.exists(path):
            continue

        for filename in os.listdir(path):
            if filename.endswith('.md'):
                filepath = os.path.join(path, filename)
                review = load_review(filepath)
                if review:
                    review["type"] = subdir
                    reviews.append(review)

    return reviews


def calculate_life_area_trends() -> dict:
    """
    Calculate trends for each life area over time.

    Returns:
        dict with trends for each life area
    """
    reviews = get_all_reviews("quarterly")

    if len(reviews) < 2:
        return {"insufficient_data": True}

    # Sort by date
    reviews.sort(key=lambda x: (x["metadata"].get("year", 0), x["metadata"].get("quarter", 0)))

    trends = {}

    for area in LIFE_AREAS:
        area_id = area["id"]
        scores = []

        for review in reviews:
            score = review["metadata"].get("life_areas", {}).get(area_id)
            if score and score > 0:
                scores.append({
                    "period": f"Q{review['metadata'].get('quarter')}/{review['metadata'].get('year')}",
                    "score": score
                })

        if len(scores) >= 2:
            trend = "improving" if scores[-1]["score"] > scores[-2]["score"] else \
                    "declining" if scores[-1]["score"] < scores[-2]["score"] else "stable"
            change = scores[-1]["score"] - scores[-2]["score"]
        else:
            trend = "insufficient_data"
            change = 0

        trends[area_id] = {
            "current": scores[-1]["score"] if scores else None,
            "previous": scores[-2]["score"] if len(scores) >= 2 else None,
            "trend": trend,
            "change": change,
            "history": scores
        }

    return trends


def get_okr_progress() -> List[dict]:
    """
    Get current OKR progress from latest quarterly review.

    Returns:
        List of objective progress dicts
    """
    year, quarter = get_current_quarter()

    filepath = os.path.join(REVIEWS_DIR, "quarterly", f"{year}-Q{quarter}.md")

    if not os.path.exists(filepath):
        return []

    review = load_review(filepath)
    if not review:
        return []

    # Parse OKR progress from content
    content = review["content"]
    objectives = []

    # Find OKR sections
    okr_pattern = r"### Objective (\d+):(.*?)(?=### Objective|\Z)"
    matches = re.findall(okr_pattern, content, re.DOTALL)

    for num, section in matches:
        kr_pattern = r"\[([x ])\] KR\d+:(.*?)(?=\[|\n\n|\Z)"
        krs = re.findall(kr_pattern, section)

        key_results = []
        for checked, kr_text in krs:
            key_results.append({
                "text": kr_text.strip(),
                "completed": checked.lower() == 'x'
            })

        objectives.append({
            "number": int(num),
            "key_results": key_results,
            "completion_rate": sum(1 for kr in key_results if kr["completed"]) / len(key_results) if key_results else 0
        })

    return objectives


def get_weekly_scores_trend(weeks: int = 4) -> List[dict]:
    """
    Get weekly check-in scores for trend analysis.

    Args:
        weeks: Number of weeks to look back

    Returns:
        List of weekly score dicts
    """
    reviews = get_all_reviews("weekly")

    # Sort by date descending
    reviews.sort(key=lambda x: (x["metadata"].get("year", 0), x["metadata"].get("week", 0)), reverse=True)

    trend = []
    for review in reviews[:weeks]:
        meta = review["metadata"]
        scores = meta.get("scores", {})

        trend.append({
            "week": f"W{meta.get('week')}",
            "year": meta.get("year"),
            "energy": scores.get("energy", 0),
            "focus": scores.get("focus", 0),
            "mood": scores.get("mood", 0),
            "progress": scores.get("progress", 0),
            "average": sum(scores.values()) / len(scores) if scores else 0
        })

    return list(reversed(trend))


def get_review_summary() -> dict:
    """
    Get summary of review status for dashboard.

    Returns:
        dict with current period info, life areas, OKR progress
    """
    year, quarter = get_current_quarter()
    now = datetime.now()
    week_num = now.isocalendar()[1]

    # Check if current reviews exist
    quarterly_path = os.path.join(REVIEWS_DIR, "quarterly", f"{year}-Q{quarter}.md")
    weekly_path = os.path.join(REVIEWS_DIR, "weekly", f"{year}-W{week_num:02d}.md")

    quarterly_exists = os.path.exists(quarterly_path)
    weekly_exists = os.path.exists(weekly_path)

    # Get life area trends
    trends = calculate_life_area_trends()

    # Get OKR progress
    okrs = get_okr_progress()

    # Get weekly trend
    weekly_trend = get_weekly_scores_trend()

    # Calculate days until quarter end
    _, quarter_end = get_quarter_dates(year, quarter)
    days_remaining = (quarter_end - now).days

    return {
        "current_quarter": f"Q{quarter} {year}",
        "current_week": f"W{week_num}",
        "days_until_quarter_end": days_remaining,
        "quarterly_review_exists": quarterly_exists,
        "weekly_checkin_exists": weekly_exists,
        "life_area_trends": trends if not trends.get("insufficient_data") else None,
        "okr_progress": okrs,
        "weekly_trend": weekly_trend,
        "needs_weekly_checkin": not weekly_exists,
        "needs_quarterly_review": not quarterly_exists and days_remaining <= 7
    }


def generate_review_nudges() -> List[str]:
    """Generate review-related nudges for daily briefing."""
    nudges = []
    summary = get_review_summary()

    if summary["needs_weekly_checkin"]:
        nudges.append("Complete weekly check-in")

    if summary["needs_quarterly_review"]:
        nudges.append(f"Quarterly review needed - {summary['days_until_quarter_end']} days left in Q")

    # Check OKR progress
    for okr in summary.get("okr_progress", []):
        if okr["completion_rate"] < 0.5:
            nudges.append(f"Objective {okr['number']} at {int(okr['completion_rate']*100)}% - needs attention")

    return nudges


def sync_review_data():
    """Sync review data to JSON for analysis."""
    summary = get_review_summary()

    data_dir = os.path.dirname(REVIEW_DATA_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    data = {
        "version": "1.0",
        "synced_at": datetime.now().isoformat(),
        "summary": summary
    }

    with open(REVIEW_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Review data synced to {REVIEW_DATA_FILE}")


if __name__ == "__main__":
    import sys

    ensure_directories()

    if len(sys.argv) < 2:
        # Show summary
        summary = get_review_summary()
        print(f"\n=== Review Status ===")
        print(f"Quarter: {summary['current_quarter']} ({summary['days_until_quarter_end']} days remaining)")
        print(f"Week: {summary['current_week']}")
        print(f"Quarterly review: {'exists' if summary['quarterly_review_exists'] else 'NEEDED'}")
        print(f"Weekly check-in: {'exists' if summary['weekly_checkin_exists'] else 'NEEDED'}")

        if summary.get("life_area_trends"):
            print("\nLife Area Trends:")
            for area_id, trend in summary["life_area_trends"].items():
                if trend["current"]:
                    print(f"  {area_id}: {trend['current']}/10 ({trend['trend']})")

    elif sys.argv[1] == "create":
        if len(sys.argv) < 3:
            print("Usage: reviews.py create [quarterly|annual|weekly]")
        else:
            review_type = sys.argv[2]
            create_review(review_type)

    elif sys.argv[1] == "sync":
        sync_review_data()

    elif sys.argv[1] == "nudges":
        nudges = generate_review_nudges()
        print("\n=== Review Nudges ===")
        for nudge in nudges:
            print(f"  - {nudge}")
