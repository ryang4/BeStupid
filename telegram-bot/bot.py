#!/usr/bin/env python3
"""
BeStupid Telegram Bot - Personal productivity assistant powered by Anthropic SDK.
Thin Telegram layer; all Claude logic lives in claude_client.py.
"""

import os
import sys
import logging
import asyncio
import subprocess
import re
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from claude_client import ConversationState, run_tool_loop, MODEL, DAILY_TOKEN_BUDGET, get_model_pricing
from agent_policy import apply_agent_policy_update, format_agent_policy, load_agent_policy
from personality import (
    PERSONA_CHOICES,
    PUSH_CHOICES,
    INITIATIVE_CHOICES,
    RESPONSE_STYLE_CHOICES,
    clear_persona_profile,
    format_persona_summary,
    load_persona_profile,
    save_persona_profile,
)
from heartbeat import get_health_status, get_heartbeat_monitor, init_heartbeat_monitor
from scheduler import start_scheduler
from v2.bootstrap import get_services

load_dotenv(Path(__file__).parent / ".env")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", str(Path(__file__).resolve().parent.parent)))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Per-chat state
_conversations: dict[int, ConversationState] = {}
_chat_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
_onboarding_sessions: dict[int, dict] = {}
_heartbeat_task: asyncio.Task | None = None


def _get_conversation(chat_id: int) -> ConversationState:
    """Get or load conversation state for a chat."""
    if chat_id not in _conversations:
        _conversations[chat_id] = ConversationState.load_from_disk(chat_id)
    return _conversations[chat_id]


ONBOARD_PERSONA_CHOICES = {
    "1": "operator",
    "2": "coach",
    "3": "drill_sergeant",
    "4": "strategist",
}

ONBOARD_PUSH_CHOICES = {
    "1": "gentle",
    "2": "firm",
    "3": "hard",
}

ONBOARD_INITIATIVE_CHOICES = {
    "1": "ask_first",
    "2": "balanced",
    "3": "act_first",
}

ONBOARD_RESPONSE_STYLE_CHOICES = {
    "1": "checklist",
    "2": "concise",
    "3": "mixed",
}


def _choice_lines(choices: dict[str, str], metadata: dict) -> list[str]:
    lines = []
    for key, value in choices.items():
        label = metadata.get(value, {}).get("label", value)
        desc = metadata.get(value, {}).get("description", "")
        lines.append(f"{key}. *{label}* - {desc}")
    return lines


def _parse_choice(text: str, choices: dict[str, str], metadata: dict) -> str:
    normalized = text.strip().lower()
    if normalized in choices:
        return choices[normalized]

    for value in choices.values():
        if normalized == value:
            return value
        if normalized == metadata.get(value, {}).get("label", "").lower():
            return value

    return ""


def _get_onboarding_prompt(step: int) -> str:
    if step == 1:
        lines = [
            "*Persona Onboarding (1/5)*",
            "Choose an assistant archetype:",
            *_choice_lines(ONBOARD_PERSONA_CHOICES, PERSONA_CHOICES),
            "",
            "Reply with the number or name.",
        ]
        return "\n".join(lines)

    if step == 2:
        lines = [
            "*Persona Onboarding (2/5)*",
            "How hard should I push when you drift?",
            *_choice_lines(ONBOARD_PUSH_CHOICES, PUSH_CHOICES),
            "",
            "Reply with the number or name.",
        ]
        return "\n".join(lines)

    if step == 3:
        lines = [
            "*Persona Onboarding (3/5)*",
            "When requirements are not fully specified, what should I do?",
            *_choice_lines(ONBOARD_INITIATIVE_CHOICES, INITIATIVE_CHOICES),
            "",
            "Reply with the number or name.",
        ]
        return "\n".join(lines)

    if step == 4:
        lines = [
            "*Persona Onboarding (4/5)*",
            "Preferred response style:",
            *_choice_lines(ONBOARD_RESPONSE_STYLE_CHOICES, RESPONSE_STYLE_CHOICES),
            "",
            "Reply with the number or name.",
        ]
        return "\n".join(lines)

    return (
        "*Persona Onboarding (5/5)*\n"
        "Optional: share a short phrase I can use sparingly for flavor.\n"
        "Reply with a phrase, or `none` to skip."
    )


def _start_onboarding(chat_id: int) -> str:
    _onboarding_sessions[chat_id] = {"step": 1, "answers": {}}
    return _get_onboarding_prompt(1)


def _apply_onboarding_answer(chat_id: int, user_text: str) -> tuple[str, bool]:
    session = _onboarding_sessions.get(chat_id)
    if not session:
        return "No active onboarding session. Run /onboard to start.", True

    step = session["step"]
    answers = session["answers"]

    if step == 1:
        parsed = _parse_choice(user_text, ONBOARD_PERSONA_CHOICES, PERSONA_CHOICES)
        if not parsed:
            return "Please choose one of the listed archetypes.\n\n" + _get_onboarding_prompt(step), False
        answers["persona"] = parsed
        session["step"] = 2
        return _get_onboarding_prompt(2), False

    if step == 2:
        parsed = _parse_choice(user_text, ONBOARD_PUSH_CHOICES, PUSH_CHOICES)
        if not parsed:
            return "Please choose one of the listed push levels.\n\n" + _get_onboarding_prompt(step), False
        answers["push_intensity"] = parsed
        session["step"] = 3
        return _get_onboarding_prompt(3), False

    if step == 3:
        parsed = _parse_choice(user_text, ONBOARD_INITIATIVE_CHOICES, INITIATIVE_CHOICES)
        if not parsed:
            return "Please choose one of the listed initiative modes.\n\n" + _get_onboarding_prompt(step), False
        answers["initiative"] = parsed
        session["step"] = 4
        return _get_onboarding_prompt(4), False

    if step == 4:
        parsed = _parse_choice(user_text, ONBOARD_RESPONSE_STYLE_CHOICES, RESPONSE_STYLE_CHOICES)
        if not parsed:
            return "Please choose one of the listed response styles.\n\n" + _get_onboarding_prompt(step), False
        answers["response_style"] = parsed
        session["step"] = 5
        return _get_onboarding_prompt(5), False

    signature_phrase = user_text.strip()
    if signature_phrase.lower() == "none":
        signature_phrase = ""
    answers["signature_phrase"] = signature_phrase

    profile = save_persona_profile(chat_id, answers)
    del _onboarding_sessions[chat_id]

    return (
        "Persona setup complete.\n\n"
        + format_persona_summary(profile)
        + "\n\nThis profile is now injected into your assistant prompt."
    ), True


def _render_v2_context(chat_id: int) -> str:
    services = get_services()
    resolved = services.timezone_resolver.resolve_now(chat_id)
    services.store.ensure_day_open(resolved)
    envelope = services.context_assembler.build(chat_id, user_text="")
    return envelope.dynamic_system_prompt or "No V2 context available."


def _preprocess_user_corrections(chat_id: int, user_text: str):
    """Apply explicit day/time corrections before the model sees the message."""
    services = get_services()
    timezone_match = re.search(
        r"\b(?:i am at|i'm at|my timezone is|timezone is)\s+([A-Za-z_]+\/[A-Za-z_]+|UTC[+-]\d{1,2}(?::?\d{2})?|[+-]\d{1,2}(?::?\d{2})?)",
        user_text,
        re.IGNORECASE,
    )
    if timezone_match:
        tz_text = timezone_match.group(1).strip()
        services.timezone_resolver.set_current_timezone(chat_id, tz_text, source="explicit_user")

    day_match = re.search(r"\btoday is ([A-Za-z]+)\b", user_text, re.IGNORECASE)
    if day_match:
        resolved = services.timezone_resolver.resolve_now(chat_id)
        services.store.record_day_correction(
            chat_id,
            resolved.local_date,
            f"User corrected the day reference to {day_match.group(1).strip().title()}",
        )


def _run_auto_backup():
    """Run auto_backup.sh (fire-and-forget)."""
    try:
        subprocess.run(
            ["bash", str(SCRIPTS_DIR / "auto_backup.sh")],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT),
        )
    except Exception as e:
        logger.error(f"Auto backup failed: {e}")


def _run_memory_extract(text: str):
    """Run legacy memory extraction fire-and-forget path for compatibility."""
    try:
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "memory.py"), "extract", text],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")


def _is_authorized(update: Update) -> bool:
    return not OWNER_CHAT_ID or update.effective_chat.id == OWNER_CHAT_ID


async def _send_message(update: Update, text: str):
    """Send message with Markdown fallback to plain text."""
    for chunk in _split_message(text):
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except BadRequest:
            await update.message.reply_text(chunk)


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks


async def _post_init(app: Application):
    """Initialize async background services after the bot event loop starts."""
    del app  # Unused
    interval_minutes = int(os.environ.get("HEARTBEAT_INTERVAL_MINUTES", "60"))
    monitor = init_heartbeat_monitor(interval_minutes=interval_minutes)
    global _heartbeat_task
    _heartbeat_task = asyncio.create_task(monitor.run_forever(), name="heartbeat-monitor")
    logger.info(f"Heartbeat monitor started ({interval_minutes} minute interval)")


async def _post_shutdown(app: Application):
    """Stop async background services cleanly."""
    del app  # Unused
    monitor = get_heartbeat_monitor()
    if monitor:
        monitor.stop()

    global _heartbeat_task
    if _heartbeat_task:
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass
        _heartbeat_task = None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        await update.message.reply_text("Unauthorized.")
        return

    chat_id = update.effective_chat.id
    lock = _chat_locks[chat_id]

    if lock.locked():
        await update.message.reply_text("Still working on your previous message...")
        return

    async with lock:
        services = get_services()
        state = _get_conversation(chat_id)
        user_text = (update.message.text or "").strip()
        monitor = get_heartbeat_monitor()
        if monitor:
            monitor.record_activity()

        if chat_id in _onboarding_sessions:
            onboarding_reply, _ = _apply_onboarding_answer(chat_id, user_text)
            await _send_message(update, onboarding_reply)
            return

        if not services.store.mark_update_processed(chat_id, update.update_id):
            logger.info("Skipping duplicate Telegram update %s for chat %s", update.update_id, chat_id)
            return

        _preprocess_user_corrections(chat_id, user_text)
        resolved = services.timezone_resolver.resolve_now(chat_id)
        day = services.store.ensure_day_open(resolved)

        async def typing_callback():
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        await typing_callback()

        try:
            response = await run_tool_loop(
                state,
                user_text,
                typing_callback=typing_callback,
                chat_id=chat_id,
            )
        except Exception as e:
            logger.error(f"Claude error: {e}")
            error_name = type(e).__name__
            response = f"Error ({error_name}): {e}"

        await _send_message(update, response)

        session = services.store.get_or_create_session(chat_id, resolved.utc_now)
        user_turn_id = services.store.record_turn(
            chat_id=chat_id,
            session_id=session["session_id"],
            update_id=update.update_id,
            role="user",
            text=user_text,
        )
        services.memory_review.extract_candidates(chat_id, user_turn_id, user_text)
        services.store.record_turn(
            chat_id=chat_id,
            session_id=session["session_id"],
            update_id=update.update_id,
            role="assistant",
            text=response,
        )
        services.store.refresh_session_summary(session["session_id"])
        services.projection.render_private_day_log(day["day_id"])

        # Fire-and-forget: keep existing backup behavior for resilience.
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _run_auto_backup)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    await update.message.reply_text(
        "BeStupid assistant (V2 core)\n\n"
        "Just chat naturally:\n"
        "- 'Log weight 241'\n"
        "- 'I am at UTC-5'\n"
        "- 'Remember that John is my accountant'\n"
        "- 'Remind me to follow up with Sarah tomorrow'\n\n"
        "/today - Show canonical day snapshot\n"
        "/travel - Update current timezone\n"
        "/review - Review pending memory candidates\n"
        "/followups - Show due open loops and follow-ups\n"
        "/snooze - Snooze an open loop by id or title\n"
        "/close_day - Close the current local day\n"
        "/context - Show current V2 dynamic context\n"
        "/health - Bot health + heartbeat status\n"
        "/cost - Token usage\n"
        "/onboard - Configure assistant personality\n"
        "/persona - Show current personality profile\n"
        "/resetpersona - Clear profile and re-onboard\n"
        "/policy - Show self-updated agent policy\n"
        "/resetpolicy - Reset self-updated agent policy"
    )


async def cmd_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    del context
    chat_id = update.effective_chat.id
    await _send_message(update, _render_v2_context(chat_id))


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    del context  # Unused
    await _send_message(update, get_health_status())


async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    chat_id = update.effective_chat.id
    state = _get_conversation(chat_id)

    input_price, output_price = get_model_pricing()
    input_cost = state.total_input_tokens * input_price / 1_000_000
    output_cost = state.total_output_tokens * output_price / 1_000_000
    total = input_cost + output_cost

    daily_used = state.daily_input_tokens + state.daily_output_tokens
    daily_pct = min(100, round(daily_used * 100 / DAILY_TOKEN_BUDGET)) if DAILY_TOKEN_BUDGET else 0

    await update.message.reply_text(
        f"Model: {MODEL}\n"
        f"Input tokens: {state.total_input_tokens:,}\n"
        f"Output tokens: {state.total_output_tokens:,}\n"
        f"Estimated cost: ${total:.4f}\n\n"
        f"Daily budget: {daily_used:,} / {DAILY_TOKEN_BUDGET:,} ({daily_pct}%)"
    )


async def cmd_onboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    chat_id = update.effective_chat.id
    prompt = _start_onboarding(chat_id)
    await _send_message(update, prompt)


async def cmd_persona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    chat_id = update.effective_chat.id
    profile = load_persona_profile(chat_id)
    await _send_message(update, format_persona_summary(profile))


async def cmd_resetpersona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    chat_id = update.effective_chat.id
    _onboarding_sessions.pop(chat_id, None)
    clear_persona_profile(chat_id)
    prompt = _start_onboarding(chat_id)
    await _send_message(update, "Persona profile cleared.\n\n" + prompt)


async def cmd_policy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    chat_id = update.effective_chat.id
    policy = load_agent_policy(chat_id)
    await _send_message(update, format_agent_policy(policy))


async def cmd_resetpolicy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return

    chat_id = update.effective_chat.id
    updated = apply_agent_policy_update(
        chat_id=chat_id,
        action="reset",
        reason="Manual reset via /resetpolicy",
    )
    await _send_message(update, "Agent policy reset.\n\n" + format_agent_policy(updated))


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    del context
    chat_id = update.effective_chat.id
    services = get_services()
    resolved = services.timezone_resolver.resolve_now(chat_id)
    services.store.ensure_day_open(resolved)
    snapshot = services.store.get_day_snapshot(chat_id, resolved.local_date)
    if not snapshot:
        await _send_message(update, "No current day snapshot is available.")
        return
    lines = [
        f"*Today* `{snapshot.local_date}`",
        f"- Timezone: `{snapshot.timezone}`",
        f"- Status: `{snapshot.status}`",
        f"- State version: `{snapshot.state_version}`",
    ]
    if snapshot.metrics:
        lines.append("- Metrics:")
        for field, value in sorted(snapshot.metrics.items()):
            lines.append(f"  `{field}` = {value}")
    if snapshot.habits:
        lines.append("- Habits:")
        for habit in snapshot.habits:
            lines.append(f"  {habit['name']}: `{habit['status']}`")
    if snapshot.open_loops:
        lines.append("- Open loops:")
        for item in snapshot.open_loops[:5]:
            lines.append(f"  `{item['loop_id']}` [{item['priority']}] {item['title']}")
    await _send_message(update, "\n".join(lines))


async def cmd_travel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    chat_id = update.effective_chat.id
    services = get_services()
    timezone_text = " ".join(context.args).strip()
    if not timezone_text:
        resolved = services.timezone_resolver.resolve_now(chat_id)
        await _send_message(update, f"Current timezone: `{resolved.timezone_label}`. Use `/travel America/Los_Angeles` or `/travel UTC-5`.")
        return
    resolved = services.timezone_resolver.set_current_timezone(chat_id, timezone_text, source="explicit_user")
    services.store.ensure_day_open(resolved)
    await _send_message(update, f"Timezone updated to `{resolved.timezone_label}`. Local date is `{resolved.local_date}`.")


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    chat_id = update.effective_chat.id
    services = get_services()
    if len(context.args) >= 2:
        candidate_id = context.args[0]
        action = context.args[1].lower()
        result = services.memory_review.review_candidate(chat_id, candidate_id, action)
        if not result:
            await _send_message(update, f"Candidate not found: `{candidate_id}`")
            return
        await _send_message(update, f"Candidate `{candidate_id}` -> `{result['status']}`")
        return
    pending = services.store.list_pending_memory_candidates(chat_id, limit=20)
    if not pending:
        await _send_message(update, "No pending memory candidates.")
        return
    lines = ["*Pending Memory Candidates*"]
    for item in pending:
        lines.append(f"- `{item.candidate_id}` [{item.kind}] {item.payload} ({item.reason})")
    await _send_message(update, "\n".join(lines))


async def cmd_followups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    del context
    chat_id = update.effective_chat.id
    services = get_services()
    due = services.store.list_due_followups(chat_id, now_utc=services.clock.now_utc(), limit=10)
    if not due:
        await _send_message(update, "No due follow-ups.")
        return
    lines = ["*Due Follow-ups*"]
    for item in due:
        suffix = f" due `{item['due_at_utc']}`" if item.get("due_at_utc") else ""
        lines.append(f"- `{item['loop_id']}` [{item['priority']}] {item['title']}{suffix}")
    await _send_message(update, "\n".join(lines))


async def cmd_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    chat_id = update.effective_chat.id
    services = get_services()
    if not context.args:
        await _send_message(update, "Usage: `/snooze <loop_id_or_title> [minutes]`")
        return
    minutes = 60
    target_parts = list(context.args)
    if target_parts and target_parts[-1].isdigit():
        try:
            minutes = int(target_parts[-1])
            target_parts = target_parts[:-1]
        except ValueError:
            await _send_message(update, "Minutes must be an integer.")
            return
    target = " ".join(target_parts).strip()
    if not target:
        await _send_message(update, "Usage: `/snooze <loop_id_or_title> [minutes]`")
        return
    result = services.store.snooze_open_loop(chat_id, target, minutes)
    if not result:
        await _send_message(update, f"No open loop found for `{target}`.")
        return
    await _send_message(update, f"Snoozed `{result['title']}` until `{result['snoozed_until_utc']}`.")


async def cmd_close_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    del context
    chat_id = update.effective_chat.id
    services = get_services()
    resolved = services.timezone_resolver.resolve_now(chat_id)
    if not services.store.close_day(chat_id, resolved.local_date):
        await _send_message(update, f"No open day found for `{resolved.local_date}`.")
        return
    snapshot = services.store.get_day_snapshot(chat_id, resolved.local_date)
    if snapshot:
        path = services.projection.render_private_day_log(snapshot.day_id)
        await _send_message(update, f"Closed `{resolved.local_date}` and rendered private log to `{path}`.")
    else:
        await _send_message(update, f"Closed `{resolved.local_date}`.")


def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    get_services()

    # Start background scheduler for cron-like jobs
    start_scheduler()

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("travel", cmd_travel))
    app.add_handler(CommandHandler("review", cmd_review))
    app.add_handler(CommandHandler("followups", cmd_followups))
    app.add_handler(CommandHandler("snooze", cmd_snooze))
    app.add_handler(CommandHandler("close_day", cmd_close_day))
    app.add_handler(CommandHandler("context", cmd_context))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(CommandHandler("onboard", cmd_onboard))
    app.add_handler(CommandHandler("persona", cmd_persona))
    app.add_handler(CommandHandler("resetpersona", cmd_resetpersona))
    app.add_handler(CommandHandler("policy", cmd_policy))
    app.add_handler(CommandHandler("resetpolicy", cmd_resetpolicy))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (Anthropic SDK mode)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
