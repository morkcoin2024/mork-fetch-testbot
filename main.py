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
    from alerts.telegram import cmd_whoami, cmd_ping, unknown

    TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

    logging.info("Starting PTB v20.7 streamlined implementation...")

    # Kill any webhook so polling works
    Bot(TOKEN).delete_webhook(drop_pending_updates=True)

    app = ApplicationBuilder().token(TOKEN).build()

    # Specific commands FIRST (group 0)
    app.add_handler(CommandHandler("whoami", cmd_whoami), group=0)
    app.add_handler(CommandHandler("ping", cmd_ping), group=0)

    # Catch-all LAST (very low priority)
    app.add_handler(MessageHandler(filters.COMMAND, unknown), group=999)

    logging.info("PTB polling boot OK. Handlers: whoami(g0), ping(g0), unknown(g999)")
    
    if __name__ == '__main__':
        app.run_polling(allowed_updates=constants.UpdateType.ALL_TYPES, drop_pending_updates=True)

except ImportError as e:
    logging.info(f"PTB streamlined mode not available ({e}) - using Flask fallback")
    
    # Fallback to Flask application
    from app import app
    
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)