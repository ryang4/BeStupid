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

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            with patch("tools_v2._default_readable_prefixes", return_value=[mock_env["project_root"] / "content"]):
                from tools_v2 import read_file

                result = read_file("content/logs/2026-02-05.md")

                assert "Quick Log" in result

    def test_denies_blocked_path(self, mock_env):
        """Test that .env files are blocked."""
        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import read_file

            result = read_file(".env")

            assert "denied" in result.lower()

    def test_handles_missing_file(self, mock_env):
        """Test handling of missing files."""
        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            with patch("tools_v2._default_readable_prefixes", return_value=[mock_env["project_root"]]):
                from tools_v2 import read_file

                result = read_file("nonexistent.txt")

                assert "not found" in result.lower()


class TestWriteFile:
    """Test write_file tool."""

    def test_writes_to_allowed_path(self, mock_env):
        """Test writing to allowed paths."""
        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            with patch("tools_v2._default_writable_prefixes", return_value=[mock_env["project_root"] / "memory"]):
                from tools_v2 import write_file

                result = write_file("memory/test.md", "# Test\n\nContent")

                assert "Wrote" in result
                assert (mock_env["project_root"] / "memory" / "test.md").exists()

    def test_denies_non_writable_path(self, mock_env):
        """Test that non-writable paths are denied."""
        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            with patch("tools_v2._default_writable_prefixes", return_value=[mock_env["project_root"] / "memory"]):
                from tools_v2 import write_file

                result = write_file("content/index.md", "test")

                assert "denied" in result.lower()


class TestManageCron:
    """Test manage_cron tool."""

    def test_list_empty_config(self, mock_env):
        """Test listing when no jobs configured."""
        with patch("tools_v2.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            with patch("tools_v2._sync_cron_to_scheduler", return_value=None):
                from tools_v2 import manage_cron

                result = manage_cron("list")

                assert "No cron jobs" in result

    def test_add_valid_job(self, mock_env):
        """Test adding a valid cron job."""
        with patch("tools_v2.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            with patch("tools_v2._sync_cron_to_scheduler", return_value=None):
                from tools_v2 import manage_cron

                result = manage_cron("add", "0 8 * * *", "morning_briefing")

                assert "Added" in result

                # Verify config was saved
                config_file = mock_env["private_dir"] / "cron_jobs.json"
                config = json.loads(config_file.read_text())
                assert "morning_briefing" in config

    def test_rejects_invalid_schedule(self, mock_env):
        """Test rejection of invalid cron schedule."""
        with patch("tools_v2.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            from tools_v2 import manage_cron

            result = manage_cron("add", "invalid", "morning_briefing")

            assert "Invalid" in result

    def test_rejects_unknown_command(self, mock_env):
        """Test rejection of unknown command names."""
        with patch("tools_v2.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            from tools_v2 import manage_cron

            result = manage_cron("add", "0 8 * * *", "unknown_job")

            assert "Unknown" in result

    def test_remove_job(self, mock_env, sample_cron_config):
        """Test removing a cron job."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            with patch("tools_v2._sync_cron_to_scheduler", return_value=None):
                from tools_v2 import manage_cron

                result = manage_cron("remove", command_name="morning_briefing")

                assert "Removed" in result


class TestManageCronMessages:
    """Test manage_cron set_message/get_message actions."""

    def test_set_message_persists(self, mock_env, sample_cron_config):
        """Test that set_message saves and get_message retrieves."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            result = manage_cron("set_message", command_name="morning_briefing", message="Custom morning msg")

            assert "Updated" in result
            assert "Custom morning msg" in result

            result = manage_cron("get_message", command_name="morning_briefing")
            assert "Custom morning msg" in result

    def test_set_message_rejects_oversized(self, mock_env, sample_cron_config):
        """Test rejection of messages exceeding max length."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            result = manage_cron("set_message", command_name="morning_briefing", message="x" * 2500)
            assert "Error" in result
            assert "2500" in result

    def test_set_message_warns_unmatched_markdown(self, mock_env, sample_cron_config):
        """Test warning on unmatched Markdown delimiters."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            result = manage_cron("set_message", command_name="morning_briefing", message="*bold but not closed")
            assert "unmatched" in result.lower()

    def test_set_message_requires_command_name(self, mock_env, sample_cron_config):
        """Test that command_name is required."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            result = manage_cron("set_message", message="Hello")
            assert "Error" in result

    def test_set_message_requires_message(self, mock_env, sample_cron_config):
        """Test that message text is required."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            result = manage_cron("set_message", command_name="morning_briefing")
            assert "Error" in result

    def test_get_message_no_custom(self, mock_env, sample_cron_config):
        """Test get_message when no custom message is set."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            result = manage_cron("get_message", command_name="morning_briefing")
            assert "default" in result.lower()

    def test_list_shows_custom_message_indicator(self, mock_env, sample_cron_config):
        """Test that list shows custom message status."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            manage_cron("set_message", command_name="morning_briefing", message="Custom")
            result = manage_cron("list")
            assert "custom message" in result

    def test_set_message_on_nonexistent_job(self, mock_env):
        """Test set_message on a job that doesn't exist in config."""
        with patch("tools_v2.CRON_CONFIG", mock_env["private_dir"] / "cron_jobs.json"):
            from tools_v2 import manage_cron

            result = manage_cron("set_message", command_name="morning_briefing", message="Test")
            assert "not found" in result.lower()

    def test_set_message_allows_valid_markdown(self, mock_env, sample_cron_config):
        """Test that properly paired Markdown is accepted."""
        with patch("tools_v2.CRON_CONFIG", sample_cron_config):
            from tools_v2 import manage_cron

            msg = "**Bold title**\n\n- Item 1\n- Item 2\n\n_Italic footer_"
            result = manage_cron("set_message", command_name="morning_briefing", message=msg)
            assert "Updated" in result


class TestRunScript:
    """Test run_script tool."""

    def test_runs_python_script(self, mock_env, mock_subprocess):
        """Test running a Python script."""
        script = mock_env["project_root"] / "scripts" / "test.py"
        script.write_text("print('Hello')")

        with patch("tools_v2.SCRIPTS_DIR", mock_env["project_root"] / "scripts"):
            with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
                from tools_v2 import run_script

                result = run_script("test.py")

                mock_subprocess.assert_called_once()

    def test_rejects_path_traversal(self, mock_env):
        """Test rejection of path traversal attempts."""
        with patch("tools_v2.SCRIPTS_DIR", mock_env["project_root"] / "scripts"):
            from tools_v2 import run_script

            result = run_script("../../../etc/passwd")

            assert "invalid" in result.lower() or "error" in result.lower()

    def test_rejects_non_script_extensions(self, mock_env):
        """Test rejection of non-script files."""
        with patch("tools_v2.SCRIPTS_DIR", mock_env["project_root"] / "scripts"):
            from tools_v2 import run_script

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

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import search_logs

            result = search_logs("workout")

            assert "workout" in result.lower()

    def test_returns_empty_for_no_matches(self, mock_env):
        """Test handling of no matches."""
        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import search_logs

            result = search_logs("nonexistent_query_xyz")

            assert "No matches" in result


class TestGrepFiles:
    """Test grep_files tool."""

    def test_finds_regex_matches(self, mock_env):
        """Test regex pattern matching."""
        test_file = mock_env["project_root"] / "memory" / "test.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# Title\n\nEmail: test@example.com\n")

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import grep_files

            result = grep_files(r"\w+@\w+\.\w+", "memory", "*.md")

            assert "test@example.com" in result

    def test_handles_invalid_regex(self, mock_env):
        """Test handling of invalid regex patterns."""
        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import grep_files

            result = grep_files("[invalid(regex", ".")

            assert "Invalid regex" in result


class TestFactCheck:
    """Test fact_check tool."""

    def test_finds_memory_evidence(self, mock_env):
        """Test that fact_check finds evidence in approved_memory table."""
        from v2.bootstrap import get_services
        services = get_services()
        # Insert an approved memory about John Smith
        with services.store.begin_write() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO approved_memory
                    (memory_id, chat_id, kind, subject_key, payload_json, version, active, valid_from_utc, source_candidate_id)
                VALUES ('mem_test1', 0, 'relationship', 'relationship:john smith:accountant',
                        '{"name": "John Smith", "role": "accountant"}', 1, 1, '2026-01-01T00:00:00', 'cand_test1')
                """,
            )

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import fact_check

            result = fact_check("John Smith is my accountant")

            assert "Evidence Found" in result or "EVIDENCE FOUND" in result
            assert "john" in result.lower()

    def test_finds_log_evidence(self, mock_env, sample_log_content):
        """Test that fact_check finds evidence in daily logs."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = mock_env["project_root"] / "content" / "logs" / f"{today}.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(sample_log_content)

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import fact_check

            result = fact_check("I did a morning workout today", sources="logs")

            assert "EVIDENCE FOUND" in result
            assert "workout" in result.lower()

    def test_returns_unverified_for_no_matches(self, mock_env):
        """Test that fact_check returns UNVERIFIED when no evidence found."""
        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            with patch("tools_v2.PRIVATE_DIR", mock_env["private_dir"]):
                from tools_v2 import fact_check

                result = fact_check("The moon is made of cheese")

                assert "UNVERIFIED" in result

    def test_finds_commitment_evidence(self, mock_env):
        """Test that fact_check finds evidence in approved_memory (commitments)."""
        from v2.bootstrap import get_services
        services = get_services()
        with services.store.begin_write() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO approved_memory
                    (memory_id, chat_id, kind, subject_key, payload_json, version, active, valid_from_utc, source_candidate_id)
                VALUES ('mem_test2', 0, 'commitment', 'commitment:send proposal to john',
                        '{"title": "Send proposal to John", "deadline": "2026-02-15"}', 1, 1, '2026-01-01T00:00:00', 'cand_test2')
                """,
            )

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import fact_check

            result = fact_check("I need to send a proposal to John")

            assert "EVIDENCE FOUND" in result
            assert "proposal" in result.lower()

    def test_finds_decision_evidence(self, mock_env):
        """Test that fact_check finds evidence in approved_memory (decisions)."""
        from v2.bootstrap import get_services
        services = get_services()
        with services.store.begin_write() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO approved_memory
                    (memory_id, chat_id, kind, subject_key, payload_json, version, active, valid_from_utc, source_candidate_id)
                VALUES ('mem_test3', 0, 'fact', 'fact:react fastapi tech stack',
                        '{"fact": "Decided to use React and FastAPI for tech stack"}', 1, 1, '2026-01-01T00:00:00', 'cand_test3')
                """,
            )

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import fact_check

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

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import fact_check

            # Only search logs (not memory), so should find nothing
            result = fact_check("Alice is an engineer", sources="logs")

            assert "UNVERIFIED" in result

    def test_extracts_keywords(self):
        """Test keyword extraction from claims."""
        from tools_v2 import _extract_keywords

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
        from tools_v2 import fact_check

        result = fact_check("I am")

        assert "Could not extract" in result

    def test_searches_conversation_history(self, mock_env):
        """Test that fact_check finds evidence in the turn table."""
        from v2.bootstrap import get_services
        services = get_services()
        # Insert turns about Acme Corp contract
        session = services.store.get_or_create_session(0)
        services.store.record_turn(0, session["session_id"], 0, "user",
                                   "I signed the contract with Acme Corp yesterday")
        services.store.record_turn(0, session["session_id"], 0, "assistant",
                                   "Got it, I noted the Acme Corp contract signing.")

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import fact_check

            result = fact_check("I signed a contract with Acme Corp", sources="history", chat_id=0)

            assert "EVIDENCE FOUND" in result
            assert "acme" in result.lower() or "contract" in result.lower()


class TestGetSystemStatus:
    """Test get_system_status tool."""

    def test_returns_git_info(self, mock_env, mock_subprocess):
        """Test that system status includes git info."""
        (mock_env["project_root"] / ".git" / "HEAD").parent.mkdir(parents=True)
        (mock_env["project_root"] / ".git" / "HEAD").write_text("ref: refs/heads/main")

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import get_system_status

            result = get_system_status()

            assert "main" in result or "Git" in result

    def test_shows_backup_log(self, mock_env):
        """Test that system status shows backup failures."""
        log_file = mock_env["project_root"] / "logs" / "backup-failures.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("[2026-02-05] Test failure\n")

        with patch("tools_v2.REPO_ROOT", mock_env["project_root"]):
            from tools_v2 import get_system_status

            result = get_system_status()

            assert "failure" in result.lower() or "Backup" in result


class TestSelfUpdatePolicy:
    """Test self-updating agent policy tools."""

    def test_get_agent_policy_without_chat_context(self):
        from tools_v2 import get_agent_policy

        result = get_agent_policy(chat_id=0)
        assert "missing chat context" in result.lower()

    def test_self_update_policy_appends_rules(self, mock_env):
        with patch("tools_v2.PRIVATE_DIR", mock_env["private_dir"]):
            with patch("agent_policy.HISTORY_DIR", mock_env["private_dir"]):
                with patch("agent_policy.POLICY_FILE", mock_env["private_dir"] / "agent_policies.json"):
                    from tools_v2 import self_update_policy

                    result = self_update_policy(
                        action="append_rules",
                        reason="Missed follow-through on open tasks",
                        chat_id=12345,
                        rules=["Always include next 3 actions with owners"],
                    )

                    assert "Self-update applied" in result
                    assert "Always include next 3 actions with owners" in result
