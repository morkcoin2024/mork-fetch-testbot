"""
Mork F.E.T.C.H Bot - Main Entry Point
Production-ready Solana trading bot with safety systems
"""

import logging
logging.basicConfig(level=logging.INFO)

from app import app

def log_update(update, context):
    """Log all incoming updates for debugging"""
    try:
        logging.info("UPDATE: %s", update.to_dict())
    except Exception:
        logging.info("UPDATE received (non-dict)")

# Lightweight assistant command handlers for direct application integration
# Uncomment these lines to wire handlers directly:
#
# from telegram.ext import CommandHandler
# from alerts.telegram import cmd_whoami, cmd_assistant, cmd_assistant_toggle
# 
# # Add handlers to application:
# application.add_handler(CommandHandler("whoami", cmd_whoami))
# application.add_handler(CommandHandler("assistant", cmd_assistant))
# application.add_handler(CommandHandler("assistant_toggle", cmd_assistant_toggle))

# Update logging for debugging (choose version based on PTB):
# PTB v13:
# from telegram.ext import MessageHandler, Filters
# dispatcher.add_handler(MessageHandler(Filters.all, log_update))

# PTB v20:
# from telegram.ext import MessageHandler, filters
# application.add_handler(MessageHandler(filters.ALL, log_update))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)