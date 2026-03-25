"""Shared Telegram message sending for the BeStupid bot."""
import logging
import requests
from config import TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID

logger = logging.getLogger(__name__)


def send_telegram_message(
    text: str,
    chat_id: int | None = None,
    parse_mode: str = "Markdown",
    reply_markup: dict | None = None,
) -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    target = chat_id or OWNER_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target:
        logger.warning("Cannot send: missing TELEGRAM_BOT_TOKEN or chat_id")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": target, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        import json
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error("Telegram send failed: %s %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as e:
        logger.error("Telegram send error: %s", e)
        return False
