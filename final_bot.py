#!/usr/bin/env python3
"""
Final bot implementation with bulletproof error handling
"""

import logging
import os
import sys
import time

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("final_bot.log", mode="w")],
)
logger = logging.getLogger(__name__)

# Disable httpx debug logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID", 0))


async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command"""
    try:
        user = update.effective_user
        logger.info(f"PING from {user.username} ({user.id})")

        response_text = f"🏓 PONG! Bot working at {time.strftime('%H:%M:%S')}"
        await update.message.reply_text(response_text)
        logger.info("PONG sent successfully")

    except Exception as e:
        logger.error(f"Error in ping handler: {e}")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    try:
        user = update.effective_user
        logger.info(f"STATUS from {user.username} ({user.id})")

        status_text = f"""Bot Status Report:
Running: Yes
Mode: Polling
Admin ID: {ADMIN_ID}
Your ID: {user.id}
Admin Access: {"Yes" if user.id == ADMIN_ID else "No"}
Time: {time.strftime("%Y-%m-%d %H:%M:%S")}"""

        await update.message.reply_text(status_text)
        logger.info("Status sent successfully")

    except Exception as e:
        logger.error(f"Error in status handler: {e}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all other messages"""
    try:
        user = update.effective_user
        text = update.message.text if update.message.text else "[non-text]"
        logger.info(f"Message: {user.username} ({user.id}) -> {text}")

    except Exception as e:
        logger.error(f"Error in message handler: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error occurred: {context.error}")
    if update and hasattr(update, "effective_user"):
        logger.error(f"Error for user: {update.effective_user.id}")


def main():
    """Main bot function with robust error handling"""

    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found")
        sys.exit(1)

    if not ADMIN_ID:
        logger.error("ASSISTANT_ADMIN_TELEGRAM_ID not found")
        sys.exit(1)

    logger.info(f"Starting final bot for admin {ADMIN_ID}")

    # Create application
    try:
        app = ApplicationBuilder().token(TOKEN).build()

        # Add handlers
        app.add_handler(CommandHandler("ping", ping_handler))
        app.add_handler(CommandHandler("status", status_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        app.add_error_handler(error_handler)

        logger.info("Handlers registered, starting polling...")

        # Start polling with robust configuration
        app.run_polling(
            timeout=30,
            poll_interval=2.0,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
