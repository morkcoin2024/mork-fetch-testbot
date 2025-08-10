"""
Mork F.E.T.C.H Bot - Main Application Entry Point
PTB v20+ integration with fallback support
"""

import os
import logging

logging.basicConfig(level=logging.INFO)

# Try PTB v20+ streamlined integration
try:
    import telegram
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
    from alerts.telegram import cmd_whoami, cmd_ping, cmd_xyzabc, unknown

    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if TOKEN:
        logging.info("Starting PTB v20+ bot with handler diagnostics...")
        
        from telegram import Bot
        Bot(TOKEN).delete_webhook(drop_pending_updates=True)

        application = ApplicationBuilder().token(TOKEN).build()

        # SPECIFIC commands FIRST (group 0)
        application.add_handler(CommandHandler("whoami", cmd_whoami), group=0)
        application.add_handler(CommandHandler("ping", cmd_ping), group=0)
        application.add_handler(CommandHandler("xyzabc", cmd_xyzabc), group=0)

        # Catch-all LAST (very low priority)
        application.add_handler(MessageHandler(filters.COMMAND, unknown), group=999)

        # Dump handler table at startup
        def _dump_handlers(app):
            lines = []
            for grp in sorted(app.handlers.keys()):
                items = []
                for h in app.handlers[grp]:
                    name = type(h).__name__
                    if name == "CommandHandler":
                        cmds = ",".join(sorted(getattr(h, "commands", set())))
                        items.append(f"{name}({cmds})")
                    else:
                        items.append(name)
                lines.append(f"g{grp}: " + " | ".join(items))
            logging.info("HANDLERS:\n%s", "\n".join(lines))

        _dump_handlers(application)

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