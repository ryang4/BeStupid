"""
Pytest fixtures for BeStupid Telegram bot tests.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
TELEGRAM_BOT_DIR = Path(__file__).parent.parent
PROJECT_ROOT = TELEGRAM_BOT_DIR.parent
sys.path.insert(0, str(TELEGRAM_BOT_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temporary project directory structure."""
    # Create standard directories
    (tmp_path / "content" / "logs").mkdir(parents=True)
    (tmp_path / "memory").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / ".bestupid-private").mkdir()

    return tmp_path


@pytest.fixture
def tmp_private_dir(tmp_path):
    """Create a temporary private directory for cron config, history, etc."""
    private_dir = tmp_path / ".bestupid-private"
    private_dir.mkdir(parents=True, exist_ok=True)
    return private_dir


@pytest.fixture
def mock_env(tmp_project_dir, tmp_private_dir):
    """Patch environment variables for testing."""
    with patch.dict(os.environ, {
        "PROJECT_ROOT": str(tmp_project_dir),
        "HISTORY_DIR": str(tmp_private_dir),
        "TELEGRAM_BOT_TOKEN": "test-token",
        "OWNER_CHAT_ID": "12345",
    }):
        yield {
            "project_root": tmp_project_dir,
            "private_dir": tmp_private_dir,
        }


@pytest.fixture
def sample_cron_config(tmp_private_dir):
    """Create a sample cron configuration."""
    config = {
        "morning_briefing": {"schedule": "0 7 * * *", "enabled": True},
        "auto_backup": {"schedule": "0 */6 * * *", "enabled": True},
    }
    config_file = tmp_private_dir / "cron_jobs.json"
    config_file.write_text(json.dumps(config, indent=2))
    return config_file


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for testing."""
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    bot.send_chat_action = AsyncMock()
    return bot


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    client = MagicMock()

    # Create a mock response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Test response")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    client.messages.create = MagicMock(return_value=mock_response)
    return client


@pytest.fixture
def sample_log_content():
    """Sample daily log content for testing."""
    return """---
date: 2026-02-05
---

## Quick Log
Weight:: 185
Sleep:: 7.5
Sleep_Quality:: 8
Mood_AM:: 7
Mood_PM::

## Today's Todos
- [ ] Review quarterly goals
- [x] Morning workout
- [ ] Call dentist

## Notes
Test log entry.
"""


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for testing."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Success",
            stderr="",
        )
        yield mock_run
