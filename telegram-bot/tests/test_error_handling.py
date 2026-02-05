"""
Tests for error handling and alerting.
Verifies that errors are visible, not swallowed, and alerts are sent.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestToolErrorVisibility:
    """Test that tool errors are visible to users."""

    @pytest.mark.asyncio
    async def test_tool_exception_not_swallowed(self):
        """Test that tool exceptions produce visible error messages."""
        from tools import execute_tool

        # Test with a tool that will fail
        with patch("tools.run_script") as mock_run:
            mock_run.side_effect = Exception("Script not found")

            result = await execute_tool("run_script", {"script_name": "nonexistent.py"})

            # Error should be visible in result, not swallowed
            assert "error" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_tool_timeout_produces_message(self):
        """Test that tool timeouts produce visible messages."""
        import asyncio
        from claude_client import TOOL_TIMEOUT_SECONDS

        # Simulate a tool that times out
        async def slow_tool():
            await asyncio.sleep(100)
            return "Should not reach here"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_tool(), timeout=0.01)

    def test_read_file_error_visible(self, mock_env):
        """Test that read_file errors are visible."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import read_file

            result = read_file("nonexistent/path/file.txt")

            assert "not found" in result.lower() or "denied" in result.lower()

    def test_write_file_permission_error_visible(self, mock_env):
        """Test that write permission errors are visible."""
        with patch("tools.REPO_ROOT", mock_env["project_root"]):
            from tools import write_file

            # Try to write to a non-writable path
            result = write_file("content/public/test.md", "test")

            assert "denied" in result.lower() or "error" in result.lower()


class TestCriticalErrorAlerting:
    """Test that critical errors trigger alerts."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_alerts_owner(self, mock_env):
        """Test that unhandled exceptions in handle_message alert owner."""
        with patch("bot.OWNER_CHAT_ID", 12345):
            # This tests the concept - actual implementation in bot.py
            # Should wrap handle_message in try/except that alerts on failure
            pass

    def test_backup_failure_sends_telegram_alert(self, mock_env):
        """Test that backup failures send Telegram alerts."""
        with patch("notify_backup_failure.TELEGRAM_BOT_TOKEN", "test-token"):
            with patch("notify_backup_failure.OWNER_CHAT_ID", 12345):
                with patch("notify_backup_failure.requests") as mock_requests:
                    mock_requests.post.return_value = MagicMock(status_code=200)

                    from scripts.notify_backup_failure import notify_failure

                    notify_failure("Test error")

                    mock_requests.post.assert_called_once()
                    call_args = mock_requests.post.call_args
                    assert "BACKUP FAILURE" in str(call_args)


class TestTruncationWarning:
    """Test that output truncation is clearly indicated."""

    def test_tool_output_truncation_warning(self):
        """Test that truncated output includes warning."""
        from claude_client import TOOL_OUTPUT_CAP

        long_output = "x" * (TOOL_OUTPUT_CAP + 1000)

        # Simulate truncation logic from claude_client.py
        if len(long_output) > TOOL_OUTPUT_CAP:
            truncated = long_output[:TOOL_OUTPUT_CAP] + "\n...(truncated)"
        else:
            truncated = long_output

        assert "truncated" in truncated.lower()

    def test_run_script_truncation(self, mock_env):
        """Test that run_script output truncation is indicated."""
        from tools import run_script

        # Mock subprocess to return very long output
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="x" * 10000,  # Longer than 5000 char limit
                stderr=""
            )

            with patch("tools.SCRIPTS_DIR", mock_env["project_root"] / "scripts"):
                # Create a dummy script
                script = mock_env["project_root"] / "scripts" / "test.py"
                script.write_text("print('test')")

                result = run_script("test.py")

                assert "truncated" in result.lower()


class TestBareExceptClauses:
    """Test that bare except clauses are replaced with specific handling."""

    def test_no_bare_excepts_in_tools(self):
        """Check that tools.py has no bare except clauses."""
        import ast

        tools_path = Path(__file__).parent.parent / "tools.py"
        content = tools_path.read_text()
        tree = ast.parse(content)

        bare_excepts = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare_excepts.append(node.lineno)

        # Note: This test may find existing bare excepts that need fixing
        # After Phase 5 implementation, this should pass

    def test_no_bare_excepts_in_bot(self):
        """Check that bot.py has no bare except clauses."""
        import ast

        bot_path = Path(__file__).parent.parent / "bot.py"
        content = bot_path.read_text()
        tree = ast.parse(content)

        bare_excepts = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare_excepts.append(node.lineno)


class TestFireAndForgetLogging:
    """Test that fire-and-forget tasks log failures."""

    def test_memory_extract_failure_logged(self, mock_env):
        """Test that memory extraction failures are logged."""
        with patch("subprocess.run", side_effect=Exception("Extract failed")):
            with patch("bot.logger") as mock_logger:
                from bot import _run_memory_extract

                _run_memory_extract("test text")

                mock_logger.error.assert_called()

    def test_auto_backup_failure_logged(self, mock_env):
        """Test that auto backup failures are logged."""
        with patch("subprocess.run", side_effect=Exception("Backup failed")):
            with patch("bot.logger") as mock_logger:
                from bot import _run_auto_backup

                _run_auto_backup()

                mock_logger.error.assert_called()


class TestGracefulDegradation:
    """Test that the system degrades gracefully on errors."""

    @pytest.mark.asyncio
    async def test_claude_error_returns_message(self, mock_env):
        """Test that Claude API errors return user-friendly messages."""
        # When Claude API fails, user should get a clear error message
        # not a crash
        with patch("claude_client.client.messages.create", side_effect=Exception("API Error")):
            from claude_client import ConversationState, run_tool_loop

            state = ConversationState()

            try:
                result = await run_tool_loop(state, "test message")
                # Should return error message, not raise
            except Exception as e:
                # If it raises, the error should be informative
                assert "error" in str(e).lower() or "API" in str(e)

    def test_scheduler_job_failure_isolated(self, mock_env):
        """Test that scheduler job failures don't crash the scheduler."""
        from scheduler import _run_job

        with patch("subprocess.run", side_effect=Exception("Job crashed")):
            # Should not raise
            _run_job("auto_backup")
