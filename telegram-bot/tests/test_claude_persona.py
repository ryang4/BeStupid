"""
Tests for persona prompt injection in claude_client.
"""

from unittest.mock import patch


def test_build_system_messages_injects_persona_directives():
    from claude_client import build_system_messages

    with patch("claude_client.load_persona_profile", return_value={"persona": "operator"}):
        with patch("claude_client.render_persona_instructions", return_value="PERSONA BLOCK"):
            with patch("claude_client.load_agent_policy", return_value={"behavior_rules": []}):
                with patch("claude_client.render_agent_policy_instructions", return_value="POLICY BLOCK"):
                    messages = build_system_messages(chat_id=123)

    assert len(messages) == 1
    assert "PERSONA BLOCK" in messages[0]["text"]
    assert "POLICY BLOCK" in messages[0]["text"]


def test_build_system_messages_without_chat_id_uses_base_prompt_only():
    from claude_client import SYSTEM_PROMPT, build_system_messages

    messages = build_system_messages(chat_id=0)

    assert len(messages) == 1
    assert messages[0]["text"] == SYSTEM_PROMPT
