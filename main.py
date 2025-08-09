"""
Mork F.E.T.C.H Bot - Main Entry Point
Production-ready Solana trading bot with safety systems
"""

from app import app

# Lightweight assistant command handlers for direct dispatcher integration
# Uncomment these lines to wire handlers directly to dispatcher:
#
# from telegram.ext import CommandHandler
# from alerts.telegram import cmd_whoami, cmd_assistant, cmd_assistant_toggle
# 
# # Add handlers to dispatcher:
# dispatcher.add_handler(CommandHandler("whoami", cmd_whoami))
# dispatcher.add_handler(CommandHandler("assistant", cmd_assistant))
# dispatcher.add_handler(CommandHandler("assistant_toggle", cmd_assistant_toggle))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)