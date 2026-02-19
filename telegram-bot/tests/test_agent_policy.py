"""
Tests for self-updating agent policy storage and rendering.
"""

from unittest.mock import patch


def test_policy_roundtrip(tmp_path):
    private_dir = tmp_path / ".bestupid-private"
    policy_file = private_dir / "agent_policies.json"

    with patch("agent_policy.HISTORY_DIR", private_dir):
        with patch("agent_policy.POLICY_FILE", policy_file):
            from agent_policy import load_agent_policy, save_agent_policy

            save_agent_policy(
                chat_id=42,
                policy={
                    "behavior_rules": ["Use concrete next steps", "Default to active follow-up"],
                    "operating_focus": ["Close loops same day"],
                    "last_reason": "Missed follow-through on unresolved tasks",
                },
            )
            loaded = load_agent_policy(42)

            assert loaded["behavior_rules"] == [
                "Use concrete next steps",
                "Default to active follow-up",
            ]
            assert loaded["operating_focus"] == ["Close loops same day"]
            assert loaded["last_reason"] == "Missed follow-through on unresolved tasks"


def test_apply_policy_update_actions(tmp_path):
    private_dir = tmp_path / ".bestupid-private"
    policy_file = private_dir / "agent_policies.json"

    with patch("agent_policy.HISTORY_DIR", private_dir):
        with patch("agent_policy.POLICY_FILE", policy_file):
            from agent_policy import apply_agent_policy_update, load_agent_policy

            apply_agent_policy_update(
                chat_id=99,
                action="append_rules",
                rules=["Prioritize blocker removal"],
                reason="Task flow blocked",
            )
            apply_agent_policy_update(
                chat_id=99,
                action="set_focus",
                focus=["Production launch path"],
                reason="Highest leverage focus",
            )
            policy = load_agent_policy(99)

            assert "Prioritize blocker removal" in policy["behavior_rules"]
            assert policy["operating_focus"] == ["Production launch path"]

            reset = apply_agent_policy_update(
                chat_id=99,
                action="reset",
                reason="Fresh start",
            )
            assert reset["behavior_rules"] == []
            assert reset["operating_focus"] == []


def test_render_policy_instructions_has_sections():
    from agent_policy import render_agent_policy_instructions

    instructions = render_agent_policy_instructions(
        {
            "behavior_rules": ["Be explicit about assumptions"],
            "operating_focus": ["Reduce context switching"],
            "last_reason": "Quality drift",
        }
    )

    assert "SELF-UPDATED OPERATING POLICY" in instructions
    assert "Be explicit about assumptions" in instructions
    assert "Reduce context switching" in instructions
