#!/usr/bin/env python3
"""
Helper script to get your Telegram chat ID.

Usage:
1. Create a bot with @BotFather and get your token
2. Set TELEGRAM_BOT_TOKEN in .env (or pass as argument)
3. Send a message to your bot on Telegram (anything like "hello")
4. Run this script: python telegram-bot/get_chat_id.py

It will print your chat ID which you can add to .env
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent / ".env")

def get_chat_id(token=None):
    """Get chat ID from bot updates."""
    if not token:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not token:
        print("❌ Error: No TELEGRAM_BOT_TOKEN found.")
        print("\nUsage:")
        print("  1. Add TELEGRAM_BOT_TOKEN to telegram-bot/.env")
        print("  2. Or run: python get_chat_id.py YOUR_BOT_TOKEN")
        sys.exit(1)

    print("🔍 Fetching updates from Telegram...")
    print(f"Token: {token[:10]}...{token[-5:]}\n")

    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        response = requests.get(url, timeout=10)
        data = response.json()

        if not data.get("ok"):
            print(f"❌ Telegram API error: {data.get('description', 'Unknown error')}")
            print("\nMake sure your bot token is correct.")
            sys.exit(1)

        updates = data.get("result", [])

        if not updates:
            print("⚠️  No messages found yet.")
            print("\n📱 To get your chat ID:")
            print("1. Open Telegram")
            print("2. Find your bot (search for the username you gave it)")
            print("3. Send it ANY message (like 'hello')")
            print("4. Run this script again\n")
            sys.exit(0)

        # Get the most recent chat ID
        chat_ids = set()
        for update in updates:
            message = update.get("message", {})
            chat = message.get("chat", {})
            chat_id = chat.get("id")
            username = chat.get("username", "Unknown")
            first_name = chat.get("first_name", "")

            if chat_id:
                chat_ids.add((chat_id, username, first_name))

        if not chat_ids:
            print("❌ No chat IDs found in updates.")
            sys.exit(1)

        print("✅ Found chat ID(s):\n")

        for chat_id, username, first_name in chat_ids:
            print(f"   Chat ID: {chat_id}")
            if username:
                print(f"   Username: @{username}")
            if first_name:
                print(f"   Name: {first_name}")
            print()

        if len(chat_ids) == 1:
            chat_id = list(chat_ids)[0][0]
            print(f"✅ Your chat ID is: {chat_id}\n")
            print("Add this to telegram-bot/.env:")
            print(f"OWNER_CHAT_ID={chat_id}\n")
        else:
            print("⚠️  Multiple chat IDs found. Use the one that's yours.")
            print("\nAdd to telegram-bot/.env:")
            print(f"OWNER_CHAT_ID={list(chat_ids)[0][0]}\n")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    token = sys.argv[1] if len(sys.argv) > 1 else None
    get_chat_id(token)
