#!/usr/bin/env python3
"""
BeStupid Telegram Bot - Personal productivity assistant powered by Claude Code.
Uses Claude Code CLI with a dedicated session ID to maintain context.
"""

import os
import sys
import logging
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
SESSION_FILE = Path(__file__).parent / ".session_id"
SKIP_PERMISSIONS = os.environ.get("SKIP_PERMISSIONS", "false").lower() == "true"

SESSION_CREATED_FILE = Path(__file__).parent / ".session_created"

def get_session_id() -> tuple[str, bool]:
    """Get session ID and whether it's been used before.
    Returns (session_id, is_new_session)."""
    if SESSION_FILE.exists():
        session_id = SESSION_FILE.read_text().strip()
        is_new = not SESSION_CREATED_FILE.exists()
        return session_id, is_new
    # Create new session ID
    new_id = str(uuid.uuid4())
    SESSION_FILE.write_text(new_id)
    # Remove created marker if it exists
    if SESSION_CREATED_FILE.exists():
        SESSION_CREATED_FILE.unlink()
    return new_id, True

def mark_session_created():
    """Mark that the session has been created in Claude."""
    SESSION_CREATED_FILE.write_text("1")

def reset_session() -> str:
    """Create a new session ID (for /clear command)."""
    new_id = str(uuid.uuid4())
    SESSION_FILE.write_text(new_id)
    # Remove created marker so next call uses --session-id
    if SESSION_CREATED_FILE.exists():
        SESSION_CREATED_FILE.unlink()
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


def call_claude(message: str, force_new_session: bool = False) -> str:
    """Call Claude Code CLI and return the response."""
    if force_new_session:
        session_id = reset_session()
        is_new = True
    else:
        session_id, is_new = get_session_id()

    cmd = ["claude", "-p", "--model", "sonnet"]

    # Skip permission prompts in container/sandbox mode
    if SKIP_PERMISSIONS:
        cmd.append("--dangerously-skip-permissions")

    if is_new:
        # First message in this session - create it
        cmd.extend(["--session-id", session_id])
    else:
        # Continuing existing session - resume it
        cmd.extend(["--resume", session_id])

    cmd.extend(["--system-prompt", SYSTEM_PROMPT, message])

    logger.info(f"Calling Claude: {message[:50]}...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=180,
        )

        if result.returncode != 0:
            logger.error(f"Claude error: {result.stderr}")
            return f"Error: {result.stderr[:200]}"

        # Mark session as created for future --resume calls
        mark_session_created()
        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        return "Timed out - try a simpler question."
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error: {e}"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    if OWNER_CHAT_ID and update.effective_chat.id != OWNER_CHAT_ID:
        await update.message.reply_text("Unauthorized.")
        return

    user_text = update.message.text
    logger.info(f"Message: {user_text[:50]}...")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    response = call_claude(user_text)

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
        subprocess.run(["claude", "--version"], capture_output=True, check=True)
    except:
        print("Error: claude CLI not found")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Bot starting - working dir: {PROJECT_ROOT}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
