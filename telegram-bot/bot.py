#!/usr/bin/env python3
"""
BeStupid Telegram Bot - Personal productivity assistant powered by Claude Code.
Uses Claude Code CLI (claude -p --continue) with your Claude Max subscription.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment
load_dotenv(Path(__file__).parent / ".env")

# Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))
PROJECT_ROOT = Path(__file__).parent.parent

# Keep system prompt short to reduce latency
SYSTEM_PROMPT = """You are Ryan's personal AI assistant via Telegram. Be concise.

You have full Claude Code tools (read/write files, bash, etc). Use them proactively.

Key paths in this repo:
- Daily logs: content/logs/YYYY-MM-DD.md
- Metrics: data/daily_metrics.json
- Scripts: scripts/*.py"""

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def call_claude(message: str, continue_conversation: bool = True) -> str:
    """Call Claude Code CLI and return the response."""
    cmd = ["claude", "-p", "--model", "sonnet"]

    if continue_conversation:
        cmd.append("--continue")

    # Only add system prompt on fresh conversations
    if not continue_conversation:
        cmd.extend(["--system-prompt", SYSTEM_PROMPT])

    cmd.append(message)

    logger.info(f"Calling Claude: {message[:50]}...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=90,
        )

        if result.returncode != 0:
            logger.error(f"Claude error: {result.stderr}")
            return f"Error: {result.stderr[:200]}"

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
    """Start fresh conversation."""
    response = call_claude("Hi! Fresh conversation.", continue_conversation=False)
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
