"""
Mork F.E.T.C.H Bot - Main Application Entry Point
Modern PTB v20+ integration with assistant system
"""

import os
import logging
logging.basicConfig(level=logging.INFO)

# Try PTB v20+ integration first, fallback to Flask app
try:
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from alerts.telegram import cmd_whoami, cmd_assistant, cmd_assistant_model, cmd_assistant_toggle, unknown

    # Get token from environment
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    if TOKEN:
        # Build application with PTB v20+
        application = ApplicationBuilder().token(TOKEN).build()

        # IMPORTANT: specific command handlers FIRST (group 0)
        application.add_handler(CommandHandler("whoami", cmd_whoami), group=0)
        application.add_handler(CommandHandler("assistant_model", cmd_assistant_model), group=0)
        application.add_handler(CommandHandler("assistant_toggle", cmd_assistant_toggle), group=0)
        application.add_handler(CommandHandler("assistant", cmd_assistant), group=0)

        # Catch-all for any other /commands LAST (group 1)
        application.add_handler(MessageHandler(filters.COMMAND, unknown), group=1)

        print("Mork F.E.T.C.H Bot starting with PTB v20+ integration...")
        print("Assistant commands available: /assistant, /assistant_model, /assistant_toggle, /whoami")
        
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