#!/usr/bin/env python3
"""
BeStupid Telegram Bot - Personal productivity assistant powered by Claude Code.
Uses Claude Code CLI with a dedicated session ID to maintain context.
"""

import os
import sys
import logging
import asyncio
import subprocess
import uuid
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment
load_dotenv(Path(__file__).parent / ".env")

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", Path(__file__).parent.parent))
SESSION_DIR = Path(os.environ.get("PROJECT_ROOT", Path(__file__).parent.parent)) / "telegram-bot"
SESSION_FILE = SESSION_DIR / ".session_id"
SKIP_PERMISSIONS = os.environ.get("SKIP_PERMISSIONS", "false").lower() == "true"


def get_or_create_session_id() -> str:
    """Get existing session ID or create a new one."""
    if SESSION_FILE.exists():
        return SESSION_FILE.read_text().strip()
    new_id = str(uuid.uuid4())
    SESSION_FILE.write_text(new_id)
    return new_id


def reset_session() -> str:
    """Create a new session ID (for /clear command)."""
    new_id = str(uuid.uuid4())
    SESSION_FILE.write_text(new_id)
    return new_id

# System prompt - kept concise for speed
SYSTEM_PROMPT = """You are Ryan's executive assistant via Telegram. Be concise and direct.

MEMORY SYSTEM - Use `python scripts/memory.py` to maintain knowledge:
- people add/get/update/list/delete "Name" --context/--role/--field/--value
- projects add/get/update/list "name" --status/--description
- decisions add/list/revoke "topic" --choice/--rationale
- commitments add/list/complete/cancel "what" --deadline/--who
- search "query"

When people/decisions/commitments come up, update memory. Check memory for context when relevant.

Key paths: memory/*.json, content/logs/YYYY-MM-DD.md, scripts/*.py"""

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _run_claude(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run Claude CLI with no timeout."""
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))


def call_claude(message: str, force_new_session: bool = False) -> str:
    """Call Claude Code CLI and return the response.

    Strategy: always try --resume first. If the session doesn't exist yet,
    Claude returns an error and we retry with --session-id to create it.
    """
    if force_new_session:
        session_id = reset_session()
    else:
        session_id = get_or_create_session_id()

    base_cmd = ["claude", "-p", "--model", "sonnet"]
    if SKIP_PERMISSIONS:
        base_cmd.append("--dangerously-skip-permissions")

    # Try --resume first (works if session exists)
    cmd = base_cmd + ["--resume", session_id, "--system-prompt", SYSTEM_PROMPT, message]
    logger.info(f"Calling Claude (resume): {message[:50]}...")

    try:
        result = _run_claude(cmd)

        if result.returncode == 0:
            return result.stdout.strip()

        # Session doesn't exist — create it with --session-id
        if "No conversation found" in result.stderr or "already in use" in result.stderr:
            logger.info("Session not found or stale, creating new session")
            session_id = reset_session()
            cmd = base_cmd + ["--session-id", session_id, "--system-prompt", SYSTEM_PROMPT, message]
            result = _run_claude(cmd)
            if result.returncode == 0:
                return result.stdout.strip()

        logger.error(f"Claude error (rc={result.returncode}): stderr={result.stderr[:500]}")
        logger.error(f"Claude stdout: {result.stdout[:500]}")
        return f"Error: {result.stderr[:200] or result.stdout[:200]}"

    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error: {e}"


THINKING_INTERVAL = 30  # seconds between "still thinking" updates


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    if OWNER_CHAT_ID and update.effective_chat.id != OWNER_CHAT_ID:
        await update.message.reply_text("Unauthorized.")
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id
    logger.info(f"Message: {user_text[:50]}...")

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Run Claude in a thread so we can send periodic updates
    loop = asyncio.get_event_loop()
    claude_task = loop.run_in_executor(None, call_claude, user_text)

    elapsed = 0
    while True:
        try:
            response = await asyncio.wait_for(asyncio.shield(claude_task), timeout=THINKING_INTERVAL)
            break  # got a response
        except asyncio.TimeoutError:
            elapsed += THINKING_INTERVAL
            minutes = elapsed // 60
            seconds = elapsed % 60
            if minutes:
                ts = f"{minutes}m {seconds}s"
            else:
                ts = f"{seconds}s"
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            logger.info(f"Still waiting for Claude ({ts})...")

    # Split long messages
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
    else:
        await update.message.reply_text(response)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start fresh conversation with new session ID."""
    if OWNER_CHAT_ID and update.effective_chat.id != OWNER_CHAT_ID:
        await update.message.reply_text("Unauthorized.")
        return
    response = call_claude("Hi! Fresh conversation started.", force_new_session=True)
    await update.message.reply_text(f"Fresh start!\n\n{response}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start."""
    await update.message.reply_text(
        "BeStupid assistant (Claude Code)\n\n"
        "Just chat naturally:\n"
        "- 'Read today's log'\n"
        "- 'Log weight 241'\n"
        "- 'Run brain.py'\n\n"
        "/clear - Fresh conversation"
    )


def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    try:
        subprocess.run(["claude", "--version"], capture_output=True, timeout=30)
    except FileNotFoundError:
        print("Error: claude CLI not found")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        pass  # CLI hangs after printing version, but it exists

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Bot starting - working dir: {PROJECT_ROOT}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
