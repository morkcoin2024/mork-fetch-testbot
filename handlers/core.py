"""
handlers/core.py - Core Bot Commands
/start, /linkwallet, /status, /config, /stop
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from wallet import get_wallet, create_wallet, import_wallet
from jupiter_engine import _get_sol_balance
from risk import check_safe_mode, check_emergency_stop

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message"""
    welcome_text = """🐕 **Mork — Degens' Best Friend is online!**

F.E.T.C.H. = Fast Execution, Trade Control Handler

**Commands:**
• /linkwallet - Import or create wallet
• /status - Check balance and system status
• /snipe <mint> <sol> - Buy specific token
• /fetch - Auto-discover and buy token
• /positions - View your holdings
• /config - Adjust settings
• /help - Show detailed help

**Safety First:**
• SAFE_MODE protects against real trades
• Emergency stops prevent risky situations
• Only trade with money you can afford to lose

Ready to fetch some profits! 🚀"""

    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def linkwallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Link wallet - import existing or create new"""
    chat_id = str(update.effective_chat.id)
    
    # Check if wallet already exists
    existing_wallet = get_wallet(chat_id)
    if existing_wallet:
        await update.message.reply_text(
            f"✅ **Wallet Already Linked**\n\n"
            f"**Address:** `{existing_wallet['pubkey']}`\n"
            f"**Label:** {existing_wallet['label']}\n\n"
            f"To change wallet, contact support.",
            parse_mode='Markdown'
        )
        return
    
    # Check if private key provided
    if len(context.args) == 0:
        # No private key - create new wallet
        result = create_wallet(chat_id)
        
        if result["success"]:
            await update.message.reply_text(
                f"✅ **New Wallet Created**\n\n"
                f"**Address:** `{result['pubkey']}`\n\n"
                f"⚠️ **IMPORTANT:** This is a burner wallet for trading only. "
                f"Send some SOL to this address to start trading.\n\n"
                f"💡 **Tip:** Keep your main funds in a secure wallet like Phantom.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ **Wallet Creation Failed**\n\n{result['error']}"
            )
            
    else:
        # Private key provided - import wallet
        private_key = context.args[0]
        result = import_wallet(chat_id, private_key)
        
        if result["success"]:
            await update.message.reply_text(
                f"✅ **Wallet Imported**\n\n"
                f"**Address:** `{result['pubkey']}`\n\n"
                f"Wallet is ready for trading!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ **Import Failed**\n\n{result['error']}\n\n"
                f"**Usage:** `/linkwallet <base58-private-key>`\n"
                f"Or use `/linkwallet` to create a new wallet.",
                parse_mode='Markdown'
            )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system and wallet status"""
    chat_id = str(update.effective_chat.id)
    
    status_lines = ["📊 **System Status**\n"]
    
    # Check system flags
    safe_mode = check_safe_mode()
    is_stopped, stop_reason = check_emergency_stop()
    
    status_lines.append(f"**Safe Mode:** {'🟡 ON' if safe_mode else '🟢 OFF'}")
    
    if is_stopped:
        status_lines.append(f"**Emergency Stop:** 🔴 {stop_reason}")
    else:
        status_lines.append("**Emergency Stop:** 🟢 OFF")
    
    # Check wallet
    wallet = get_wallet(chat_id)
    if wallet:
        sol_balance = _get_sol_balance(wallet['pubkey'])
        status_lines.append(f"\n💰 **Wallet Status**")
        status_lines.append(f"**Address:** `{wallet['pubkey']}`")
        status_lines.append(f"**SOL Balance:** {sol_balance:.6f} SOL")
        
        if sol_balance < 0.01:
            status_lines.append("⚠️ Low SOL balance - add funds to trade")
    else:
        status_lines.append("\n❌ **No Wallet Linked**")
        status_lines.append("Use /linkwallet to get started")
    
    await update.message.reply_text("\n".join(status_lines), parse_mode='Markdown')

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show/update user configuration"""
    chat_id = str(update.effective_chat.id)
    
    # For now, show default config
    # TODO: Implement user settings in database
    config_text = """⚙️ **Trading Configuration**

**Current Settings:**
• Slippage: 1.5% (150 bps)
• Priority Fee: 2,000,000 microlamports
• Spend Cap: 0.1 SOL per trade
• MORK Requirement (Snipe): 0.1 SOL worth
• MORK Requirement (Fetch): 1.0 SOL worth

**Auto Trading:**
• Auto TP/SL: Disabled
• Stop Loss: 50%
• Take Profit: 200%

💡 Configuration updates coming soon!"""

    await update.message.reply_text(config_text, parse_mode='Markdown')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Emergency stop toggle (admin only)"""
    # For now, just show status
    # TODO: Implement admin check and emergency stop toggle
    await update.message.reply_text(
        "🛑 **Emergency Stop**\n\n"
        "Admin-only command for emergency trading halt.\n"
        "Contact support if trading needs to be stopped."
    )

# Register handlers
def register_core_handlers(application):
    """Register all core command handlers"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("linkwallet", linkwallet_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("config", config_command))
    application.add_handler(CommandHandler("stop", stop_command))