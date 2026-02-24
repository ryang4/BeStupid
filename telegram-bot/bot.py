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


def _run_context_briefing() -> str:
    """Run context_briefing.py --full and return output."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "context_briefing.py"), "--full"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        return result.stdout.strip() if result.stdout.strip() else "No context available."
    except Exception as e:
        logger.error(f"Context briefing failed: {e}")
        return f"Context briefing failed: {e}"


def _run_memory_extract(text: str):
    """Run memory.py extract on text (fire-and-forget)."""
    try:
        subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "memory.py"), "extract", text],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT),
        )
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")


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
        state = _get_conversation(chat_id)
        user_text = (update.message.text or "").strip()
        monitor = get_heartbeat_monitor()
        if monitor:
            monitor.record_activity()

        if chat_id in _onboarding_sessions:
            onboarding_reply, _ = _apply_onboarding_answer(chat_id, user_text)
            await _send_message(update, onboarding_reply)
            return

        # On new session (empty history), inject context briefing
        if not state.history:
            briefing = await asyncio.to_thread(_run_context_briefing)
            context_msg = f"[AUTO-CONTEXT] New session. Here's my current context:\n\n{briefing}"
            persona_hint = ""
            if not load_persona_profile(chat_id):
                persona_hint = "\nRun /onboard to configure your assistant's personality."
            # Run tool loop with context briefing first (no save needed, next call saves)
            await asyncio.to_thread(lambda: None)  # yield
            state.history.append({"role": "user", "content": context_msg})
            state.history.append({
                "role": "assistant",
                "content": "Got it — I've reviewed your current context. How can I help?" + persona_hint,
            })

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

        # Fire-and-forget: memory extraction + git backup
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _run_memory_extract, user_text)
        loop.run_in_executor(None, _run_auto_backup)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    await update.message.reply_text(
        "BeStupid assistant (Anthropic SDK)\n\n"
        "Just chat naturally:\n"
        "- 'Read today's log'\n"
        "- 'Log weight 241'\n"
        "- 'Find files mentioning protein'\n"
        "- 'Remember that John is my accountant'\n\n"
        "/context - Show current briefing\n"
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
    briefing = await asyncio.to_thread(_run_context_briefing)
    await _send_message(update, briefing)


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


def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

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
