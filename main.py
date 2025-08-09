"""
Mork F.E.T.C.H Bot - Main Entry Point
Production-ready Solana trading bot with safety systems
"""

from app import app

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)