"""
Mork F.E.T.C.H Bot - Main Application Entry Point
PTB v20.7 integration with intelligent fallback
"""

import logging, os, pathlib
from logging.handlers import RotatingFileHandler

# Enhanced logging setup with file rotation
pathlib.Path("logs").mkdir(exist_ok=True)
log_file = "logs/app.log"

root = logging.getLogger()
root.setLevel(logging.INFO)

# Avoid duplicate handlers if main.py reloads
if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
    fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    sh = logging.StreamHandler()  # still see output in Replit console
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh.setFormatter(fmt); sh.setFormatter(fmt)
    root.addHandler(fh); root.addHandler(sh)

logging.info("Boot: logging to %s", log_file)

# Try streamlined PTB v20.7 implementation
try:
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from telegram import Bot, constants
    from alerts.telegram import (
        cmd_whoami, cmd_ping, unknown, cmd_status, cmd_logs_tail, 
        cmd_logs_stream, cmd_logs_watch, cmd_mode
    )

    TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

    logging.info("Starting PTB v20.7 streamlined implementation...")

    # Kill any webhook so polling works
    Bot(TOKEN).delete_webhook(drop_pending_updates=True)

    app = ApplicationBuilder().token(TOKEN).build()

    # Specific commands FIRST (group 0)
    app.add_handler(CommandHandler("whoami", cmd_whoami), group=0)
    app.add_handler(CommandHandler("ping", cmd_ping), group=0)
    app.add_handler(CommandHandler("status", cmd_status), group=0)
    app.add_handler(CommandHandler("logs_tail", cmd_logs_tail), group=0)
    app.add_handler(CommandHandler("logs_stream", cmd_logs_stream), group=0)
    app.add_handler(CommandHandler("logs_watch", cmd_logs_watch), group=0)
    app.add_handler(CommandHandler("mode", cmd_mode), group=0)

    # Catch-all LAST (very low priority)
    app.add_handler(MessageHandler(filters.COMMAND, unknown), group=999)

    logging.info("PTB polling boot OK. Handlers: whoami, ping, status, logs_tail, logs_stream, logs_watch, mode(g0), unknown(g999)")
    
    if __name__ == '__main__':
        app.run_polling(allowed_updates=constants.UpdateType.ALL_TYPES, drop_pending_updates=True)

except ImportError as e:
    logging.info(f"PTB streamlined mode not available ({e}) - using Flask fallback")
    
    # Fallback to Flask application
    from app import app
    
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)