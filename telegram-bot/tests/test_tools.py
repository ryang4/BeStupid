"""
Tests for tool implementations.
Verifies tool behavior, security, and edge cases.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestReadFile:
    """Test read_file tool."""

    def test_reads_allowed_path(self, mock_env, sample_log_content):
        """Test reading files from allowed paths."""
        log_file = mock_env["project_root"] / "content" / "logs" / "2026-02-05.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(sample_log_content)

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            with patch("tools.READABLE_PREFIXES", [mock_env["project_root"] / "content"]):
                from tools import read_file

                result = read_file("content/logs/2026-02-05.md")

                assert "Quick Log" in result

    def test_denies_blocked_path(self, mock_env):
        """Test that .env files are blocked."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import read_file

            result = read_file(".env")

            assert "denied" in result.lower()

    def test_handles_missing_file(self, mock_env):
        """Test handling of missing files."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            with patch("tools.READABLE_PREFIXES", [mock_env["project_root"]]):
                from tools import read_file

                result = read_file("nonexistent.txt")

                assert "not found" in result.lower()


class TestWriteFile:
    """Test write_file tool."""

    def test_writes_to_allowed_path(self, mock_env):
        """Test writing to allowed paths."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            with patch("tools.WRITABLE_PREFIXES", [mock_env["project_root"] / "memory"]):
                from tools import write_file

                result = write_file("memory/test.md", "# Test\n\nContent")

                assert "Wrote" in result
                assert (mock_env["project_root"] / "memory" / "test.md").exists()

    def test_denies_non_writable_path(self, mock_env):
        """Test that non-writable paths are denied."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            with patch("tools.WRITABLE_PREFIXES", [mock_env["project_root"] / "memory"]):
                from tools import write_file

                result = write_file("content/index.md", "test")

                assert "denied" in result.lower()


class TestUpdateMetric:
    """Test update_metric tool."""

    def test_updates_existing_metric(self, mock_env, sample_log_content):
        """Test updating an existing metric."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = mock_env["project_root"] / "content" / "logs" / f"{today}.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(sample_log_content)

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import update_metric_in_log

            result = update_metric_in_log("Weight", "190")

            assert "Updated" in result
            content = log_file.read_text()
            assert "Weight:: 190" in content

    def test_adds_missing_metric(self, mock_env, sample_log_content):
        """Test adding a metric that doesn't exist."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = mock_env["project_root"] / "content" / "logs" / f"{today}.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Remove the Weight line from sample
        content = sample_log_content.replace("Weight:: 185\n", "")
        log_file.write_text(content)

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import update_metric_in_log

            result = update_metric_in_log("Weight", "185")

            # Should add to Quick Log section
            assert "Added" in result or "Updated" in result


class TestManageCron:
    """Test manage_cron tool."""

    def test_list_empty_config(self, mock_env):
        """Test listing when no jobs configured."""
        with patch("tools.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            with patch("tools._sync_cron_to_scheduler", return_value=None):
                from tools import manage_cron

                result = manage_cron("list")

                assert "No cron jobs" in result

    def test_add_valid_job(self, mock_env):
        """Test adding a valid cron job."""
        with patch("tools.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            with patch("tools._sync_cron_to_scheduler", return_value=None):
                from tools import manage_cron

                result = manage_cron("add", "0 8 * * *", "morning_briefing")

                assert "Added" in result

                # Verify config was saved
                config_file = mock_env["private_dir"] / "cron_jobs.json"
                config = json.loads(config_file.read_text())
                assert "morning_briefing" in config

    def test_rejects_invalid_schedule(self, mock_env):
        """Test rejection of invalid cron schedule."""
        with patch("tools.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            from tools import manage_cron

            result = manage_cron("add", "invalid", "morning_briefing")

            assert "Invalid" in result

    def test_rejects_unknown_command(self, mock_env):
        """Test rejection of unknown command names."""
        with patch("tools.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            from tools import manage_cron

            result = manage_cron("add", "0 8 * * *", "unknown_job")

            assert "Unknown" in result

    def test_remove_job(self, mock_env, sample_cron_config):
        """Test removing a cron job."""
        with patch("tools.CRON_CONFIG", sample_cron_config):
            with patch("tools._sync_cron_to_scheduler", return_value=None):
                from tools import manage_cron

                result = manage_cron("remove", command_name="morning_briefing")

                assert "Removed" in result


class TestRunScript:
    """Test run_script tool."""

    def test_runs_python_script(self, mock_env, mock_subprocess):
        """Test running a Python script."""
        script = mock_env["project_root"] / "scripts" / "test.py"
        script.write_text("print('Hello')")

        with patch("tools.SCRIPTS_DIR", mock_env["project_root"] / "scripts"):
            with patch("tools.REPO_ROOT", mock_env["project_root"]):
                from tools import run_script

                result = run_script("test.py")

                mock_subprocess.assert_called_once()

    def test_rejects_path_traversal(self, mock_env):
        """Test rejection of path traversal attempts."""
        with patch("tools.SCRIPTS_DIR", mock_env["project_root"] / "scripts"):
            from tools import run_script

            result = run_script("../../../etc/passwd")

            assert "invalid" in result.lower() or "error" in result.lower()

    def test_rejects_non_script_extensions(self, mock_env):
        """Test rejection of non-script files."""
        with patch("tools.SCRIPTS_DIR", mock_env["project_root"] / "scripts"):
            from tools import run_script

            result = run_script("config.json")

            assert "only .py and .sh" in result.lower()


class TestSearchLogs:
    """Test search_logs tool."""

    def test_finds_matching_entries(self, mock_env, sample_log_content):
        """Test finding entries matching query."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = mock_env["project_root"] / "content" / "logs" / f"{today}.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(sample_log_content)

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import search_logs

            result = search_logs("workout")

            assert "workout" in result.lower()

    def test_returns_empty_for_no_matches(self, mock_env):
        """Test handling of no matches."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import search_logs

            result = search_logs("nonexistent_query_xyz")

            assert "No matches" in result


class TestGrepFiles:
    """Test grep_files tool."""

    def test_finds_regex_matches(self, mock_env):
        """Test regex pattern matching."""
        test_file = mock_env["project_root"] / "memory" / "test.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# Title\n\nEmail: test@example.com\n")

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import grep_files

            result = grep_files(r"\w+@\w+\.\w+", "memory", "*.md")

            assert "test@example.com" in result

    def test_handles_invalid_regex(self, mock_env):
        """Test handling of invalid regex patterns."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import grep_files

            result = grep_files("[invalid(regex", ".")

            assert "Invalid regex" in result


class TestGetSystemStatus:
    """Test get_system_status tool."""

    def test_returns_git_info(self, mock_env, mock_subprocess):
        """Test that system status includes git info."""
        (mock_env["project_root"] / ".git" / "HEAD").parent.mkdir(parents=True)
        (mock_env["project_root"] / ".git" / "HEAD").write_text("ref: refs/heads/main")

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import get_system_status

            result = get_system_status()

            assert "main" in result or "Git" in result

    def test_shows_backup_log(self, mock_env):
        """Test that system status shows backup failures."""
        log_file = mock_env["project_root"] / "logs" / "backup-failures.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("[2026-02-05] Test failure\n")

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import get_system_status

            result = get_system_status()

            assert "failure" in result.lower() or "Backup" in result
