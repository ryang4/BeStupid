# /plan-week - Weekly Protocol Generation

Generates the next week's training and work protocol.

## Trigger Phrases
- "Create next week's protocol"
- "Plan my week"
- "Generate weekly protocol"
- "/plan-week"

## When to Use

- Current week's protocol is ending (Saturday/Sunday)
- Starting a new training block
- User explicitly requests protocol generation
- Need to regenerate current week due to changes

## Execution

### Generate Next Week's Protocol (default)
```bash
cd /Users/ryang4/Projects/BeStupid && python scripts/weekly_planner.py
```

### Regenerate Current Week
```bash
cd /Users/ryang4/Projects/BeStupid && python scripts/weekly_planner.py --this-week
```

### Finalize a Draft Protocol
```bash
cd /Users/ryang4/Projects/BeStupid && python scripts/weekly_planner.py --finalize
```

## What the Script Does

The `weekly_planner.py` script:
1. Reads `content/config/ryan.md` for goals, training philosophy, and adjustment rules
2. Reads last week's protocol and all daily logs
3. Calculates compliance rate and identifies patterns
4. Generates new protocol via LLM with progressive adjustments
5. Writes to `content/config/protocol_{next_monday}_DRAFT.md`

## Adjustment Rules

From `ryan.md`, the script applies these rules:

| Compliance | Sleep Avg | Action |
|------------|-----------|--------|
| >85% | >7 hrs | Increase volume 5-10% |
| 70-85% | Any | Hold steady |
| <70% | Any | Reduce volume 10-20% |
| Any | <6.5 hrs | Reduce volume, add rest |

## Protocol Structure

Generated protocols include:

```markdown
---
title: "Protocol YYYY-WXX: [Phase Name]"
date: YYYY-MM-DD
week_number: WXX
tags: ["protocol"]
phase: "Base Building"
focus: "Aerobic base + consistency"
target_compliance: 85%
---

## Weekly Schedule
| Day | Morning | Afternoon/Evening |
|-----|---------|-------------------|
| Mon | Rest | Strength: Upper |
| Tue | Swim 1500m | - |
| ... | ... | ... |

## Training Goals
- Swim: X meters total
- Bike: X minutes total
- Run: X miles total
- Strength: X sessions

## Startup Goals
- Deep work: X hours
- Content: X pieces

## Weekly Targets
[Volume metrics]

## AI Rationale
[Why this protocol was designed this way]
```

## Data Sources

- Profile: `content/config/ryan.md` → goals, philosophy, rules
- Last protocol: `content/config/protocol_*.md` (most recent)
- Last week's logs: `content/logs/*.md` for Mon-Sun
- Metrics: `data/daily_metrics.json` → compliance data
- Projects: `content/projects/*.md` → startup goals to incorporate

## Post-Generation

After protocol is created:
1. Inform user it's in DRAFT state
2. Summarize key changes from last week
3. Prompt to review and either:
   - Edit the draft manually
   - Run `--finalize` to approve it
