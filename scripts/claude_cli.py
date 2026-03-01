#!/usr/bin/env python3
"""
Thin wrapper around `claude -p` CLI for BeStupid.

Replaces Anthropic API calls with Claude Code CLI invocations
authenticated via CLAUDE_CODE_OAUTH_TOKEN (from Claude Max subscription).

Falls back gracefully: all functions return None when CLI is unavailable,
allowing callers to fall back to the Anthropic API.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Default timeout for one-shot calls (seconds)
DEFAULT_TIMEOUT = 120
# Default model — haiku for cheap one-shot extraction
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def cli_available() -> bool:
    """Check if claude CLI binary exists and auth token is set."""
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return False
    return shutil.which("claude") is not None


def call_claude(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_turns: int = 1,
) -> Optional[str]:
    """Shell out to `claude -p` and return raw text response.

    Returns None if CLI is unavailable or call fails (caller should fall back to API).
    """
    if not cli_available():
        return None

    cmd = [
        "claude",
        "-p",  # print mode (non-interactive)
        "--output-format", "text",
        "--max-turns", str(max_turns),
        "--model", model,
    ]

    if system_prompt:
        # Write system prompt to a temp file to avoid CLI arg length limits
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        try:
            tmp.write(system_prompt)
            tmp.close()
            cmd.extend(["--system-prompt-file", tmp.name])
        except OSError:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # Strip CLAUDECODE env var to prevent nested session detection
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        if result.returncode != 0:
            logger.warning("claude CLI failed (exit %d): %s", result.returncode, result.stderr[:500])
            return None

        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("claude CLI timed out after %ds", timeout)
        return None
    except FileNotFoundError:
        logger.warning("claude CLI binary not found")
        return None
    except OSError as e:
        logger.warning("claude CLI OS error: %s", e)
        return None
    finally:
        # Clean up system prompt temp file
        if system_prompt:
            try:
                os.unlink(tmp.name)
            except (OSError, UnboundLocalError):
                pass


def call_claude_json(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_turns: int = 1,
) -> Optional[dict | list]:
    """Shell out to `claude -p` with JSON output format and parse response.

    Returns parsed JSON (dict or list), or None if CLI unavailable / parse fails.
    """
    if not cli_available():
        return None

    cmd = [
        "claude",
        "-p",
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--model", model,
    ]

    if system_prompt:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        try:
            tmp.write(system_prompt)
            tmp.close()
            cmd.extend(["--system-prompt-file", tmp.name])
        except OSError:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        if result.returncode != 0:
            logger.warning("claude CLI JSON failed (exit %d): %s", result.returncode, result.stderr[:500])
            return None

        raw = result.stdout.strip()
        if not raw:
            return None

        # --output-format json wraps response in {"type":"result","result":"..."}
        outer = json.loads(raw)
        if isinstance(outer, dict) and "result" in outer:
            inner = outer["result"]
            # The result field contains the model's text response
            # which itself should be JSON — parse it
            if isinstance(inner, str):
                return _extract_json(inner)
            return inner

        # Direct JSON response (shouldn't happen with --output-format json, but handle it)
        return outer

    except json.JSONDecodeError as e:
        logger.warning("claude CLI JSON parse error: %s", e)
        return None
    except subprocess.TimeoutExpired:
        logger.warning("claude CLI JSON timed out after %ds", timeout)
        return None
    except FileNotFoundError:
        logger.warning("claude CLI binary not found")
        return None
    except OSError as e:
        logger.warning("claude CLI JSON OS error: %s", e)
        return None
    finally:
        if system_prompt:
            try:
                os.unlink(tmp.name)
            except (OSError, UnboundLocalError):
                pass


def _extract_json(text: str) -> Optional[dict | list]:
    """Extract JSON from text that may contain markdown code blocks."""
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to extract JSON from CLI response")
        return None
