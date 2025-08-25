#!/usr/bin/env python3
import logging
import os
import time

from telegram.ext import ApplicationBuilder, CommandHandler

# Simple logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID"))


async def ping(update, context):
    logger.info(f"PING from {update.effective_user.id}")
    await update.message.reply_text(f"PONG! Bot working at {time.strftime('%H:%M:%S')}")
    logger.info("PONG sent")


async def status(update, context):
    logger.info(f"STATUS from {update.effective_user.id}")
    await update.message.reply_text(
        f"Bot Status: Running\nAdmin: {ADMIN_ID}\nYou: {update.effective_user.id}"
    )
    logger.info("Status sent")


def main():
    logger.info(f"Starting ultra-simple bot for admin {ADMIN_ID}")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status))
    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
