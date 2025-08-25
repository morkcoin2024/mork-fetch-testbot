#!/usr/bin/env python3
"""
SIMPLE POLLING BOT - Runs as primary process for Replit deployment
This bot runs in the foreground to avoid process termination issues
"""

import os
import sys
import time

import requests

# Environment check
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN environment variable not set")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def log(message):
    """Simple logging"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    print(f"[{timestamp}] {message}")


def send_telegram_message(chat_id, text):
    """Send message to Telegram with error handling"""
    try:
        url = f"{API_URL}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        response = requests.post(url, json=data, timeout=10)

        if response.ok:
            result = response.json().get("result", {})
            message_id = result.get("message_id")
            log(f"✅ Sent message {message_id} to chat {chat_id}")
            return True
        else:
            log(f"❌ Send failed: {response.status_code} - {response.text}")
            # Fallback to plain text
            data = {"chat_id": chat_id, "text": text}
            response = requests.post(url, json=data, timeout=10)
            return response.ok

    except Exception as e:
        log(f"❌ Send error: {e}")
        return False


def process_command(message):
    """Process individual Telegram message"""
    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")
    user_info = message.get("from", {})
    user_id = user_info.get("id")
    username = user_info.get("username", "Unknown")

    if not text or not chat_id:
        return

    log(f"📨 Message from @{username} ({user_id}): '{text}'")

    # Admin check (you can modify this ID)
    ADMIN_ID = 1653046781
    is_admin = user_id == ADMIN_ID

    # Command processing
    if text.startswith("/ping"):
        response = (
            "🤖 **Mork F.E.T.C.H Bot**\n✅ Simple polling mode active\n🔥 Bot responding perfectly!"
        )
        send_telegram_message(chat_id, response)

    elif text.startswith("/status"):
        uptime = time.strftime("%H:%M:%S UTC", time.gmtime())
        response = f"✅ **Bot Status: OPERATIONAL**\n⚡ Mode: Simple Polling\n🕐 Current Time: {uptime}\n\n{'🔐 Admin access' if is_admin else '👤 User access'}"
        send_telegram_message(chat_id, response)

    elif text.startswith("/help"):
        response = "🐕 **Mork F.E.T.C.H Bot Help**\n\n📋 **Available Commands:**\n• `/ping` - Test connection\n• `/status` - System status\n• `/help` - Show help\n\n🔥 Ready for trading!"
        send_telegram_message(chat_id, response)

    elif text.startswith("/test"):
        if is_admin:
            response = (
                "🧪 **Test Mode**\nAll systems operational!\nBot processing commands correctly."
            )
            send_telegram_message(chat_id, response)
        else:
            send_telegram_message(chat_id, "Access denied - admin only command")

    elif text.startswith("/"):
        cmd = text.split()[0]
        response = f"Command `{cmd}` not recognized.\nUse /help for available commands."
        send_telegram_message(chat_id, response)


def clear_pending_updates():
    """Clear any pending Telegram updates"""
    try:
        log("Clearing pending updates...")
        response = requests.get(f"{API_URL}/getUpdates", timeout=10)
        if response.ok:
            updates = response.json().get("result", [])
            if updates:
                last_update_id = max(update.get("update_id", 0) for update in updates)
                # Mark as processed
                requests.get(
                    f"{API_URL}/getUpdates", params={"offset": last_update_id + 1}, timeout=10
                )
                log(f"Cleared {len(updates)} pending updates")
            else:
                log("No pending updates")
        else:
            log(f"Failed to get updates: {response.status_code}")
    except Exception as e:
        log(f"Error clearing updates: {e}")


def polling_loop():
    """Main polling loop"""
    log("🚀 Starting Telegram polling loop")

    # Delete webhook first
    try:
        requests.post(f"{API_URL}/deleteWebhook", timeout=10)
        log("Webhook deleted - polling mode active")
    except Exception as e:
        log(f"Webhook delete error: {e}")

    # Clear pending
    clear_pending_updates()

    offset = 0
    consecutive_errors = 0

    while True:
        try:
            # Long polling request
            params = {
                "offset": offset,
                "limit": 10,
                "timeout": 25,  # 25 second timeout for long polling
            }

            log(f"Polling for updates (offset: {offset})...")
            response = requests.get(f"{API_URL}/getUpdates", params=params, timeout=30)

            if not response.ok:
                consecutive_errors += 1
                log(f"❌ Poll failed: {response.status_code} (error #{consecutive_errors})")
                if consecutive_errors > 5:
                    log("Too many consecutive errors - waiting longer")
                    time.sleep(30)
                else:
                    time.sleep(5)
                continue

            # Reset error counter
            consecutive_errors = 0

            data = response.json()
            if not data.get("ok"):
                log(f"API error response: {data}")
                time.sleep(5)
                continue

            updates = data.get("result", [])

            if updates:
                log(f"📥 Processing {len(updates)} updates")

                for update in updates:
                    update_id = update.get("update_id", 0)
                    offset = max(offset, update_id + 1)

                    message = update.get("message")
                    if message:
                        process_command(message)

                    # Also handle edited messages
                    edited_message = update.get("edited_message")
                    if edited_message:
                        process_command(edited_message)
            else:
                log("No new updates")

        except requests.exceptions.Timeout:
            log("Poll timeout - continuing...")
        except KeyboardInterrupt:
            log("Shutting down polling...")
            break
        except Exception as e:
            consecutive_errors += 1
            log(f"❌ Unexpected error: {e} (error #{consecutive_errors})")
            time.sleep(10 if consecutive_errors < 3 else 30)


def main():
    """Main entry point"""
    print("=" * 50)
    print("🤖 Mork F.E.T.C.H Bot - Simple Polling Mode")
    print("=" * 50)

    # Verify bot token
    try:
        response = requests.get(f"{API_URL}/getMe", timeout=10)
        if response.ok:
            bot_info = response.json().get("result", {})
            bot_name = bot_info.get("first_name", "Unknown")
            log(f"✅ Bot verified: {bot_name}")
        else:
            log(f"❌ Bot verification failed: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        log(f"❌ Bot verification error: {e}")
        sys.exit(1)

    # Start polling
    try:
        polling_loop()
    except KeyboardInterrupt:
        log("Bot stopped by user")
    except Exception as e:
        log(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
