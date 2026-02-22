# Mobile Setup Guide

This guide walks you through setting up the BeStupid daily planning system on your iPhone using Obsidian and a-shell.

> Status update (2026-02-22): GitHub Actions automations were removed from this
> repo. Use local or container scheduler jobs (`.bestupid-private/cron_jobs.json`)
> for automatic reminders/planner runs.

## Overview

```
11:00 PM → Scheduler generates tomorrow's log (`daily_planner` job)
6:00 AM  → iOS Shortcut (a-shell) pulls latest + opens Obsidian
All Day  → Edit daily log on phone (inline fields)
9:00 PM  → iOS Shortcut (a-shell) commits + pushes changes
```

---

## Prerequisites

- iPhone with iOS 15+
- GitHub account with this repo
- Hugging Face account (free) for LLM API

---

## Step 1: GitHub Setup

### Add HF_TOKEN Secret

1. Go to [Hugging Face Settings > Access Tokens](https://huggingface.co/settings/tokens)
2. Create a new token with "Read" permissions
3. Go to your GitHub repo > **Settings** > **Secrets and variables** > **Actions**
4. Click **New repository secret**
5. Name: `HF_TOKEN`
6. Value: paste your Hugging Face token
7. Click **Add secret**

### Verify GitHub Actions

1. Go to **Actions** tab in your repo
2. Find "Generate Daily Log" workflow
3. Click **Run workflow** > **Run workflow** to test
4. Check that a new log appears in `content/logs/`

---

## Step 2: a-shell (Free Git on iPhone)

[a-shell](https://apps.apple.com/us/app/a-shell/id1473805438) is a free terminal app for iOS with full Git support. Unlike Working Copy, it's 100% free including push operations.

### Install and Setup

1. Install **a-shell** from App Store (free)
2. Open a-shell
3. Configure Git credentials:

   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```

### Clone the Repository

1. In a-shell, run:

   ```bash
   cd Documents
   git clone https://github.com/YOUR_USERNAME/BeStupid.git
   ```

2. When prompted, enter your GitHub username
3. For password, use a [Personal Access Token](https://github.com/settings/tokens) (not your GitHub password)
   - Create token with `repo` scope
   - Save it securely (you'll need it for push operations)

### Setup GitHub Authentication

To avoid entering credentials every time, configure credential caching:

```bash
cd Documents/BeStupid
git config credential.helper store
```

The next time you push, enter your token - it will be saved for future operations.

---

## Step 3: Obsidian Setup

### Install and Configure

1. Install [Obsidian](https://apps.apple.com/app/obsidian/id1557175442) from App Store
2. Open Obsidian
3. Tap **Open folder as vault**
4. Navigate to: On My iPhone > a-shell > Documents > BeStupid > **content**
5. Tap **Open**

### Enable Mobile CSS Snippet

The `.obsidian/snippets/` folder syncs via git. To enable the mobile-friendly CSS:

1. In Obsidian, open **Settings** (gear icon)
2. Go to **Appearance** > **CSS snippets**
3. Tap the reload button (circular arrow) to refresh
4. Toggle **mobile** to enable it
5. Close settings

> **Note:** Other `.obsidian/` files (workspace, plugins, cache) are gitignored to prevent sync conflicts. Each device configures Obsidian independently.

### Install Recommended Plugins (Optional)

For better mobile experience:

1. **Settings** > **Community plugins** > **Turn on community plugins**
2. Browse and install:
   - **Dataview** - Query inline fields
   - **QuickAdd** - One-tap logging macros

---

## Step 4: iOS Shortcuts

Create these shortcuts for automated workflows.

### Morning Pull Shortcut

Creates a shortcut that pulls latest changes and opens today's note.

1. Open **Shortcuts** app
2. Tap **+** to create new shortcut
3. Add these actions:

**Full shortcut:**

```
1. [Date] → Format Date (Custom: yyyy-MM-dd) → Save to "today"

2. [Scripting] → Run Shell Script
   - Shell: a-shell
   - Script:
     cd Documents/BeStupid
     git pull origin main
   - Pass Input: No

3. [URL] → Open URL "obsidian://open?vault=content&file=logs/[today]"
```

**Tip:** Search for "Run Shell Script" in Shortcuts, then select "a-shell" as the shell option.

### Evening Push Shortcut

Commits and pushes your daily log edits.

1. Open **Shortcuts** app
2. Create new shortcut with:

```
1. [Date] → Format Date (Custom: yyyy-MM-dd) → Save to "today"

2. [Scripting] → Run Shell Script
   - Shell: a-shell
   - Script:
     cd Documents/BeStupid
     git add content/logs/
     git commit -m "Daily log update: [today]"
     git push origin main
   - Pass Input: No

3. [Notification] → Show Notification
   - Title: "Daily log synced"
   - Body: "Changes pushed to GitHub"
```

**Note:** The commit message will include today's date for easier tracking in Git history.

### Notification Shortcuts

Create time-based automations:

1. Open **Shortcuts** > **Automation** tab
2. Tap **+** > **Create Personal Automation**
3. Select **Time of Day**

| Time | Notification | Action |
|------|-------------|--------|
| 6:00 AM | "Morning: Log weight & mood" | Run Morning Pull shortcut |
| 12:00 PM | "Midday: Log lunch" | Open Obsidian URL |
| 9:00 PM | "Evening: Complete habits, Top 3" | Run Evening Push shortcut |

---

## Step 5: Daily Workflow

### Morning (6 AM)

1. Notification triggers Morning Pull shortcut
2. Today's log opens automatically
3. Fill in Quick Log section:
   ```
   Weight:: 185
   Sleep:: 7:30
   Mood_AM:: 7
   ```

### Throughout Day

- Log food in Fuel Log section
- Check off completed todos and habits
- Use calorie estimator (see below)

### Evening (9 PM)

1. Complete remaining habits
2. Fill in Top 3 for Tomorrow
3. Fill in `Mood_PM::`
4. Notification triggers Evening Push shortcut

---

## On-Demand Calorie Counter

### Option A: GitHub Actions (Recommended)

1. Go to repo **Actions** > **Estimate Calories**
2. Click **Run workflow**
3. Enter food description (e.g., "2 eggs with toast and avocado")
4. Check **Append to today's log** if desired
5. View results in workflow summary

### Option B: iOS Shortcut

Create a shortcut that calls the GitHub API:

```
1. [Ask for Input] → "What did you eat?"
2. [Get Contents of URL]
   - URL: https://api.github.com/repos/YOUR_USERNAME/BeStupid/actions/workflows/calorie-estimate.yml/dispatches
   - Method: POST
   - Headers:
     - Authorization: Bearer [YOUR_GITHUB_TOKEN]
     - Accept: application/vnd.github.v3+json
   - Body: {"ref": "main", "inputs": {"food": "[Input]"}}
3. [Show Notification] → "Estimating calories..."
```

Note: Results appear in GitHub Actions, not directly in the shortcut.

---

## Troubleshooting

### Log not appearing

- Check GitHub Actions ran successfully
- Verify HF_TOKEN secret is set
- Try manual workflow dispatch

### Git authentication fails

- Make sure you're using a GitHub Personal Access Token, not your password
- Verify the token has `repo` scope enabled
- Re-run credential setup: `git config credential.helper store`

### Push fails with "permission denied"

- Check your GitHub token hasn't expired
- Verify you have write access to the repository
- Try pulling first: `git pull origin main`

### Obsidian can't find vault

- Make sure a-shell cloned to `Documents/BeStupid`
- Ensure vault path is pointing to the `content/` folder
- Check Files app to verify the folder exists

### Shortcuts not working

- Verify a-shell is installed and repository is cloned
- Test the git commands manually in a-shell first
- Make sure "Run Shell Script" action is set to use "a-shell" not "sh"

### CSS snippet not working

- Check file is in `.obsidian/snippets/mobile.css`
- Ensure snippet is toggled ON in settings
- Restart Obsidian

---

## File Locations

| What | Where |
|------|-------|
| Daily logs | `content/logs/YYYY-MM-DD.md` |
| Protocols | `content/config/protocol_YYYY-MM-DD.md` |
| Habits config | `content/config/habits.md` |
| Metrics data | `data/daily_metrics.json` |
| Mobile CSS | `.obsidian/snippets/mobile.css` |

---

## Deep Links

Use these Obsidian URLs in shortcuts:

| Action | URL |
|--------|-----|
| Open today's log | `obsidian://open?vault=content&file=logs/2026-01-20` |
| Open vault | `obsidian://open?vault=content` |
| Search | `obsidian://search?vault=content&query=workout` |

Replace `2026-01-20` with dynamic date using Shortcuts "Format Date" action.
