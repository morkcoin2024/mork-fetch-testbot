#!/usr/bin/env python3
"""
Simple polling bot - fixed version
Handles all admin commands with direct polling
"""

import asyncio
import logging
import os
import sys
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID', 0))

async def handle_ping(update, context):
    """Handle /ping command"""
    user = update.effective_user
    logger.info(f"PING command from {user.username} (ID: {user.id})")
    
    if user.id == ADMIN_ID:
        await update.message.reply_text('🏓 **Pong!** Bot is working in polling mode.')
        logger.info("Pong response sent")
    else:
        logger.info(f"Ping ignored from non-admin user {user.id}")

async def handle_status(update, context):
    """Handle /status command"""
    user = update.effective_user
    logger.info(f"STATUS command from {user.username} (ID: {user.id})")
    
    if user.id == ADMIN_ID:
        await update.message.reply_text('''🤖 **Mork F.E.T.C.H Bot Status**

Mode: Polling (direct)
System: Operational
Bot: Responding
Admin: Authorized

All systems working correctly.''', parse_mode='Markdown')
        logger.info("Status response sent")

async def handle_whoami(update, context):
    """Handle /whoami command"""
    user = update.effective_user
    logger.info(f"WHOAMI command from {user.username} (ID: {user.id})")
    
    is_admin = user.id == ADMIN_ID
    await update.message.reply_text(f'''**Your Telegram Info:**
ID: `{user.id}`
Username: @{user.username or 'unknown'}
Admin: {'Yes' if is_admin else 'No'}''', parse_mode='Markdown')
    logger.info("Whoami response sent")

async def handle_all_messages(update, context):
    """Handle all other messages"""
    user = update.effective_user
    text = update.message.text or '[no text]'
    logger.info(f"Message from {user.username} (ID: {user.id}): {text}")
    
    # Only respond to admin for unhandled commands
    if user.id == ADMIN_ID and text.startswith('/'):
        await update.message.reply_text(f'Command received: {text}\nBot is working. Available commands: /ping, /status, /whoami')

def main():
    """Start the polling bot"""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found")
        sys.exit(1)
        
    if not ADMIN_ID:
        logger.error("ASSISTANT_ADMIN_TELEGRAM_ID not found") 
        sys.exit(1)
        
    logger.info(f"Starting simple polling bot for admin ID: {ADMIN_ID}")
    
    # Build application
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("ping", handle_ping))
    app.add_handler(CommandHandler("status", handle_status)) 
    app.add_handler(CommandHandler("whoami", handle_whoami))
    
    # Handle all other messages (for debugging)
    app.add_handler(MessageHandler(filters.ALL, handle_all_messages))
    
    logger.info("Starting polling...")
    
    try:
        # Start polling with error handling
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message'],
            timeout=20,
            poll_interval=1.0
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise

if __name__ == '__main__':
    main()