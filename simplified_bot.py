import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from models import UserSession
from utils import check_mork_token_balance
from database import db

logger = logging.getLogger(__name__)

# Decorator to ensure user holds at least 100,000 MORK
def require_mork_holder(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        user_address = context.user_data.get("wallet")  # Assume wallet is stored per user

        if not user_address:
            await update.message.reply_text("You need to link a wallet first.")
            return

        try:
            holds_mork = check_mork_token_balance(user_address, minimum_required=100000)
            if not holds_mork:
                await update.message.reply_text("You must hold at least 100,000 MORK to use this feature.")
                return
        except Exception as e:
            logger.error(f"Token balance check failed: {e}")
            await update.message.reply_text("Couldn't verify your MORK holdings. Try again later.")
            return

        return await func(update, context)

    return wrapper

@require_mork_holder
async def handle_fetch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)

    logger.info(f"/fetch called by chat_id: {chat_id}")

    session = UserSession.query.filter_by(chat_id=chat_id).first()
    if not session:
        logger.info(f"No session found for chat_id: {chat_id}, creating one.")
        session = UserSession(chat_id=chat_id)
        db.session.add(session)
        db.session.commit()

    # Simulated token fetching and trading flow
    try:
        await update.message.reply_text("Scanning Pump.fun tokens and preparing your trade...")
        # Replace this with actual trading logic
        # result = await trader.execute_trade(...)
        await update.message.reply_text("✅ Trade prepared. Mork is ready to snipe.")
    except Exception as e:
        logger.error(f"/fetch failed for {chat_id}: {e}")
        await update.message.reply_text("❌ Something went wrong during the fetch process.")

# Register handler with Telegram dispatcher (example)
def register_handlers(app):
    app.add_handler(CommandHandler("fetch", handle_fetch))
