# /capture - Quick Capture and Metric Logging

Quickly capture ideas, tasks, or metrics without breaking flow state.

## Trigger Phrases
- "Add to inbox: [idea]"
- "Log my weight: 244"
- "Capture: [note]"
- "Remember this: [text]"
- "Log sleep 7.5"
- "Mood is 8"
- "/capture [text]"

## Capture Types

### 1. Inbox Capture (Ideas/Tasks/Notes)

**Destination**: `~/.bestupid-private/inbox.md`

**Format**: Append timestamped entry
```markdown
- [YYYY-MM-DD HH:MM] {user's text}
```

**Action**: Read the file, append the new entry after the `<!-- New items -->` comment line.

### 2. Metric Logging

**Destination**: `content/logs/{YYYY-MM-DD}.md` (today's log)

**Supported Metrics**:
| Keyword | Field | Example |
|---------|-------|---------|
| weight | Weight:: | "log weight 243" |
| sleep | Sleep:: | "sleep 7.5" |
| sleep_quality | Sleep_Quality:: | "sleep quality 8" |
| mood, mood_am | Mood_AM:: | "mood 7" |
| mood_pm | Mood_PM:: | "mood pm 6" |

**Action**:
1. Read today's log
2. Find the line containing the metric field (e.g., `Weight::`)
3. Replace the line with `Weight:: {value}`
4. Save the file

### 3. Training Output Logging

**Destination**: `content/logs/{YYYY-MM-DD}.md`

**Supported Fields**:
| Keyword | Field | Example |
|---------|-------|---------|
| swim | Swim:: | "swim 1500m in 32:00" |
| bike | Bike:: | "bike 45 min" |
| run | Run:: | "run 4.5 miles in 42:30" |
| avg_hr, heart rate | Avg_HR:: | "avg hr 145" |

## Parsing Logic

1. Check if input contains metric keywords + a number
   - Yes → Metric logging
   - No → Inbox capture

2. For metric logging:
   - Extract the metric type and value
   - Verify today's log exists (if not, suggest `/plan-day` first)
   - Update the specific field

## Examples

**Inbox Capture**:
```
User: "capture: review PR for auth changes"
Action: Append to ~/.bestupid-private/inbox.md:
  - [2026-01-23 14:30] review PR for auth changes
Response: "Captured to inbox: review PR for auth changes"
```

**Weight Logging**:
```
User: "log weight 243"
Action: Update content/logs/2026-01-23.md:
  Weight:: 243
Response: "Logged weight: 243 lbs"
```

**Sleep Logging**:
```
User: "sleep was 7.5 hours"
Action: Update content/logs/2026-01-23.md:
  Sleep:: 7.5
Response: "Logged sleep: 7.5 hours"
```

**Mood Logging**:
```
User: "feeling good, mood is 8"
Action: Update content/logs/2026-01-23.md:
  Mood_AM:: 8
Response: "Logged morning mood: 8/10"
```

## Error Handling

- If today's log doesn't exist for metric logging: "Today's log doesn't exist yet. Run `/plan-day` first, or I can capture this to your inbox instead."
- If inbox file doesn't exist: Create it with header template
- If metric field not found in log: Add it to the Quick Log section
