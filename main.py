"""
Mork F.E.T.C.H Bot - Main Application Entry Point
Enhanced PTB v20+ integration with robust fallback handling
"""

import logging
import os

logging.basicConfig(level=logging.INFO)

# Try enhanced PTB v20+ integration first
try:
    import telegram
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from alerts.telegram import cmd_whoami, cmd_ping, unknown, cmd_debug_handlers

    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if TOKEN:
        logging.info("Starting enhanced PTB v20+ bot with webhook cleanup...")
        
        # Ensure polling (and kill any old webhook)
        from telegram import Bot
        Bot(TOKEN).delete_webhook(drop_pending_updates=True)

        application = ApplicationBuilder().token(TOKEN).build()

        # 1) SPECIFIC commands FIRST in group 0
        application.add_handler(CommandHandler("whoami", cmd_whoami), group=0)
        application.add_handler(CommandHandler("ping", cmd_ping), group=0)
        application.add_handler(CommandHandler("debug_handlers", cmd_debug_handlers), group=0)

        # 2) Catch-all UNKNOWN LAST in a very low priority group
        application.add_handler(MessageHandler(filters.COMMAND, unknown), group=999)

        logging.info("Registered handlers: whoami(g0), ping(g0), debug_handlers(g0), unknown(g999)")

        if __name__ == '__main__':
            application.run_polling(drop_pending_updates=True)
    else:
        raise ImportError("No TELEGRAM_BOT_TOKEN found")

except ImportError as e:
    logging.info(f"PTB integration not available ({e}) - running Flask app")
    
    # Fallback to Flask application
    from app import app
    
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)