# Consolidate Old Tools into V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Port all 17 missing tools from the old `tools.py` into `tools_v2.py` so the bot has one unified tool system with full capabilities.

**Architecture:** Add tool definitions and implementations directly into `tools_v2.py`, reusing the existing path security helpers and script execution patterns from `tools.py`. The v2 tools (day snapshot, habits, open loops, memory review) stay as-is. Old tool implementations are copied with minimal changes — just adapted to match v2's `execute_tool(name, inputs, chat_id)` async signature.

**Tech Stack:** Python 3.12, Anthropic API tool-use format, subprocess for script execution, pathlib for file ops.

---

## Context for the Engineer

### File Layout (inside Docker container)
- `/app/*.py` — bot code (copied from `telegram-bot/`)
- `/app/v2/` — v2 state management (copied from `telegram-bot/v2/`)
- `/project/` — full repo mount (read-write), includes `scripts/`, `content/`, `memory/`, `data/`, `.bestupid-private/`
- `PROJECT_ROOT` env var = `/project`
- `HISTORY_DIR` env var = `/project/.bestupid-private`

### Key Constants Already in v2
- `tools_v2.py` already imports from `v2.bootstrap` and `v2.app.timezone_resolver`
- `claude_client.py` imports `TOOLS` and `execute_tool` from `tools_v2`

### What We're Porting (17 tools, grouped into 5 tasks)

**Group 1 — File Operations:** `read_file`, `write_file`, `list_files`, `grep_files`
**Group 2 — System/Git:** `get_system_status`, `get_current_datetime`, `check_git_health`, `sync_with_remote`
**Group 3 — Planners/Brain:** `run_daily_planner`, `run_weekly_planner`, `get_brain_status`, `capture_to_inbox`
**Group 4 — Search/Knowledge:** `search_logs`, `search_conversation_history`, `fact_check`, `semantic_search`, `ingest_content`, `explore_connections`, `brain_stats`
**Group 5 — Scripts/Cron/Policy/Nutrition:** `manage_cron`, `run_script`, `run_memory_command`, `get_agent_policy`, `self_update_policy`, `log_food`, `get_nutrition_totals`

---

### Task 1: Add path security helpers and constants to tools_v2.py

**Files:**
- Modify: `telegram-bot/tools_v2.py`

**Step 1: Add imports and constants**

At the top of `tools_v2.py`, after existing imports, add:

```python
import json
import os
import re
import shlex
import subprocess
import sys
import time as time_module
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).parent.parent))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
REPO_ROOT = PROJECT_ROOT
PRIVATE_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))

BLOCKED_PATTERNS = [".env", ".git/", ".git\\", "__pycache__"]
```

**Step 2: Add path security functions**

After the constants, add:

```python
def _default_readable_prefixes() -> list[Path]:
    return [
        REPO_ROOT / "content",
        REPO_ROOT / "memory",
        REPO_ROOT / "scripts",
        REPO_ROOT / "telegram-bot",
        REPO_ROOT / "logs",
        REPO_ROOT / "data",
        REPO_ROOT / "docs",
        PRIVATE_DIR,
    ]

def _default_writable_prefixes() -> list[Path]:
    return [
        REPO_ROOT / "content" / "logs",
        REPO_ROOT / "memory",
        REPO_ROOT / "scripts",
        REPO_ROOT / "logs",
        PRIVATE_DIR,
    ]

def _is_path_blocked(path: Path) -> bool:
    s = str(path)
    return any(pat in s for pat in BLOCKED_PATTERNS)

def _check_readable(path: Path) -> str | None:
    resolved = path.resolve()
    if _is_path_blocked(resolved):
        return f"Access denied: {path}"
    for prefix in _default_readable_prefixes():
        try:
            resolved.relative_to(prefix.resolve())
            return None
        except ValueError:
            continue
    return f"Access denied: {path} is not in an allowed read path"

def _check_writable(path: Path) -> str | None:
    resolved = path.resolve()
    if _is_path_blocked(resolved):
        return f"Access denied: {path}"
    for prefix in _default_writable_prefixes():
        try:
            resolved.relative_to(prefix.resolve())
            return None
        except ValueError:
            continue
    return f"Access denied: {path} is not in an allowed write path"
```

**Step 3: Add cron constants**

```python
ALLOWED_CRON_COMMANDS = {
    "morning_briefing": "cd /project && python scripts/send_routine_reminder.py morning",
    "evening_reminder": "cd /project && python scripts/send_routine_reminder.py evening_start",
    "evening_screens": "cd /project && python scripts/send_routine_reminder.py evening_screens",
    "evening_bed": "cd /project && python scripts/send_routine_reminder.py evening_bed",
    "daily_planner": "cd /project && python scripts/daily_planner.py",
    "auto_backup": "cd /project && python scripts/robust_git_backup.py",
    "brain_pattern_detection": "cd /project && python scripts/brain_db.py patterns",
}

_CRON_SCHEDULE_RE = re.compile(r'^[\d\*/,\-]+(\s+[\d\*/,\-]+){4}$')

CRON_CONFIG = PRIVATE_DIR / "cron_jobs.json"

_GREP_EXCLUDE = {".git", ".env", "node_modules", "__pycache__"}
```

**Step 4: Verify no syntax errors**

Run: `cd /Users/ryang4/Projects/BeStupid/telegram-bot && python -c "import tools_v2; print(f'{len(tools_v2.TOOLS)} tools loaded')"`
Expected: `10 tools loaded`

**Step 5: Commit**

```bash
git add telegram-bot/tools_v2.py
git commit -m "feat: add path security helpers and constants to tools_v2"
```

---

### Task 2: Add file operation tools (read_file, write_file, list_files, grep_files)

**Files:**
- Modify: `telegram-bot/tools_v2.py`
- Test: `telegram-bot/tests/test_v2_core.py`

**Step 1: Write failing tests**

Add to `test_v2_core.py`:

```python
class TestFileOpsV2:
    """Tests for file operation tools ported to v2."""

    def test_read_file_success(self, tmp_path, monkeypatch):
        import tools_v2
        monkeypatch.setattr(tools_v2, "REPO_ROOT", tmp_path)
        content_dir = tmp_path / "content" / "logs"
        content_dir.mkdir(parents=True)
        test_file = content_dir / "test.md"
        test_file.write_text("hello world")
        monkeypatch.setattr(tools_v2, "_default_readable_prefixes", lambda: [tmp_path / "content"])
        result = tools_v2.read_file("content/logs/test.md")
        assert result == "hello world"

    def test_read_file_blocked(self, tmp_path, monkeypatch):
        import tools_v2
        monkeypatch.setattr(tools_v2, "REPO_ROOT", tmp_path)
        result = tools_v2.read_file(".env")
        assert "Access denied" in result

    def test_write_file_atomic(self, tmp_path, monkeypatch):
        import tools_v2
        monkeypatch.setattr(tools_v2, "REPO_ROOT", tmp_path)
        logs_dir = tmp_path / "content" / "logs"
        logs_dir.mkdir(parents=True)
        monkeypatch.setattr(tools_v2, "_default_writable_prefixes", lambda: [logs_dir])
        result = tools_v2.write_file("content/logs/test.md", "new content")
        assert "Wrote" in result
        assert (logs_dir / "test.md").read_text() == "new content"
        assert not (logs_dir / "test.tmp").exists()  # tmp cleaned up

    def test_list_files(self, tmp_path, monkeypatch):
        import tools_v2
        monkeypatch.setattr(tools_v2, "REPO_ROOT", tmp_path)
        d = tmp_path / "content" / "logs"
        d.mkdir(parents=True)
        (d / "a.md").write_text("a")
        (d / "b.md").write_text("b")
        result = tools_v2.list_files("content/logs")
        assert "a.md" in result
        assert "b.md" in result

    def test_grep_files(self, tmp_path, monkeypatch):
        import tools_v2
        monkeypatch.setattr(tools_v2, "REPO_ROOT", tmp_path)
        d = tmp_path / "content"
        d.mkdir(parents=True)
        (d / "test.md").write_text("protein target is 180g\nfat target is 60g")
        result = tools_v2.grep_files("protein", "content", "*.md")
        assert "protein" in result.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryang4/Projects/BeStupid/telegram-bot && python -m pytest tests/test_v2_core.py::TestFileOpsV2 -v`
Expected: FAIL — functions don't exist yet

**Step 3: Add tool definitions to TOOLS list**

In `tools_v2.py`, add to the `TOOLS` list (before the closing `]`):

```python
    {
        "name": "read_file",
        "description": "Read a file from the BeStupid repo (logs, config, memory, scripts, data)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from repo root, e.g. 'content/logs/2026-01-23.md'"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write or update a file (only content/logs/, memory/, ~/.bestupid-private/)",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from repo root"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from repo root"},
                "pattern": {"type": "string", "default": "*", "description": "Glob pattern"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "grep_files",
        "description": "Regex search across files in the repo. Returns file:line: content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "default": ".", "description": "Relative path to search in"},
                "file_glob": {"type": "string", "default": "*.md", "description": "File glob pattern"},
            },
            "required": ["pattern"],
        },
    },
```

**Step 4: Add implementations**

Copy directly from `tools.py` — `read_file()`, `write_file()`, `list_files()`, `grep_files()`. These are standalone functions.

**Step 5: Add dispatch cases to execute_tool()**

```python
    if name == "read_file":
        return read_file(inputs["path"])
    if name == "write_file":
        return write_file(inputs["path"], inputs["content"])
    if name == "list_files":
        return list_files(inputs["path"], inputs.get("pattern", "*"))
    if name == "grep_files":
        return grep_files(inputs["pattern"], inputs.get("path", "."), inputs.get("file_glob", "*.md"))
```

**Step 6: Run tests to verify they pass**

Run: `cd /Users/ryang4/Projects/BeStupid/telegram-bot && python -m pytest tests/test_v2_core.py::TestFileOpsV2 -v`
Expected: PASS

**Step 7: Commit**

```bash
git add telegram-bot/tools_v2.py telegram-bot/tests/test_v2_core.py
git commit -m "feat: port file operation tools to v2 (read, write, list, grep)"
```

---

### Task 3: Add system/git tools + search/knowledge tools

**Files:**
- Modify: `telegram-bot/tools_v2.py`

**Step 1: Add tool definitions for all system, search, and knowledge tools**

Add to `TOOLS` list: `get_system_status`, `get_current_datetime`, `check_git_health`, `sync_with_remote`, `search_logs`, `search_conversation_history`, `fact_check`, `semantic_search`, `ingest_content`, `explore_connections`, `brain_stats`.

Copy the tool definition dicts exactly from `tools.py` lines 289-476.

**Step 2: Add implementations**

Copy these functions from `tools.py`:
- `get_system_status()` (lines 1084-1146)
- `get_current_datetime()` (lines 1149-1163)
- `check_git_health()` (lines 1166-1238)
- `sync_with_remote()` (lines 1241-1274)
- `search_logs()` (lines 798-822)
- `search_conversation_history()` (lines 1030-1081)
- `_extract_keywords()`, `_search_memory()`, `_summarize_memory_entry()`, `_search_logs_for_claim()`, `_search_history_for_claim()`, `fact_check()` (lines 1313-1537)
- `_get_brain_db()`, `tool_semantic_search()`, `tool_ingest_content()`, `tool_explore_connections()`, `tool_brain_stats()` (lines 1542-1648)

**Step 3: Add dispatch cases**

Add all 11 dispatch cases to `execute_tool()`.

**Step 4: Verify import works**

Run: `cd /Users/ryang4/Projects/BeStupid/telegram-bot && python -c "import tools_v2; print(f'{len(tools_v2.TOOLS)} tools loaded')"`
Expected: `25 tools loaded` (10 v2 + 4 file ops + 11 here)

**Step 5: Commit**

```bash
git add telegram-bot/tools_v2.py
git commit -m "feat: port system, search, and knowledge tools to v2"
```

---

### Task 4: Add planner, cron, script, policy, and nutrition tools

**Files:**
- Modify: `telegram-bot/tools_v2.py`

**Step 1: Add tool definitions**

Add to `TOOLS` list: `run_daily_planner`, `run_weekly_planner`, `get_brain_status`, `capture_to_inbox`, `manage_cron`, `run_script`, `run_memory_command`, `get_agent_policy`, `self_update_policy`, `log_food`, `get_nutrition_totals`.

Copy the tool definition dicts exactly from `tools.py`.

**Step 2: Add implementations**

Copy these functions from `tools.py`:
- `run_daily_planner()` (lines 647-657)
- `run_weekly_planner()` (lines 660-677)
- `get_brain_status()` (lines 680-779)
- `capture_to_inbox()` (lines 782-795)
- `_load_cron_config()`, `_save_cron_config()`, `_sync_cron_to_scheduler()`, `manage_cron()` (lines 828-916)
- `run_script()` (lines 983-1027)
- `run_memory_command()` (lines 959-980)
- `get_agent_policy()`, `self_update_policy()` (lines 1277-1308) — these need `from agent_policy import apply_agent_policy_update, format_agent_policy, load_agent_policy` at top
- `tool_log_food()`, `tool_get_nutrition_totals()` (lines 1653-1708)

**Step 3: Add dispatch cases**

Add all 11 dispatch cases to `execute_tool()`.

**Step 4: Add agent_policy import at top of file**

```python
from agent_policy import apply_agent_policy_update, format_agent_policy, load_agent_policy
```

**Step 5: Verify all tools load**

Run: `cd /Users/ryang4/Projects/BeStupid/telegram-bot && python -c "import tools_v2; print(f'{len(tools_v2.TOOLS)} tools loaded'); [print(f'  - {t[\"name\"]}') for t in tools_v2.TOOLS]"`
Expected: `36 tools loaded` (10 v2 + 4 file + 11 system/search + 11 planner/cron/etc)

**Step 6: Commit**

```bash
git add telegram-bot/tools_v2.py
git commit -m "feat: port planner, cron, script, policy, and nutrition tools to v2"
```

---

### Task 5: Add prompts COPY to Dockerfile, rebuild and verify

**Files:**
- Modify: `telegram-bot/Dockerfile`

**Step 1: Add prompts COPY**

After the `COPY v2/ ./v2/` line, add:

```dockerfile
COPY prompts/ ./prompts/
```

**Step 2: Rebuild and deploy**

```bash
cd /Users/ryang4/Projects/BeStupid/telegram-bot && docker compose up -d --build
```

**Step 3: Verify bot starts and loads all tools**

```bash
sleep 5 && docker logs bestupid-telegram-bot --tail 20
```

Expected: No import errors, "Application started" in logs.

**Step 4: Verify via Telegram**

Send to bot: "What's my workout today?" — should access protocol files and data.
Send to bot: "Get system status" — should return git/backup/scheduler info.

**Step 5: Commit**

```bash
git add telegram-bot/Dockerfile
git commit -m "feat: add prompts to Docker image for coaching support"
```

---

### Task 6: Delete old tools.py

**Files:**
- Delete: `telegram-bot/tools.py`

**Step 1: Verify nothing imports from tools.py**

```bash
grep -r "from tools import\|import tools\b" telegram-bot/ --include="*.py" | grep -v tools_v2 | grep -v __pycache__
```

Expected: Only `tools.py` itself or test files that should be updated.

**Step 2: Update any remaining imports**

If `test_tools.py` imports from `tools`, either update it to import from `tools_v2` or delete it (since we have `test_v2_core.py`).

**Step 3: Delete tools.py**

```bash
git rm telegram-bot/tools.py
```

**Step 4: Run all tests**

```bash
cd /Users/ryang4/Projects/BeStupid/telegram-bot && python -m pytest tests/ -v
```

**Step 5: Commit**

```bash
git commit -m "chore: remove old tools.py — all tools consolidated into tools_v2"
```
