#!/usr/bin/env python3
"""
Debug polling bot with extensive logging
"""

import asyncio
import logging
import os
import sys
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram.error import NetworkError, TimedOut

# Enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug_bot.log', mode='w')
    ]
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID', 0))

async def handle_ping(update, context):
    """Handle /ping command with extensive logging"""
    user = update.effective_user
    logger.info(f"=== PING RECEIVED ===")
    logger.info(f"User ID: {user.id}")
    logger.info(f"Username: {user.username}")
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Is Admin: {user.id == ADMIN_ID}")
    logger.info(f"Message: {update.message.text}")
    logger.info(f"Update ID: {update.update_id}")
    
    try:
        await update.message.reply_text('🏓 PONG! Debug bot is working!')
        logger.info("PONG response sent successfully")
    except Exception as e:
        logger.error(f"Failed to send PONG: {e}")

async def handle_all(update, context):
    """Log all incoming messages"""
    user = update.effective_user
    text = update.message.text if update.message else "[no message]"
    logger.info(f"Message from {user.username} ({user.id}): {text}")

async def error_handler(update, context):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    if not TOKEN or not ADMIN_ID:
        logger.error(f"Missing config: TOKEN={bool(TOKEN)}, ADMIN_ID={ADMIN_ID}")
        sys.exit(1)
        
    logger.info(f"Starting debug bot for admin {ADMIN_ID}")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("ping", handle_ping))
    app.add_handler(MessageHandler(filters.ALL, handle_all))
    app.add_error_handler(error_handler)
    
    logger.info("Starting polling with debug mode...")
    
    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query'],
            timeout=30,
            poll_interval=2.0,
            close_loop=False
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise

if __name__ == '__main__':
    main()