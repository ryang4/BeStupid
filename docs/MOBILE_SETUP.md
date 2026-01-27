# Mobile Setup Guide

This guide walks you through setting up the BeStupid daily planning system on your iPhone using Obsidian and Working Copy.

## Overview

```
5:00 AM  → GitHub Action generates today's log
6:00 AM  → iOS Shortcut pulls latest + opens Obsidian
All Day  → Edit daily log on phone (inline fields)
9:00 PM  → iOS Shortcut commits + pushes changes
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

## Step 2: Working Copy (Git on iPhone)

[Working Copy](https://apps.apple.com/app/working-copy/id896694807) is a Git client for iOS. Free for pulling; one-time purchase for pushing.

### Clone the Repository

1. Install Working Copy from App Store
2. Tap **+** > **Clone repository**
3. Sign in with GitHub
4. Select your BeStupid repo
5. Wait for clone to complete

### Enable Obsidian Access

1. In Working Copy, open the repo
2. Tap the **⚙️ gear icon** (top right)
3. Tap **Share as Linked Repository**
4. This makes the folder visible to Obsidian

---

## Step 3: Obsidian Setup

### Install and Configure

1. Install [Obsidian](https://apps.apple.com/app/obsidian/id1557175442) from App Store
2. Open Obsidian
3. Tap **Open folder as vault**
4. Navigate to: Working Copy > BeStupid > **content**
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

```
Action 1: Run Working Copy Pull
  - Repository: BeStupid
  - Remote: origin

Action 2: Open URL
  - URL: obsidian://open?vault=content&file=logs/[Current Date]

  (Use "Format Date" action to get YYYY-MM-DD format)
```

**Full shortcut:**

```
1. [Date] → Format Date (Custom: yyyy-MM-dd) → Save to "today"
2. [Working Copy] → Pull Repository "BeStupid"
3. [URL] → Open URL "obsidian://open?vault=content&file=logs/[today]"
```

### Evening Push Shortcut

Commits and pushes your daily log edits.

```
1. [Working Copy] → Stage for Commit
   - Repository: BeStupid
   - Path: content/logs/

2. [Working Copy] → Commit Repository
   - Repository: BeStupid
   - Message: "Daily log update"

3. [Working Copy] → Push Repository
   - Repository: BeStupid
```

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

### Working Copy won't push

- Ensure you have the paid version (or use GitHub web)
- Check repository permissions
- Verify you're on the `main` branch

### Obsidian can't find vault

- Re-link repository in Working Copy settings
- Ensure vault path is `content/` not root

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
