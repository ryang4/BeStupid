"""
Persona profile persistence and prompt rendering for the Telegram assistant.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
PROFILE_FILE = HISTORY_DIR / "persona_profiles.json"

PERSONA_CHOICES = {
    "operator": {
        "label": "Operator",
        "description": "Direct, tactical, and execution-first with minimal fluff.",
    },
    "coach": {
        "label": "Coach",
        "description": "Supportive and motivating while staying specific and practical.",
    },
    "drill_sergeant": {
        "label": "Drill Sergeant",
        "description": "Blunt, high-accountability, and willing to challenge excuses.",
    },
    "strategist": {
        "label": "Strategist",
        "description": "Calm, analytical, and leverage-focused in decision making.",
    },
}

PUSH_CHOICES = {
    "gentle": {
        "label": "Gentle",
        "description": "Use light nudges and minimal confrontation.",
    },
    "firm": {
        "label": "Firm",
        "description": "Use direct nudges and call out drift clearly.",
    },
    "hard": {
        "label": "Hard",
        "description": "Use high-pressure accountability and challenge avoidance.",
    },
}

INITIATIVE_CHOICES = {
    "ask_first": {
        "label": "Ask First",
        "description": "Clarify before acting when requirements are not explicit.",
    },
    "balanced": {
        "label": "Balanced",
        "description": "Act on obvious next steps, ask only when risk is meaningful.",
    },
    "act_first": {
        "label": "Act First",
        "description": "Default to initiative and execution, then report outcomes.",
    },
}

RESPONSE_STYLE_CHOICES = {
    "checklist": {
        "label": "Checklist",
        "description": "Use terse, action-first bullet points.",
    },
    "concise": {
        "label": "Concise",
        "description": "Use short prose with only essential details.",
    },
    "mixed": {
        "label": "Mixed",
        "description": "Use concise prose plus bullets when helpful.",
    },
}


def _load_profiles() -> dict:
    if not PROFILE_FILE.exists():
        return {}

    try:
        return json.loads(PROFILE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_profiles(data: dict):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PROFILE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")))
    tmp.rename(PROFILE_FILE)


def _sanitize_choice(value: str, choices: dict, default: str) -> str:
    if value in choices:
        return value
    return default


def _sanitize_profile(profile: dict) -> dict:
    persona = _sanitize_choice(profile.get("persona", ""), PERSONA_CHOICES, "operator")
    push_intensity = _sanitize_choice(profile.get("push_intensity", ""), PUSH_CHOICES, "firm")
    initiative = _sanitize_choice(profile.get("initiative", ""), INITIATIVE_CHOICES, "balanced")
    response_style = _sanitize_choice(profile.get("response_style", ""), RESPONSE_STYLE_CHOICES, "checklist")

    signature_phrase = str(profile.get("signature_phrase", "")).strip()
    if signature_phrase.lower() == "none":
        signature_phrase = ""
    if len(signature_phrase) > 80:
        signature_phrase = signature_phrase[:80]

    return {
        "persona": persona,
        "push_intensity": push_intensity,
        "initiative": initiative,
        "response_style": response_style,
        "signature_phrase": signature_phrase,
    }


def load_persona_profile(chat_id: int) -> dict:
    data = _load_profiles()
    raw = data.get(str(chat_id))
    if not isinstance(raw, dict):
        return {}

    profile = _sanitize_profile(raw)
    if "updated_at" in raw:
        profile["updated_at"] = raw["updated_at"]
    return profile


def save_persona_profile(chat_id: int, profile: dict) -> dict:
    data = _load_profiles()
    sanitized = _sanitize_profile(profile)
    sanitized["updated_at"] = datetime.now().isoformat()

    data[str(chat_id)] = sanitized
    _save_profiles(data)
    return sanitized


def clear_persona_profile(chat_id: int) -> bool:
    data = _load_profiles()
    key = str(chat_id)
    if key not in data:
        return False

    del data[key]
    _save_profiles(data)
    return True


def _label_for(choices: dict, value: str) -> str:
    return choices.get(value, {}).get("label", value)


def _description_for(choices: dict, value: str) -> str:
    return choices.get(value, {}).get("description", "")


def format_persona_summary(profile: dict) -> str:
    if not profile:
        return "No persona profile is configured yet. Run /onboard to set it up."

    lines = [
        "*Current Persona Profile*",
        f"- Archetype: {_label_for(PERSONA_CHOICES, profile.get('persona', ''))}",
        f"- Push level: {_label_for(PUSH_CHOICES, profile.get('push_intensity', ''))}",
        f"- Initiative: {_label_for(INITIATIVE_CHOICES, profile.get('initiative', ''))}",
        f"- Response style: {_label_for(RESPONSE_STYLE_CHOICES, profile.get('response_style', ''))}",
    ]

    phrase = profile.get("signature_phrase", "")
    if phrase:
        lines.append(f"- Signature phrase: `{phrase}`")

    updated_at = profile.get("updated_at")
    if updated_at:
        lines.append(f"- Updated: `{updated_at}`")

    return "\n".join(lines)


def render_persona_instructions(profile: dict) -> str:
    if not profile:
        return ""

    persona = profile.get("persona", "operator")
    push_intensity = profile.get("push_intensity", "firm")
    initiative = profile.get("initiative", "balanced")
    response_style = profile.get("response_style", "checklist")

    lines = [
        "USER-CONFIGURED PERSONALITY DIRECTIVES:",
        f"- Archetype: {_label_for(PERSONA_CHOICES, persona)}. {_description_for(PERSONA_CHOICES, persona)}",
        f"- Accountability intensity: {_label_for(PUSH_CHOICES, push_intensity)}. {_description_for(PUSH_CHOICES, push_intensity)}",
        f"- Initiative policy: {_label_for(INITIATIVE_CHOICES, initiative)}. {_description_for(INITIATIVE_CHOICES, initiative)}",
        f"- Response format: {_label_for(RESPONSE_STYLE_CHOICES, response_style)}. {_description_for(RESPONSE_STYLE_CHOICES, response_style)}",
        "- Keep recommendations concrete and execution-oriented.",
    ]

    signature_phrase = profile.get("signature_phrase", "")
    if signature_phrase:
        lines.append(
            f"- Voice flavor: You may use `{signature_phrase}` sparingly (at most once per reply)."
        )

    return "\n".join(lines)
