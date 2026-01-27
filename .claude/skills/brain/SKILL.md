# /brain - Unified Dashboard and Status

Provides a unified view of current status, priorities, and context for decision-making.

## Trigger Phrases
- "What should I focus on?"
- "Show me my status"
- "What's happening today?"
- "/brain"

## Data Sources

Read these files in order:

### 1. Today's Daily Log
- Path: `content/logs/{YYYY-MM-DD}.md` (today's date)
- Extract: Incomplete todos (unchecked `- [ ]`), workout status, inline metrics (Weight::, Sleep::, Mood_AM::)

### 2. Recent Logs (last 3 days)
- Paths: `content/logs/{date}.md` for yesterday, 2 days ago, 3 days ago
- Extract: Sleep hours, mood values, todo completion rates

### 3. Active Protocol
- Find: `content/config/protocol_*.md` where date is the Monday of current week
- Extract: Today's planned workout (based on day of week), weekly targets

### 4. Profile
- Path: `content/config/ryan.md`
- Extract: Current goals, red flag thresholds, priorities

### 5. Metrics JSON
- Path: `data/daily_metrics.json`
- Extract: 7-day rolling averages for sleep, mood

### 6. Private Data (if accessible)
- `~/.bestupid-private/calendar.json` - upcoming events
- `~/.bestupid-private/inbox.md` - pending inbox items count
- `~/.bestupid-private/business_metrics.json` - MRR, user counts

### 7. Project Files
- Path: `content/projects/*.md`
- Extract: Any blockers listed in YAML frontmatter

## Health Check Logic

Apply these rules to detect issues:

1. **Sleep debt**: If 7-day average sleep < 6.5 hours → "Sleep debt detected. Consider rest day or reduced intensity."
2. **Mood warning**: If Mood_AM < 5 for 3+ consecutive days → "Mood trending low. Check stress and recovery."
3. **Todo overload**: If completion rate < 50% over last 3 days → "Completion rate low. Consider reducing todo count."

## Output Format

Generate a concise briefing:

```markdown
## Today's Priorities
1. [Most urgent/important task from incomplete todos or protocol]
2. [Second priority]
3. [Third priority]

## Health Check
- Sleep: {last_night} hrs (7-day avg: {avg} hrs) {FLAG if issue}
- Mood: {today_am}/10 {FLAG if trending low}
- {Any health warnings}

## Today's Workout
{Extract from protocol for today's day of week}

## Upcoming
- {Calendar events if available}
- {Inbox: X pending items}

## Blockers
- {Any blockers from project files}
- {Incomplete rollover todos from yesterday}
```

## Priority Logic

1. Rollover incomplete todos from yesterday get elevated
2. "Top 3 for Tomorrow" from yesterday's log become today's priorities
3. Workout from protocol is always included if not completed
4. Project blockers are flagged for attention
