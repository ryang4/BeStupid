"""
Per-chat agent policy persistence and prompt rendering for self-updates.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path(os.environ.get("HISTORY_DIR", str(Path.home() / ".bestupid-private")))
POLICY_FILE = HISTORY_DIR / "agent_policies.json"

MAX_RULES = 20
MAX_FOCUS_ITEMS = 10
MAX_ITEM_LEN = 220
MAX_REASON_LEN = 500


def _load_all() -> dict:
    if not POLICY_FILE.exists():
        return {}

    try:
        return json.loads(POLICY_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = POLICY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")))
    tmp.rename(POLICY_FILE)


def _sanitize_items(values: list[str], cap: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    for raw in values[:cap]:
        text = str(raw).strip().replace("\n", " ")
        if not text:
            continue
        if len(text) > MAX_ITEM_LEN:
            text = text[:MAX_ITEM_LEN]
        if text not in seen:
            seen.add(text)
            out.append(text)

    return out


def _sanitize_policy(policy: dict) -> dict:
    rules = _sanitize_items(policy.get("behavior_rules", []), MAX_RULES)
    focus = _sanitize_items(policy.get("operating_focus", []), MAX_FOCUS_ITEMS)
    reason = str(policy.get("last_reason", "")).strip()
    if len(reason) > MAX_REASON_LEN:
        reason = reason[:MAX_REASON_LEN]

    result = {
        "behavior_rules": rules,
        "operating_focus": focus,
        "last_reason": reason,
    }

    if policy.get("updated_at"):
        result["updated_at"] = str(policy["updated_at"])

    return result


def load_agent_policy(chat_id: int) -> dict:
    data = _load_all()
    raw = data.get(str(chat_id))
    if not isinstance(raw, dict):
        return {"behavior_rules": [], "operating_focus": [], "last_reason": ""}

    return _sanitize_policy(raw)


def save_agent_policy(chat_id: int, policy: dict) -> dict:
    data = _load_all()
    sanitized = _sanitize_policy(policy)
    sanitized["updated_at"] = datetime.now().isoformat()
    data[str(chat_id)] = sanitized
    _save_all(data)
    return sanitized


def apply_agent_policy_update(
    chat_id: int,
    action: str,
    rules: list[str] | None = None,
    focus: list[str] | None = None,
    reason: str = "",
) -> dict:
    current = load_agent_policy(chat_id)
    next_policy = dict(current)
    next_policy["last_reason"] = str(reason).strip()[:MAX_REASON_LEN]

    if action == "append_rules":
        merged = current.get("behavior_rules", []) + (rules or [])
        next_policy["behavior_rules"] = _sanitize_items(merged, MAX_RULES)
    elif action == "replace_rules":
        next_policy["behavior_rules"] = _sanitize_items(rules or [], MAX_RULES)
    elif action == "set_focus":
        next_policy["operating_focus"] = _sanitize_items(focus or [], MAX_FOCUS_ITEMS)
    elif action == "reset":
        next_policy["behavior_rules"] = []
        next_policy["operating_focus"] = []
        next_policy["last_reason"] = str(reason).strip()[:MAX_REASON_LEN]
    else:
        raise ValueError(f"Unknown action: {action}")

    return save_agent_policy(chat_id, next_policy)


def format_agent_policy(policy: dict) -> str:
    policy = _sanitize_policy(policy)
    rules = policy.get("behavior_rules", [])
    focus = policy.get("operating_focus", [])
    reason = policy.get("last_reason", "")
    updated_at = policy.get("updated_at", "")

    lines = ["*Agent Self-Update Policy*"]

    if rules:
        lines.append("Rules:")
        for idx, rule in enumerate(rules, start=1):
            lines.append(f"{idx}. {rule}")
    else:
        lines.append("Rules: none")

    if focus:
        lines.append("Focus:")
        for idx, item in enumerate(focus, start=1):
            lines.append(f"{idx}. {item}")
    else:
        lines.append("Focus: none")

    if reason:
        lines.append(f"Last reason: {reason}")
    if updated_at:
        lines.append(f"Updated: `{updated_at}`")

    return "\n".join(lines)


def render_agent_policy_instructions(policy: dict) -> str:
    policy = _sanitize_policy(policy)
    rules = policy.get("behavior_rules", [])
    focus = policy.get("operating_focus", [])
    if not rules and not focus:
        return ""

    lines = ["SELF-UPDATED OPERATING POLICY (apply unless user overrides):"]

    if rules:
        lines.append("- Rules:")
        for rule in rules:
            lines.append(f"  - {rule}")

    if focus:
        lines.append("- Focus priorities:")
        for item in focus:
            lines.append(f"  - {item}")

    return "\n".join(lines)
