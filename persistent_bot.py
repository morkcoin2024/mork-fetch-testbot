#!/usr/bin/env python3
"""
Persistent polling bot that stays alive and logs everything
"""

import logging
import os
import signal
import sys
import time

from telegram.error import NetworkError, TimedOut
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Setup logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("persistent_bot.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID", 0))

# Global flag to keep bot running
running = True


def signal_handler(sig, frame):
    global running
    logger.info(f"Received signal {sig}, shutting down...")
    running = False


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


async def ping_handler(update, context):
    """Handle ping commands"""
    user = update.effective_user
    logger.info(f"🏓 PING from {user.username} ({user.id})")

    try:
        response = f"🏓 **PONG!**\n\nBot is working!\nTime: {time.strftime('%H:%M:%S')}\nAdmin: {'Yes' if user.id == ADMIN_ID else 'No'}"
        await update.message.reply_text(response, parse_mode="Markdown")
        logger.info("✅ PONG sent successfully")
    except Exception as e:
        logger.error(f"❌ Failed to send PONG: {e}")


async def status_handler(update, context):
    """Handle status commands"""
    user = update.effective_user
    logger.info(f"📊 STATUS from {user.username} ({user.id})")

    try:
        status_msg = f"""📊 **Bot Status**

Running: Yes ✅
Mode: Persistent Polling
Admin ID: {ADMIN_ID}
Your ID: {user.id}
Admin Access: {"Yes" if user.id == ADMIN_ID else "No"}
Time: {time.strftime("%Y-%m-%d %H:%M:%S")}"""

        await update.message.reply_text(status_msg, parse_mode="Markdown")
        logger.info("✅ Status sent successfully")
    except Exception as e:
        logger.error(f"❌ Failed to send status: {e}")


async def message_handler(update, context):
    """Handle all messages for logging"""
    user = update.effective_user
    text = update.message.text if update.message else "[no text]"
    logger.info(f"💬 Message: {user.username} ({user.id}) -> {text}")


def main():
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found")
        sys.exit(1)

    if not ADMIN_ID:
        logger.error("❌ ASSISTANT_ADMIN_TELEGRAM_ID not found")
        sys.exit(1)

    logger.info(f"🚀 Starting persistent bot for admin {ADMIN_ID}")
    logger.info(f"🤖 Token: {TOKEN[:20]}...{TOKEN[-10:]}")

    # Create application
    application = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("ping", ping_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(MessageHandler(filters.TEXT, message_handler))

    logger.info("🔄 Starting polling...")

    try:
        # Run polling with restart on failure
        while running:
            try:
                logger.info("🟢 Starting polling loop")
                application.run_polling(
                    drop_pending_updates=True,
                    allowed_updates=["message"],
                    timeout=20,
                    poll_interval=1.0,
                    close_loop=False,
                )
            except (NetworkError, TimedOut) as e:
                logger.warning(f"⚠️ Network error, retrying in 5s: {e}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                time.sleep(10)
                if not running:
                    break

    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    finally:
        logger.info("🔴 Bot shutdown complete")


if __name__ == "__main__":
    main()
