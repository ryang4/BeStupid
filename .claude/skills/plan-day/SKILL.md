# /plan-day - Daily Log Generation

Generates today's daily log with AI-powered briefing and adaptive todos.

## Trigger Phrases
- "Create today's log"
- "Plan my day"
- "Generate daily briefing"
- "/plan-day"

## Prerequisites

Before generating, check:

1. **Today's log doesn't already exist**
   - Check: `content/logs/{YYYY-MM-DD}.md`
   - If exists: Inform user and offer to show current status with `/brain` instead

2. **Active protocol exists**
   - Find: `content/config/protocol_*.md` for Monday of current week
   - If missing: Prompt user to run `/plan-week` first

## Execution

Run the daily planner script:

```bash
cd /Users/ryang4/Projects/BeStupid && python scripts/daily_planner.py
```

After the script completes:
1. Read the generated log at `content/logs/{YYYY-MM-DD}.md`
2. Summarize: workout type, todo count, any briefing highlights

## What the Script Does

The `daily_planner.py` script:
1. Reads the active protocol for today's workout
2. Gets yesterday's incomplete todos and "Top 3 for Tomorrow"
3. Analyzes 7-day metrics for the AI briefing
4. Generates the daily briefing via LLM
5. Renders the template with all sections
6. Writes to `content/logs/{YYYY-MM-DD}.md`

## Manual Generation Fallback

If the script fails, generate manually using this structure:

```markdown
---
title: "YYYY-MM-DD: [Workout Type]"
date: YYYY-MM-DD
tags: ["log"]
---

## Planned Workout
[Extract from protocol for today's day of week]

## Daily Briefing
[Generate based on recent metrics and todos]

## Today's Todos
- [ ] Perform today's workout
- [ ] [Rollover todo 1 from yesterday]
- [ ] [Top 3 item 1]
- [ ] [Top 3 item 2]

## Daily Habits
[Copy habit list from content/config/habits.md]

## Quick Log
Weight::
Sleep::
Sleep_Quality::
Mood_AM::
Mood_PM::

## Strength Log / Training Output
[Based on workout type]

## Fuel Log
Calories::
Protein::
Notes::

## Top 3 for Tomorrow
1.
2.
3.
```

## Data Sources for Manual Generation

- Yesterday's log: `content/logs/{yesterday}.md` → incomplete todos, Top 3
- Active protocol: `content/config/protocol_*.md` → today's workout
- Habits config: `content/config/habits.md` → habit checklist
- Metrics JSON: `data/daily_metrics.json` → 7-day averages for briefing

## Post-Generation

After log is created:
1. Remind user to fill in Quick Log metrics throughout the day
2. Suggest running `/brain` for current priorities
