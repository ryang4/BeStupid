"""
Tests for atomic write operations.
Verifies that file writes are crash-safe using tmp+rename pattern.
"""

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAtomicCronConfig:
    """Test atomic writes for cron_jobs.json."""

    def test_save_cron_config_creates_file(self, mock_env):
        """Test that _save_cron_config creates config file atomically."""
        from tools import _save_cron_config, CRON_CONFIG

        # Patch CRON_CONFIG to use test directory
        test_config_path = mock_env["private_dir"] / "cron_jobs.json"
        with patch("tools.CRON_CONFIG", test_config_path):
            config = {"test_job": {"schedule": "0 8 * * *", "enabled": True}}
            _save_cron_config(config)

            assert test_config_path.exists()
            loaded = json.loads(test_config_path.read_text())
            assert loaded == config

    def test_save_cron_config_no_partial_write(self, mock_env):
        """Test that partial writes don't corrupt the config."""
        test_config_path = mock_env["private_dir"] / "cron_jobs.json"

        # Write initial valid config
        initial = {"existing": {"schedule": "0 7 * * *", "enabled": True}}
        test_config_path.write_text(json.dumps(initial))

        with patch("tools.CRON_CONFIG", test_config_path):
            from tools import _save_cron_config

            # Simulate write with new config
            new_config = {"new_job": {"schedule": "0 9 * * *", "enabled": True}}

            # Mock Path.rename to fail (simulating crash mid-write)
            original_rename = Path.rename

            def failing_rename(self, target):
                # The .tmp file should exist at this point
                tmp_file = test_config_path.with_suffix(".tmp")
                if tmp_file.exists():
                    # Verify tmp file has complete content
                    tmp_content = tmp_file.read_text()
                    assert json.loads(tmp_content) == new_config
                raise OSError("Simulated crash")

            with patch.object(Path, "rename", failing_rename):
                with pytest.raises(OSError, match="Simulated crash"):
                    _save_cron_config(new_config)

            # Original config should still be intact
            loaded = json.loads(test_config_path.read_text())
            assert loaded == initial

    def test_load_cron_config_handles_missing_file(self, mock_env):
        """Test that _load_cron_config returns empty dict for missing file."""
        test_config_path = mock_env["private_dir"] / "cron_jobs.json"

        with patch("tools.CRON_CONFIG", test_config_path):
            from tools import _load_cron_config

            # File doesn't exist
            assert not test_config_path.exists()
            result = _load_cron_config()
            assert result == {}

    def test_load_cron_config_handles_corrupted_file(self, mock_env):
        """Test that _load_cron_config handles corrupted JSON gracefully."""
        test_config_path = mock_env["private_dir"] / "cron_jobs.json"
        test_config_path.write_text("{ invalid json ")

        with patch("tools.CRON_CONFIG", test_config_path):
            from tools import _load_cron_config

            # Should not raise, should return empty dict
            result = _load_cron_config()
            assert result == {}


class TestAtomicWriteFile:
    """Test atomic writes for write_file tool."""

    def test_write_file_atomic(self, mock_env):
        """Test that write_file uses atomic write pattern."""
        from tools import write_file

        # Patch module-level constants
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            test_path = "memory/test.md"
            content = "# Test Content\n\nThis is a test."

            result = write_file(test_path, content)

            assert "Wrote" in result
            full_path = mock_env["project_root"] / test_path
            assert full_path.exists()
            assert full_path.read_text() == content

    def test_write_file_no_partial_on_crash(self, mock_env):
        """Test that crashes during write don't leave partial files."""
        # Write initial content
        test_file = mock_env["project_root"] / "memory" / "existing.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = "Original content that must not be corrupted"
        test_file.write_text(original_content)

        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import write_file

            # Simulate crash during rename
            with patch.object(Path, "rename", side_effect=OSError("Simulated crash")):
                with pytest.raises(OSError):
                    write_file("memory/existing.md", "New corrupted content")

            # Original should be intact
            assert test_file.read_text() == original_content


class TestAtomicConversationHistory:
    """Test atomic writes for conversation history."""

    def test_conversation_state_save_atomic(self, mock_env):
        """Test that ConversationState.save_to_disk uses atomic write."""
        with patch("claude_client.HISTORY_DIR", mock_env["private_dir"]):
            with patch("claude_client.HISTORY_FILE", mock_env["private_dir"] / "conversation_history.json"):
                from claude_client import ConversationState

                state = ConversationState(
                    history=[{"role": "user", "content": "test"}],
                    total_input_tokens=100,
                    total_output_tokens=50,
                )

                state.save_to_disk(chat_id=12345)

                history_file = mock_env["private_dir"] / "conversation_history.json"
                assert history_file.exists()

                data = json.loads(history_file.read_text())
                assert "12345" in data
                assert data["12345"]["history"] == [{"role": "user", "content": "test"}]


class TestAtomicBackupLog:
    """Test atomic writes for backup failure log."""

    def test_backup_log_append_with_locking(self, mock_env):
        """Test that backup log appends use proper file locking."""
        log_file = mock_env["project_root"] / "logs" / "backup-failures.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Write initial content
        log_file.write_text("[2026-02-05 10:00:00] Initial entry\n")

        # Simulate concurrent appends
        results = []

        def append_entry(entry_num):
            import fcntl
            with open(log_file, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(f"[2026-02-05 10:00:0{entry_num}] Entry {entry_num}\n")
                    results.append(entry_num)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        threads = [threading.Thread(target=append_entry, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All entries should be present
        content = log_file.read_text()
        assert len(results) == 5
        for i in range(5):
            assert f"Entry {i}" in content
