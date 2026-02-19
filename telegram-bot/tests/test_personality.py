"""
Tests for persona profile persistence and prompt rendering.
"""

from unittest.mock import patch


def test_save_and_load_profile_roundtrip(tmp_path):
    private_dir = tmp_path / ".bestupid-private"
    profile_file = private_dir / "persona_profiles.json"

    with patch("personality.HISTORY_DIR", private_dir):
        with patch("personality.PROFILE_FILE", profile_file):
            from personality import load_persona_profile, save_persona_profile

            saved = save_persona_profile(
                chat_id=123,
                profile={
                    "persona": "drill_sergeant",
                    "push_intensity": "hard",
                    "initiative": "act_first",
                    "response_style": "checklist",
                    "signature_phrase": "No drift.",
                },
            )

            loaded = load_persona_profile(123)

            assert loaded["persona"] == "drill_sergeant"
            assert loaded["push_intensity"] == "hard"
            assert loaded["initiative"] == "act_first"
            assert loaded["response_style"] == "checklist"
            assert loaded["signature_phrase"] == "No drift."
            assert "updated_at" in saved


def test_invalid_values_are_sanitized(tmp_path):
    private_dir = tmp_path / ".bestupid-private"
    profile_file = private_dir / "persona_profiles.json"

    with patch("personality.HISTORY_DIR", private_dir):
        with patch("personality.PROFILE_FILE", profile_file):
            from personality import save_persona_profile

            saved = save_persona_profile(
                chat_id=321,
                profile={
                    "persona": "unknown",
                    "push_intensity": "unknown",
                    "initiative": "unknown",
                    "response_style": "unknown",
                    "signature_phrase": "x" * 1000,
                },
            )

            assert saved["persona"] == "operator"
            assert saved["push_intensity"] == "firm"
            assert saved["initiative"] == "balanced"
            assert saved["response_style"] == "checklist"
            assert len(saved["signature_phrase"]) == 80


def test_render_instructions_uses_profile_values():
    from personality import render_persona_instructions

    instructions = render_persona_instructions(
        {
            "persona": "coach",
            "push_intensity": "firm",
            "initiative": "balanced",
            "response_style": "mixed",
            "signature_phrase": "Let's execute.",
        }
    )

    assert "USER-CONFIGURED PERSONALITY DIRECTIVES" in instructions
    assert "Coach" in instructions
    assert "Firm" in instructions
    assert "Balanced" in instructions
    assert "Mixed" in instructions
    assert "Let's execute." in instructions
