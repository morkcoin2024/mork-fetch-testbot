"""
Mork F.E.T.C.H Bot - Main Application Entry Point
Clean PTB v20+ integration with essential commands
"""

import os
import logging
logging.basicConfig(level=logging.INFO)

# Try PTB v20+ integration first, fallback to Flask app
try:
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from alerts.telegram import cmd_whoami, cmd_ping, unknown

    # Get token from environment
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    if TOKEN:
        # Build application with PTB v20+
        application = ApplicationBuilder().token(TOKEN).build()

        # SPECIFIC commands FIRST (group 0)
        application.add_handler(CommandHandler("whoami", cmd_whoami), group=0)
        application.add_handler(CommandHandler("ping", cmd_ping), group=0)

        # Catch-all LAST (group 1)
        application.add_handler(MessageHandler(filters.COMMAND, unknown), group=1)

        logging.info("Handlers registered: whoami(g0), ping(g0), unknown(g1)")

        # Run the bot
        if __name__ == '__main__':
            application.run_polling(drop_pending_updates=True)
    else:
        print("TELEGRAM_BOT_TOKEN not found - running Flask app only")
        raise ImportError("No token available")
        
except ImportError as e:
    print(f"PTB integration not available ({e}) - running Flask app")
    from app import app
    
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000)