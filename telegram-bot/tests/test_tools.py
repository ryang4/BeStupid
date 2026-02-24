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


class TestFactCheck:
    """Test fact_check tool."""

    def test_finds_memory_evidence(self, mock_env):
        """Test that fact_check finds evidence in memory files."""
        # Create a person in memory
        people_dir = mock_env["project_root"] / "memory" / "people"
        people_dir.mkdir(parents=True, exist_ok=True)
        person = {
            "name": "John Smith",
            "role": "accountant",
            "context": "Met at tech conference",
            "source": "Notion",
            "tags": [],
            "notes": "",
            "interactions": [],
        }
        (people_dir / "john-smith.json").write_text(json.dumps(person))

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import fact_check

            result = fact_check("John Smith is my accountant")

            assert "Evidence Found" in result or "EVIDENCE FOUND" in result
            assert "john" in result.lower()

    def test_finds_log_evidence(self, mock_env, sample_log_content):
        """Test that fact_check finds evidence in daily logs."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = mock_env["project_root"] / "content" / "logs" / f"{today}.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(sample_log_content)

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import fact_check

            result = fact_check("I did a morning workout today", sources="logs")

            assert "EVIDENCE FOUND" in result
            assert "workout" in result.lower()

    def test_returns_unverified_for_no_matches(self, mock_env):
        """Test that fact_check returns UNVERIFIED when no evidence found."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            with patch("tools.PRIVATE_DIR", mock_env["private_dir"]):
                from tools import fact_check

                result = fact_check("The moon is made of cheese")

                assert "UNVERIFIED" in result

    def test_finds_commitment_evidence(self, mock_env):
        """Test that fact_check finds evidence in commitments."""
        commitments_dir = mock_env["project_root"] / "memory" / "commitments"
        commitments_dir.mkdir(parents=True, exist_ok=True)
        commitment = {
            "what": "Send proposal to John",
            "who": "John Smith",
            "deadline": "2026-02-15",
            "status": "open",
        }
        (commitments_dir / "20260210-send-proposal.json").write_text(json.dumps(commitment))

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import fact_check

            result = fact_check("I need to send a proposal to John")

            assert "EVIDENCE FOUND" in result
            assert "proposal" in result.lower()

    def test_finds_decision_evidence(self, mock_env):
        """Test that fact_check finds evidence in decisions."""
        decisions_dir = mock_env["project_root"] / "memory" / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        decision = {
            "topic": "tech-stack",
            "choice": "React + FastAPI",
            "rationale": "Team expertise",
            "status": "active",
        }
        (decisions_dir / "tech-stack.json").write_text(json.dumps(decision))

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import fact_check

            result = fact_check("We decided to use React and FastAPI")

            assert "EVIDENCE FOUND" in result
            assert "react" in result.lower() or "fastapi" in result.lower()

    def test_respects_sources_filter(self, mock_env):
        """Test that fact_check respects the sources parameter."""
        # Create memory evidence
        people_dir = mock_env["project_root"] / "memory" / "people"
        people_dir.mkdir(parents=True, exist_ok=True)
        person = {"name": "Alice", "role": "engineer", "context": "coworker"}
        (people_dir / "alice.json").write_text(json.dumps(person))

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import fact_check

            # Only search logs (not memory), so should find nothing
            result = fact_check("Alice is an engineer", sources="logs")

            assert "UNVERIFIED" in result

    def test_extracts_keywords(self):
        """Test keyword extraction from claims."""
        from tools import _extract_keywords

        keywords = _extract_keywords("I committed to calling John by Friday")

        assert "john" in keywords
        assert "friday" in keywords
        assert "committed" in keywords
        assert "calling" in keywords
        # Stop words should be excluded
        assert "i" not in keywords
        assert "to" not in keywords
        assert "by" not in keywords

    def test_handles_empty_claim(self):
        """Test fact_check with a claim that has no extractable keywords."""
        from tools import fact_check

        result = fact_check("I am")

        assert "Could not extract" in result

    def test_searches_conversation_history(self, mock_env):
        """Test that fact_check finds evidence in conversation history."""
        history = {
            "12345": {
                "history": [
                    {"role": "user", "content": "I signed the contract with Acme Corp yesterday"},
                    {"role": "assistant", "content": "Got it, I noted the Acme Corp contract signing."},
                ],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
        }
        history_file = mock_env["private_dir"] / "conversation_history.json"
        history_file.write_text(json.dumps(history))

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            with patch("tools.PRIVATE_DIR", mock_env["private_dir"]):
                from tools import fact_check

                result = fact_check("I signed a contract with Acme Corp", sources="history")

                assert "EVIDENCE FOUND" in result
                assert "acme" in result.lower() or "contract" in result.lower()


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


class TestSelfUpdatePolicy:
    """Test self-updating agent policy tools."""

    def test_get_agent_policy_without_chat_context(self):
        from tools import get_agent_policy

        result = get_agent_policy(chat_id=0)
        assert "missing chat context" in result.lower()

    def test_self_update_policy_appends_rules(self, mock_env):
        with patch("tools.PRIVATE_DIR", mock_env["private_dir"]):
            with patch("agent_policy.HISTORY_DIR", mock_env["private_dir"]):
                with patch("agent_policy.POLICY_FILE", mock_env["private_dir"] / "agent_policies.json"):
                    from tools import self_update_policy

                    result = self_update_policy(
                        action="append_rules",
                        reason="Missed follow-through on open tasks",
                        chat_id=12345,
                        rules=["Always include next 3 actions with owners"],
                    )

                    assert "Self-update applied" in result
                    assert "Always include next 3 actions with owners" in result
