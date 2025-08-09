"""
Mork F.E.T.C.H Bot - Main Entry Point
Production-ready Solana trading bot with safety systems
"""

from app import app

# Optional: Add lightweight assistant command handlers for direct dispatcher integration
# from telegram.ext import CommandHandler
# from alerts.telegram import cmd_whoami, cmd_assistant, cmd_assistant_toggle
# 
# if __name__ == '__main__':
#     # For webhook mode, add handlers like:
#     # dispatcher.add_handler(CommandHandler("whoami", cmd_whoami))
#     # dispatcher.add_handler(CommandHandler("assistant", cmd_assistant))
#     # dispatcher.add_handler(CommandHandler("assistant_toggle", cmd_assistant_toggle))
#     pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)