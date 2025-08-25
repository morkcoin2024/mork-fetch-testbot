"""
Mork F.E.T.C.H Bot - Main Application Entry Point
PTB v20.7 integration with intelligent fallback
"""

import logging
import os

from robust_logging import setup_robust_logging

# Initialize robust logging with file rotation and ring buffer
setup_robust_logging()
logging.info("Boot: robust logging with ring buffer initialized")

# Admin configuration and command imports
from config import ASSISTANT_ADMIN_TELEGRAM_ID

# Try streamlined PTB v20.7 implementation
try:
    from telegram import Bot, constants
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

    from alerts.admin_router import admin_router
    from alerts.telegram import (
        cmd_logs_stream,
        cmd_logs_tail,
        cmd_logs_watch,
        cmd_mode,
        cmd_ping,
        cmd_pumpfun_probe,
        cmd_pumpfun_status,
        cmd_scan_status,
        cmd_scan_test,
        cmd_status,
        cmd_whoami,
        unknown,
    )

    TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

    logging.info("Starting PTB v20.7 streamlined implementation...")

    # Kill any webhook so polling works
    import asyncio

    async def cleanup_webhook():
        bot = Bot(TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)

    asyncio.run(cleanup_webhook())

    app = ApplicationBuilder().token(TOKEN).build()

    # High-priority admin router for /a_* commands (group -100)
    app.add_handler(MessageHandler(filters.ALL, admin_router), group=-100)

    # Basic commands (group 0)
    app.add_handler(CommandHandler("whoami", cmd_whoami), group=0)
    app.add_handler(CommandHandler("ping", cmd_ping), group=0)

    # Admin monitoring commands
    app.add_handler(CommandHandler("status", cmd_status), group=0)
    app.add_handler(CommandHandler("logs_tail", cmd_logs_tail), group=0)
    app.add_handler(CommandHandler("logs_stream", cmd_logs_stream), group=0)
    app.add_handler(CommandHandler("logs_watch", cmd_logs_watch), group=0)
    app.add_handler(CommandHandler("mode", cmd_mode), group=0)
    app.add_handler(CommandHandler("pumpfun_status", cmd_pumpfun_status), group=0)
    app.add_handler(CommandHandler("pumpfun_probe", cmd_pumpfun_probe), group=0)
    app.add_handler(CommandHandler("scan_status", cmd_scan_status), group=0)
    app.add_handler(CommandHandler("scan_test", cmd_scan_test), group=0)

    # Admin-only aliases (avoid collisions with legacy commands)
    app.add_handler(CommandHandler("a_status", cmd_status), group=0)
    app.add_handler(CommandHandler("a_logs_tail", cmd_logs_tail), group=0)
    app.add_handler(CommandHandler("a_logs_stream", cmd_logs_stream), group=0)
    app.add_handler(CommandHandler("a_logs_watch", cmd_logs_watch), group=0)
    app.add_handler(CommandHandler("a_mode", cmd_mode), group=0)
    app.add_handler(CommandHandler("a_pumpfun_status", cmd_pumpfun_status), group=0)
    app.add_handler(CommandHandler("a_pumpfun_probe", cmd_pumpfun_probe), group=0)
    app.add_handler(CommandHandler("a_scan_status", cmd_scan_status), group=0)
    app.add_handler(CommandHandler("a_scan_test", cmd_scan_test), group=0)
    app.add_handler(CommandHandler("a_ping", cmd_ping), group=0)
    app.add_handler(CommandHandler("a_whoami", cmd_whoami), group=0)

    # Catch-all LAST (very low priority)
    app.add_handler(MessageHandler(filters.COMMAND, unknown), group=999)

    logging.info(
        "PTB polling boot OK. Handlers: whoami, ping, status, logs_tail, logs_stream, logs_watch, mode(g0), unknown(g999)"
    )

    # Add comprehensive logging to track all bot activity
    logging.info("[MAIN] Starting PTB polling with admin router on group -100")
    logging.info(f"[MAIN] Admin ID configured: {ASSISTANT_ADMIN_TELEGRAM_ID}")

    if __name__ == "__main__":
        app.run_polling(allowed_updates=constants.UpdateType.ALL, drop_pending_updates=True)

except ImportError as e:
    logging.info(f"PTB streamlined mode not available ({e}) - using Flask fallback")

    # Add comprehensive bot logging configuration
    bot_logger = logging.getLogger("telegram")
    bot_logger.setLevel(logging.DEBUG)

    # Fallback to Flask application
    from app import app

    # Export for gunicorn WSGI compatibility
    application = app

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000)
