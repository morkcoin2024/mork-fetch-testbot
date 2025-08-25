#!/usr/bin/env python3
"""
Working bot with Flask app in polling mode
"""

import logging
import os
import time

from telegram.ext import ApplicationBuilder, CommandHandler

# Set polling mode to prevent Flask bot interference
os.environ["POLLING_MODE"] = "ON"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID"))


async def ping(update, context):
    user_id = update.effective_user.id
    logger.info(f"PING from {user_id} ({'ADMIN' if user_id == ADMIN_ID else 'USER'})")

    response = f"🏓 PONG!\nTime: {time.strftime('%H:%M:%S')}\nAdmin: {user_id == ADMIN_ID}"
    await update.message.reply_text(response)
    logger.info("PONG response sent successfully")


async def status(update, context):
    user_id = update.effective_user.id
    logger.info(f"STATUS from {user_id}")

    status_msg = f"""Bot Status:
Running: Yes
Mode: Polling (Flask bot disabled)
Admin ID: {ADMIN_ID}
Your ID: {user_id}
Admin Access: {"Yes" if user_id == ADMIN_ID else "No"}
Time: {time.strftime("%Y-%m-%d %H:%M:%S")}"""

    await update.message.reply_text(status_msg)
    logger.info("Status response sent")


def main():
    logger.info("Starting working bot - Flask mork_bot disabled")
    logger.info(f"Admin ID: {ADMIN_ID}")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status))

    logger.info("Starting polling with Flask protection...")
    app.run_polling(drop_pending_updates=True, timeout=30, poll_interval=2)


if __name__ == "__main__":
    main()
