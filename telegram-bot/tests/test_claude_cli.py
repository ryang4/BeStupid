"""
Tests for the Claude Code CLI wrapper module.
"""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

# Import from scripts/
from claude_cli import _extract_json, _run_cli, call_claude, call_claude_json, cli_available


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
                with patch("memory.append_event"):
                    result = extract_and_persist("Some conversation text")
                    assert result == []
                    mock_cli.assert_called_once()


# =============================================================================
# _run_cli() — shared subprocess helper
# =============================================================================


class TestRunCli:
    def test_returns_none_when_unavailable(self):
        with patch("claude_cli.cli_available", return_value=False):
            assert _run_cli("hello") is None

    def test_returns_completed_process_on_success(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
            with patch("subprocess.run", return_value=mock_result):
                result = _run_cli("test")
                assert result is not None
                assert result.stdout == "ok"

    def test_returns_none_on_nonzero_exit(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=1, stdout="", stderr="fail")
            with patch("subprocess.run", return_value=mock_result):
                assert _run_cli("test") is None

    def test_output_format_passed_to_cmd(self):
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                _run_cli("test", output_format="json")
                cmd = mock_run.call_args[0][0]
                fmt_idx = cmd.index("--output-format")
                assert cmd[fmt_idx + 1] == "json"

    def test_system_prompt_temp_file_cleanup(self):
        """Verify temp file is cleaned up even on success."""
        with patch("claude_cli.cli_available", return_value=True):
            mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                _run_cli("test", system_prompt="Be helpful")
                cmd = mock_run.call_args[0][0]
                assert "--system-prompt-file" in cmd
                # The temp file path from the command
                sp_idx = cmd.index("--system-prompt-file")
                tmp_path = cmd[sp_idx + 1]
                # Temp file should have been cleaned up
                assert not os.path.exists(tmp_path)

    def test_timeout_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 120)):
                assert _run_cli("test") is None

    def test_file_not_found_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                assert _run_cli("test") is None

    def test_os_error_returns_none(self):
        with patch("claude_cli.cli_available", return_value=True):
            with patch("subprocess.run", side_effect=OSError("disk full")):
                assert _run_cli("test") is None


# =============================================================================
# claude_client.py helpers
# =============================================================================


class TestClaudeClientHelpers:
    """Tests for _cli_available, _build_tool_docs, _format_history_for_cli, _tool_runner_path."""

    def test_cli_available_disabled_by_flag(self):
        """_cli_available returns False when USE_CLI_MAIN_LOOP is disabled."""
        import claude_client
        original = claude_client.USE_CLI_MAIN_LOOP
        try:
            claude_client.USE_CLI_MAIN_LOOP = False
            assert claude_client._cli_available() is False
        finally:
            claude_client.USE_CLI_MAIN_LOOP = original

    def test_cli_available_delegates_to_cli_module(self):
        """_cli_available returns True when flag enabled and cli_available() returns True."""
        import claude_client
        original = claude_client.USE_CLI_MAIN_LOOP
        try:
            claude_client.USE_CLI_MAIN_LOOP = True
            with patch("claude_cli.cli_available", return_value=True):
                assert claude_client._cli_available() is True
        finally:
            claude_client.USE_CLI_MAIN_LOOP = original

    def test_cli_available_import_error(self):
        """_cli_available returns False when claude_cli module not importable."""
        import claude_client
        original = claude_client.USE_CLI_MAIN_LOOP
        try:
            claude_client.USE_CLI_MAIN_LOOP = True
            with patch.dict("sys.modules", {"claude_cli": None}):
                # Force re-import to fail
                with patch("builtins.__import__", side_effect=ImportError):
                    assert claude_client._cli_available() is False
        finally:
            claude_client.USE_CLI_MAIN_LOOP = original

    def test_tool_runner_path_is_sibling(self):
        """_tool_runner_path returns tool_runner.py in the same dir as claude_client.py."""
        import claude_client
        result = claude_client._tool_runner_path()
        assert result.endswith("tool_runner.py")
        from pathlib import Path
        assert Path(result).parent == Path(claude_client.__file__).parent

    def test_build_tool_docs_contains_tool_names(self):
        """_build_tool_docs includes each tool name from TOOLS."""
        import claude_client
        docs = claude_client._build_tool_docs()
        assert "AVAILABLE TOOLS:" in docs
        # Should contain at least one tool
        from tools_v2 import TOOLS
        for tool in TOOLS[:3]:  # Check first 3 tools
            assert tool["name"] in docs

    def test_build_tool_docs_uses_dynamic_path(self):
        """_build_tool_docs uses _tool_runner_path() not hardcoded /app/."""
        import claude_client
        docs = claude_client._build_tool_docs()
        expected_path = claude_client._tool_runner_path()
        assert expected_path in docs

    def test_format_history_simple_text(self):
        """_format_history_for_cli handles simple string content."""
        import claude_client
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = claude_client._format_history_for_cli(history)
        assert "[USER]: hello" in result
        assert "[ASSISTANT]: hi there" in result

    def test_format_history_tool_blocks(self):
        """_format_history_for_cli handles tool_use and tool_result blocks."""
        import claude_client
        history = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check"},
                    {"type": "tool_use", "name": "read_file", "input": {"path": "/tmp/test"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": "file contents here"},
                ],
            },
        ]
        result = claude_client._format_history_for_cli(history)
        assert "[ASSISTANT]: Let me check" in result
        assert "[TOOL CALL]: read_file" in result
        assert "[TOOL RESULT]: file contents here" in result

    def test_format_history_truncation_marker(self):
        """_format_history_for_cli adds truncation marker for long tool results."""
        import claude_client
        long_content = "x" * 600
        history = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": long_content},
                ],
            },
        ]
        result = claude_client._format_history_for_cli(history)
        assert "...(truncated)" in result
        # Should not contain the full content
        assert long_content not in result

    def test_format_history_no_truncation_for_short_content(self):
        """_format_history_for_cli does NOT add truncation for short results."""
        import claude_client
        short_content = "x" * 100
        history = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": short_content},
                ],
            },
        ]
        result = claude_client._format_history_for_cli(history)
        assert "...(truncated)" not in result
        assert short_content in result

    def test_format_history_empty(self):
        """_format_history_for_cli handles empty history."""
        import claude_client
        assert claude_client._format_history_for_cli([]) == ""


# =============================================================================
# run_tool_loop dispatch tests
# =============================================================================


class TestRunToolLoopDispatch:
    """Test CLI-first / API-fallback dispatch in run_tool_loop."""

    @pytest.mark.asyncio
    async def test_cli_success_skips_api(self):
        """When CLI returns a response, API is never called."""
        import claude_client
        state = claude_client.ConversationState()
        with patch.object(claude_client, "_cli_available", return_value=True):
            with patch.object(claude_client, "_run_tool_loop_cli", return_value="CLI response") as mock_cli:
                with patch.object(claude_client.client.messages, "create") as mock_api:
                    result = await claude_client.run_tool_loop(state, "hello")
                    assert result == "CLI response"
                    mock_cli.assert_called_once()
                    mock_api.assert_not_called()

    @pytest.mark.asyncio
    async def test_cli_empty_falls_back_to_api(self):
        """When CLI returns empty string, falls back to API."""
        import claude_client
        state = claude_client.ConversationState()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="API response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(claude_client, "_cli_available", return_value=True):
            with patch.object(claude_client, "_run_tool_loop_cli", return_value=""):
                with patch.object(claude_client, "build_system_messages", return_value=[{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}]):
                    with patch("asyncio.to_thread", return_value=mock_response):
                        result = await claude_client.run_tool_loop(state, "hello")
                        assert result == "API response"

    @pytest.mark.asyncio
    async def test_cli_unavailable_goes_straight_to_api(self):
        """When CLI is unavailable, goes directly to API."""
        import claude_client
        state = claude_client.ConversationState()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="API response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(claude_client, "_cli_available", return_value=False):
            with patch.object(claude_client, "_run_tool_loop_cli") as mock_cli:
                with patch.object(claude_client, "build_system_messages", return_value=[{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}]):
                    with patch("asyncio.to_thread", return_value=mock_response):
                        result = await claude_client.run_tool_loop(state, "hello")
                        assert result == "API response"
                        mock_cli.assert_not_called()

    @pytest.mark.asyncio
    async def test_cli_exception_falls_back_to_api(self):
        """When CLI raises an exception, falls back to API."""
        import claude_client
        state = claude_client.ConversationState()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="API fallback")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        with patch.object(claude_client, "_cli_available", return_value=True):
            with patch.object(claude_client, "_run_tool_loop_cli", side_effect=RuntimeError("boom")):
                with patch.object(claude_client, "build_system_messages", return_value=[{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}]):
                    with patch("asyncio.to_thread", return_value=mock_response):
                        result = await claude_client.run_tool_loop(state, "hello")
                        assert result == "API fallback"
