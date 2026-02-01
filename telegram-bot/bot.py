#!/usr/bin/env python3
"""
BeStupid Telegram Bot - Personal productivity assistant powered by Anthropic SDK.
Thin Telegram layer; all Claude logic lives in claude_client.py.
"""

import os
import sys
import logging
import asyncio
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from claude_client import ConversationState, run_tool_loop

load_dotenv(Path(__file__).parent / ".env")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", 0))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Per-chat state
_conversations: dict[int, ConversationState] = defaultdict(ConversationState)
_chat_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


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
        state = _conversations[chat_id]

        async def typing_callback():
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        await typing_callback()

        try:
            response = await run_tool_loop(
                state,
                update.message.text,
                typing_callback=typing_callback,
            )
        except Exception as e:
            logger.error(f"Claude error: {e}")
            error_name = type(e).__name__
            response = f"Error ({error_name}): {e}"

        await _send_message(update, response)


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
        "/clear - Fresh conversation\n"
        "/cost - Token usage"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    chat_id = update.effective_chat.id
    _conversations[chat_id].clear()
    await update.message.reply_text("Conversation cleared.")


async def cmd_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    chat_id = update.effective_chat.id
    state = _conversations[chat_id]
    # Sonnet pricing: $3/M input, $15/M output
    input_cost = state.total_input_tokens * 3.0 / 1_000_000
    output_cost = state.total_output_tokens * 15.0 / 1_000_000
    total = input_cost + output_cost
    await update.message.reply_text(
        f"Input tokens: {state.total_input_tokens:,}\n"
        f"Output tokens: {state.total_output_tokens:,}\n"
        f"Estimated cost: ${total:.4f}"
    )


def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("cost", cmd_cost))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting (Anthropic SDK mode)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
