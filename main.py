"""
Mork F.E.T.C.H Bot - Main Application Entry Point
PTB v20.7 integration with intelligent fallback
"""

import os
import logging

logging.basicConfig(level=logging.INFO)

# Try streamlined PTB v20.7 implementation
try:
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from telegram import Bot, constants
    from alerts.telegram import (
        cmd_whoami, cmd_ping, unknown, cmd_status, cmd_logs_tail, 
        cmd_logs_stream, cmd_logs_watch, cmd_mode, capture_logs
    )

    TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

    logging.info("Starting PTB v20.7 streamlined implementation...")

    # Kill any webhook so polling works
    Bot(TOKEN).delete_webhook(drop_pending_updates=True)

    app = ApplicationBuilder().token(TOKEN).build()

    # Set app reference for status command
    import alerts.telegram
    alerts.telegram.current_bot_app = app

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

    # Setup log capture
    class LogCapture(logging.Handler):
        def emit(self, record):
            capture_logs(self.format(record))
    
    log_handler = LogCapture()
    log_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(log_handler)

    logging.info("PTB polling boot OK. Handlers: whoami, ping, status, logs_tail, logs_stream, logs_watch, mode(g0), unknown(g999)")
    
    if __name__ == '__main__':
        app.run_polling(allowed_updates=constants.UpdateType.ALL_TYPES, drop_pending_updates=True)

except ImportError as e:
    logging.info(f"PTB streamlined mode not available ({e}) - using Flask fallback")
    
    # Fallback to Flask application
    from app import app
    
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)