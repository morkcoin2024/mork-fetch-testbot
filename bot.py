"""
bot.py - Telegram Bot Setup
Initialize bot, register handlers, process updates
"""
import os
import json
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes

from handlers.core import register_core_handlers
from handlers.trade import register_trade_handlers

logger = logging.getLogger(__name__)

# Bot token from environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
    raise ValueError("Bot token is required")

# Create bot application
bot_application = Application.builder().token(BOT_TOKEN).build()

# Register all handlers
register_core_handlers(bot_application)
register_trade_handlers(bot_application)

logger.info("✅ Mork F.E.T.C.H Bot handlers registered")

def process_update(update_data: dict) -> bool:
    """
    Process a single webhook update
    Returns True if successful, False otherwise
    """
    try:
        # Convert dict to Update object
        update = Update.de_json(update_data, bot_application.bot)
        
        if not update:
            logger.warning("Could not parse update data")
            return False
        
        # Process update (this handles all commands/messages)
        import asyncio
        
        # Create event loop if none exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Process the update
        context = ContextTypes.DEFAULT_TYPE(bot_application)
        
        # Run the update processing
        loop.run_until_complete(
            bot_application.process_update(update)
        )
        
        logger.info(f"✅ Update {update.update_id} processed successfully")
        return True
        
    except Exception as e:
        logger.exception(f"Failed to process update: {e}")
        return False

def set_webhook(webhook_url: str):
    """Set the webhook URL for the bot"""
    try:
        import asyncio
        
        async def _set_webhook():
            await bot_application.bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook set to: {webhook_url}")
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_set_webhook())
        
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

if __name__ == "__main__":
    # For testing - run bot in polling mode
    print("🐕 Mork F.E.T.C.H Bot starting in polling mode...")
    bot_application.run_polling()