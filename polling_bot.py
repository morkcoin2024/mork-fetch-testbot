#!/usr/bin/env python3
"""
Polling-based bot fallback for when webhooks fail
Runs alongside Flask app to ensure bot responsiveness
"""

import asyncio
import logging
import os
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID', 0))

async def ping_command(update, context):
    """Handle /ping command"""
    logger.info(f"Ping from {update.effective_user.username}")
    await update.message.reply_text('🏓 Pong! Bot is working in polling mode.')

async def status_command(update, context):
    """Handle /status command"""
    logger.info(f"Status from {update.effective_user.username}")
    await update.message.reply_text('''🤖 Mork F.E.T.C.H Bot Status

Mode: Polling (webhook fallback)
System: Operational
Scanners: Active in Flask app
Admin Commands: Available

Bot is responding via direct polling.''')

async def whoami_command(update, context):
    """Handle /whoami command"""
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
    await update.message.reply_text(f'''Your Telegram Info:
ID: {user.id}
Username: @{user.username or 'unknown'}
Admin: {'Yes' if is_admin else 'No'}''')

def main():
    """Start the polling bot"""
    if not TOKEN:
        logger.error("No Telegram token found")
        return
        
    logger.info("Starting polling bot as webhook fallback...")
    
    # Build application
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("whoami", whoami_command))
    
    # Start polling
    logger.info("Bot polling started")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()