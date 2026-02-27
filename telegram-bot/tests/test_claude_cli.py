"""
Tests for the Claude Code CLI wrapper module.
"""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

# Import from scripts/
from claude_cli import _extract_json, call_claude, call_claude_json, cli_available


# =============================================================================
# cli_available()
# =============================================================================


class TestCliAvailable:
    def test_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            assert cli_available() is False

    def test_token_set_no_binary(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-xxx"}):
            with patch("shutil.which", return_value=None):
                assert cli_available() is False

    def test_token_set_with_binary(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-xxx"}):
            with patch("shutil.which", return_value="/usr/local/bin/claude"):
                assert cli_available() is True

    def test_empty_token(self):
        with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": ""}):
            assert cli_available() is False


# =============================================================================
# call_claude()
# =============================================================================


class TestCallClaude:
    def test_returns_none_when_unavailable(self):
        with patch("claude_cli.cli_available", return_value=False):
            assert call_claude("hello") is None

    def test_successful_call(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="Hello world\n", stderr="")
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = call_claude("say hello")
                assert result == "Hello world"
                # Verify stdin prompt was passed
                mock_run.assert_called_once()
                call_kwargs = mock_run.call_args
                assert call_kwargs.kwargs["input"] == "say hello"

    def test_nonzero_exit_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=1, stdout="", stderr="auth error")
            with patch("subprocess.run", return_value=mock_result):
                assert call_claude("hello") is None

    def test_timeout_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 120)):
                assert call_claude("hello") is None

    def test_file_not_found_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                assert call_claude("hello") is None

    def test_system_prompt_uses_temp_file(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="response", stderr="")
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = call_claude("hello", system_prompt="Be concise")
                assert result == "response"
                # Verify --system-prompt-file was in the command
                cmd = mock_run.call_args[0][0]
                assert "--system-prompt-file" in cmd

    def test_claudecode_env_stripped(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
            with patch.dict(os.environ, {"CLAUDECODE": "1", "CLAUDE_CODE_OAUTH_TOKEN": "tok"}):
                with patch("subprocess.run", return_value=mock_result) as mock_run:
                    call_claude("test")
                    env = mock_run.call_args.kwargs["env"]
                    assert "CLAUDECODE" not in env

    def test_max_turns_flag(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                call_claude("test", max_turns=5)
                cmd = mock_run.call_args[0][0]
                turns_idx = cmd.index("--max-turns")
                assert cmd[turns_idx + 1] == "5"


# =============================================================================
# call_claude_json()
# =============================================================================


class TestCallClaudeJson:
    def test_returns_none_when_unavailable(self):
        with patch("claude_cli.cli_available", return_value=False):
            assert call_claude_json("hello") is None

    def test_parses_wrapped_json_response(self):
        """CLI wraps response in {"type":"result","result":"..."} """
        inner_json = {"entities": [], "relationships": []}
        outer = {"type": "result", "result": json.dumps(inner_json)}
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
            with patch("subprocess.run", return_value=mock_result):
                result = call_claude_json("extract")
                assert result == inner_json

    def test_handles_direct_dict_in_result(self):
        """When result field is already a dict (not string)."""
        inner = {"entities": []}
        outer = {"type": "result", "result": inner}
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
            with patch("subprocess.run", return_value=mock_result):
                result = call_claude_json("extract")
                assert result == inner

    def test_handles_markdown_code_blocks(self):
        """Model sometimes wraps JSON in markdown code blocks."""
        inner_json = [{"type": "food", "description": "test"}]
        wrapped = f"```json\n{json.dumps(inner_json)}\n```"
        outer = {"type": "result", "result": wrapped}
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
            with patch("subprocess.run", return_value=mock_result):
                result = call_claude_json("detect patterns")
                assert result == inner_json

    def test_nonzero_exit_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=1, stdout="", stderr="error")
            with patch("subprocess.run", return_value=mock_result):
                assert call_claude_json("test") is None

    def test_empty_stdout_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="", stderr="")
            with patch("subprocess.run", return_value=mock_result):
                assert call_claude_json("test") is None

    def test_invalid_json_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="not json at all", stderr="")
            with patch("subprocess.run", return_value=mock_result):
                assert call_claude_json("test") is None


# =============================================================================
# _extract_json()
# =============================================================================


class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"key": "value"}') == {"key": "value"}

    def test_json_array(self):
        assert _extract_json("[1, 2, 3]") == [1, 2, 3]

    def test_markdown_json_block(self):
        text = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        assert _extract_json(text) == {"key": "value"}

    def test_markdown_generic_block(self):
        text = 'Output:\n```\n[1, 2]\n```'
        assert _extract_json(text) == [1, 2]

    def test_invalid_json_returns_none(self):
        assert _extract_json("this is not json") is None

    def test_whitespace_handling(self):
        assert _extract_json('  {"key": "value"}  ') == {"key": "value"}


# =============================================================================
# Integration-style tests (with mocked subprocess)
# =============================================================================


class TestCliIntegration:
    """Test the full flow of CLI calls with mocked subprocess."""

    def test_brain_db_extract_cli_first(self):
        """Verify brain_db.extract_from_text tries CLI before API."""
        from brain_db import extract_from_text

        expected = {"entities": [], "relationships": [], "preferences": []}

        with patch("claude_cli.cli_available", return_value=True):
            with patch("claude_cli.call_claude_json", return_value=expected) as mock_cli:
                result = extract_from_text("Ryan met John at the conference")
                assert result == expected
                mock_cli.assert_called_once()

    def test_brain_db_extract_falls_back_to_api(self):
        """Verify brain_db falls back to API when CLI returns None."""
        from brain_db import extract_from_text

        expected = {"entities": [], "relationships": [], "preferences": []}

        with patch("claude_cli.cli_available", return_value=False):
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=json.dumps(expected))]
                mock_client = MagicMock()
                mock_client.messages.create.return_value = mock_response
                with patch("anthropic.Anthropic", return_value=mock_client):
                    result = extract_from_text("test text")
                    assert result == expected

    def test_memory_extract_cli_first(self):
        """Verify memory.extract_and_persist tries CLI before API."""
        from memory import extract_and_persist

        with patch("claude_cli.cli_available", return_value=True):
            with patch("claude_cli.call_claude_json", return_value=[]) as mock_cli:
                result = extract_and_persist("Some conversation text")
                assert result == []
                mock_cli.assert_called_once()
