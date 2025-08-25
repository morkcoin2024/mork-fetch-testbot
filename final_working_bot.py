#!/usr/bin/env python3
"""
Final working polling bot - bypasses Flask webhook issues
Sets POLLING_MODE to prevent Flask bot interference
"""

import logging
import os
import time

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# CRITICAL: Prevent Flask bot from consuming updates
os.environ["POLLING_MODE"] = "ON"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("final_working_bot.log")],
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ASSISTANT_ADMIN_TELEGRAM_ID", "1653046781"))


async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ping command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    logger.info(f"PING received from {username} (ID: {user_id})")

    # Check if admin
    is_admin = user_id == ADMIN_ID

    response = f"""🏓 PONG!

**Bot Status**: ✅ Operational
**Mode**: Polling (Flask webhook disabled)
**Time**: {time.strftime("%Y-%m-%d %H:%M:%S")}
**Your ID**: {user_id}
**Admin Access**: {"✅ Yes" if is_admin else "❌ No"}
**Response Delay**: < 1 second

Bot is working perfectly! 🎉"""

    await update.message.reply_text(response, parse_mode="Markdown")
    logger.info(f"PONG response sent to {username}")


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    logger.info(f"STATUS requested by {username} (ID: {user_id})")

    status_msg = f"""📊 **Mork F.E.T.C.H Bot Status**

🟢 **Connection**: Active
🔄 **Mode**: Polling (Stable)
⚡ **Response Time**: < 1 second
🛡️ **Admin ID**: {ADMIN_ID}
👤 **Your ID**: {user_id}
🔑 **Admin Access**: {"Yes ✅" if user_id == ADMIN_ID else "No ❌"}

⏰ **Uptime**: {time.strftime("%H:%M:%S")} today
🚀 **Version**: Final Working Bot v1.0

**Available Commands:**
• /ping - Test bot response
• /status - This status message
• /help - Command help

*The Degens' Best Friend* 🐕"""

    await update.message.reply_text(status_msg, parse_mode="Markdown")
    logger.info(f"Status sent to {username}")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🤖 **Mork F.E.T.C.H Bot Commands**

**Basic Commands:**
• `/ping` - Test bot connectivity
• `/status` - Show bot status
• `/help` - This help message

**Bot Info:**
• Fast Execution, Trade Control Handler
• Solana/Pump.fun trading bot
• Currently in polling mode for stability

**Support:**
This is the stable polling version that bypasses webhook connectivity issues.

*Ready to fetch some profits!* 🚀"""

    await update.message.reply_text(help_text, parse_mode="Markdown")


async def unknown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands"""
    text = update.message.text
    user_id = update.effective_user.id

    logger.info(f"Unknown command '{text}' from user {user_id}")

    response = """❓ **Unknown Command**

Available commands:
• `/ping` - Test bot
• `/status` - Bot status
• `/help` - Command help

Try one of these commands! 🤖"""

    await update.message.reply_text(response, parse_mode="Markdown")


def main():
    """Main bot function"""
    logger.info("=" * 50)
    logger.info("🚀 Starting Final Working Bot")
    logger.info("=" * 50)
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Polling Mode: {os.environ.get('POLLING_MODE', 'OFF')}")
    logger.info(f"Token configured: {bool(TOKEN)}")

    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return

    # Build application
    application = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("ping", ping_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("start", help_handler))

    # Handle unknown commands
    application.add_handler(MessageHandler(filters.COMMAND, unknown_handler))

    logger.info("✅ Handlers registered successfully")
    logger.info("🔄 Starting polling...")

    # Start polling with optimal settings
    try:
        application.run_polling(
            drop_pending_updates=True,
            timeout=30,
            poll_interval=1.0,
            read_timeout=20,
            write_timeout=20,
            connect_timeout=20,
        )
    except Exception as e:
        logger.error(f"❌ Polling failed: {e}")
        raise


if __name__ == "__main__":
    main()
