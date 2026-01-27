# /project - Project Deep Dive and Search

Provides deep-dive context on projects and searches historical logs.

## Trigger Phrases
- "Tell me about the startup project"
- "Show me half-ironman progress"
- "Search logs for 'swim'"
- "What have I done on ML learning?"
- "/project startup"
- "/project search [query]"

## Available Projects

| Name | File | Description |
|------|------|-------------|
| startup | `content/projects/startup.md` | Daily Planning Product MVP |
| half-ironman | `content/projects/half-ironman.md` | 2026 Race Goal |
| ml-engineering | `content/projects/ml-engineering.md` | ML/AI Learning Journey |

## Project Deep Dive

When user asks about a specific project:

### Step 1: Read Project File
- Path: `content/projects/{project_name}.md`
- Parse YAML frontmatter for structured data:
  - `status`: active/completed
  - `target_date`: goal date
  - `priority`: 1-5
  - `milestones`: array of milestone objects
  - `blockers`: array of blocking issues
  - `next_actions`: array of actionable items
  - `weekly_targets`: domain-specific goals

### Step 2: Search Recent Logs
- Scan `content/logs/*.md` for the past 14 days
- Find lines containing the project name or related keywords
- Extract date and context for each mention

### Step 3: Generate Report

```markdown
## Project: {title}

**Status**: {status}
**Target Date**: {target_date}
**Priority**: {priority}

### Current Milestones
| Milestone | Target | Status |
|-----------|--------|--------|
| {name} | {target} | {status} |

### Blockers
- {blocker 1}
- {blocker 2}

### Next Actions
1. {action 1}
2. {action 2}

### Weekly Targets
- {key}: {value}

### Recent Activity (past 14 days)
**{date}**
- {matching line context}

**{date}**
- {matching line context}
```

## Log Search

When user wants to search across logs:

### Step 1: Parse Query
- Extract search term from user input
- Keywords to search: project names, workout types, metrics, status words

### Step 2: Scan Logs
- Path pattern: `content/logs/*.md`
- Search range: Past 30 days by default
- Case-insensitive search
- Return up to 10 most recent matches

### Step 3: Format Results

```markdown
## Search Results for "{query}"

Found {count} matches in the past 30 days:

**{date}**
> {matching line with context}

**{date}**
> {matching line with context}
```

## Search Tips

Common search queries:
- Project names: "startup", "half-ironman", "ml"
- Workout types: "swim", "bike", "run", "strength"
- Metrics: "sleep", "weight", "mood"
- Status: "blocker", "completed", "missed"
- Training: "PR", "easy", "tempo", "intervals"

## Example Usage

**Project query**:
```
User: "How's the startup project going?"
Action: Read content/projects/startup.md, search logs for "startup"
Output: Project report with milestones, blockers, and recent log mentions
```

**Search query**:
```
User: "Search for swim workouts"
Action: Grep through content/logs/*.md for "swim"
Output: List of dates with swim-related entries
```

**Combined query**:
```
User: "What progress on half-ironman this week?"
Action: Read project file + search last 7 days of logs
Output: Project status + this week's training activity
```
