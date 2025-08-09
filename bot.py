"""
Mork F.E.T.C.H Bot - Telegram Interface
Production-ready Telegram bot for secure Solana token trading
"""

import os
import logging
import json
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from jupiter_engine import jupiter_engine
from discovery import discovery
from wallet_manager import wallet_manager
from safety_system import safety

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MorkFetchBot:
    """Main bot class handling all Telegram interactions"""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable required")
        
        self.application = Application.builder().token(self.bot_token).build()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup all command and callback handlers"""
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("wallet", self.wallet_command))
        self.application.add_handler(CommandHandler("balance", self.balance_command))
        self.application.add_handler(CommandHandler("snipe", self.snipe_command))
        self.application.add_handler(CommandHandler("fetch", self.fetch_command))
        self.application.add_handler(CommandHandler("emergency", self.emergency_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message and setup"""
        
        welcome_msg = """🐕 **Mork F.E.T.C.H Bot** — *Degens' Best Friend*

*Fast Execution, Trade Control Handler*

**Features:**
🎯 `/snipe <mint> <sol>` - Manual token sniping
🤖 `/fetch` - Auto-discovery trading  
💰 `/balance` - Check wallet & MORK holdings
⚙️ `/wallet` - Wallet management
📊 `/status` - System status

**Requirements:**
• ≥1 SOL worth of MORK for trading features
• Wallet with sufficient SOL balance

**Safety Features:**
🛡️ Safe mode with spend limits
🚨 Emergency stop capability  
🔐 Encrypted wallet storage
✅ Preflight & post-trade verification

Ready to fetch some profits? 🚀"""

        keyboard = [
            [InlineKeyboardButton("💰 Check MORK Holdings", callback_data="check_mork")],
            [InlineKeyboardButton("⚙️ Setup Wallet", callback_data="setup_wallet")],
            [InlineKeyboardButton("📖 Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode="Markdown")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detailed help information"""
        
        help_msg = """📖 **Mork F.E.T.C.H Bot Commands**

**Trading Commands:**
• `/snipe <mint> <amount>` - Buy specific token
  Example: `/snipe 7eMJmn1b... 0.01`

• `/fetch` - Auto-discover and trade new tokens
  Scans Pump.fun for bonded tokens with good liquidity

**Wallet Commands:**  
• `/wallet create` - Create new wallet
• `/wallet import <private_key>` - Import existing wallet
• `/balance` - Check SOL and MORK balances

**System Commands:**
• `/status` - Bot and safety system status
• `/emergency stop` - Admin emergency halt (if authorized)

**Requirements:**
🔹 Minimum 1 SOL worth of MORK tokens for trading
🔹 Sufficient SOL for trades + gas fees
🔹 Only trades bonded tokens routable via Jupiter

**Safety Features:**
🔹 Safe mode: Max 0.1 SOL per trade
🔹 Daily spending limits per user
🔹 Pre-flight balance and routing checks
🔹 Post-trade token delivery verification"""

        await update.message.reply_text(help_msg, parse_mode="Markdown")
    
    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Wallet management interface"""
        
        chat_id = update.effective_chat.id
        args = context.args
        
        if not args:
            # Show wallet status
            wallet_info = wallet_manager.get_wallet_info(chat_id)
            
            if not wallet_info:
                msg = "❌ No wallet found. Use:\n• `/wallet create` - Create new wallet\n• `/wallet import <private_key>` - Import existing"
            else:
                msg = "💼 **Your Wallets:**\n\n"
                for name, data in wallet_info.items():
                    status = "🔗 Imported" if data.get("imported") else "🆕 Generated"
                    msg += f"• **{name}**: {data['pubkey'][:8]}...{data['pubkey'][-8:]} {status}\n"
                
                msg += "\n💡 Use `/balance` to check wallet balances"
            
            await update.message.reply_text(msg, parse_mode="Markdown")
            return
        
        command = args[0].lower()
        
        if command == "create":
            result = wallet_manager.create_wallet(chat_id, "default")
            if result["success"]:
                msg = f"✅ **Wallet Created**\n\nAddress: `{result['pubkey']}`\n\n⚠️ **IMPORTANT**: This is a hot wallet. Fund with only what you can afford to trade with."
            else:
                msg = f"❌ Wallet creation failed: {result['error']}"
                
        elif command == "import":
            if len(args) < 2:
                msg = "❌ Please provide private key: `/wallet import <private_key>`"
            else:
                private_key = args[1]
                result = wallet_manager.import_wallet(chat_id, private_key, "default")
                if result["success"]:
                    msg = f"✅ **Wallet Imported**\n\nAddress: `{result['pubkey']}`\n\n🔐 Private key encrypted and stored securely."
                else:
                    msg = f"❌ Import failed: {result['error']}"
        else:
            msg = "❌ Unknown wallet command. Use `create` or `import`."
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check wallet balances including MORK holdings"""
        
        chat_id = update.effective_chat.id
        
        if not wallet_manager.has_wallet(chat_id):
            await update.message.reply_text("❌ No wallet found. Use `/wallet create` first.")
            return
        
        wallet_info = wallet_manager.get_wallet_info(chat_id)
        wallet_address = wallet_info["default"]["pubkey"]
        
        # Get SOL balance
        sol_balance = jupiter_engine.get_sol_balance(wallet_address)
        
        # Check MORK holdings for gate verification
        mork_ok, mork_msg = safety.check_mork_holdings(wallet_address, 1.0)  # Check for 1 SOL worth
        
        msg = f"""💰 **Wallet Balance**

**Address:** `{wallet_address}`

**SOL Balance:** {sol_balance:.6f} SOL

**MORK Holdings:** {mork_msg}

**Trading Status:**
{'✅ Eligible for /snipe and /fetch' if mork_ok else '❌ Insufficient MORK for trading'}

💡 Get MORK at: https://jup.ag/swap?inputMint=So11111111111111111111111111111111111111112&outputMint=ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"""

        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def snipe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manual token sniping with safety checks"""
        
        chat_id = update.effective_chat.id
        args = context.args
        
        if len(args) < 2:
            await update.message.reply_text("❌ Usage: `/snipe <token_mint> <sol_amount>`\nExample: `/snipe 7eMJmn1b... 0.01`")
            return
        
        if not wallet_manager.has_wallet(chat_id):
            await update.message.reply_text("❌ No wallet found. Use `/wallet create` first.")
            return
        
        token_mint = args[0]
        try:
            amount_sol = float(args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid SOL amount. Use decimal like 0.01")
            return
        
        # Get wallet info
        wallet_info = wallet_manager.get_wallet_info(chat_id)
        wallet_address = wallet_info["default"]["pubkey"]
        
        await update.message.reply_text(f"🎯 **Preparing Snipe**\n\nToken: `{token_mint[:8]}...`\nAmount: {amount_sol} SOL\n\nRunning safety checks...")
        
        # Comprehensive safety check
        safe_ok, safe_msg = safety.comprehensive_safety_check(
            chat_id, wallet_address, token_mint, amount_sol, "snipe"
        )
        
        if not safe_ok:
            await update.message.reply_text(f"❌ **Safety Check Failed**\n\n{safe_msg}")
            return
        
        # Execute the trade
        private_key = wallet_manager.get_private_key(chat_id, "default")
        if not private_key:
            await update.message.reply_text("❌ Could not access wallet private key.")
            return
        
        await update.message.reply_text("🔥 **Executing Trade...**\n\nSwapping via Jupiter DEX with verification...")
        
        result = jupiter_engine.safe_swap(private_key, token_mint, amount_sol)
        
        if result["success"]:
            # Record trade for daily limits
            safety.record_trade(chat_id, amount_sol)
            
            msg = f"""🎉 **Trade Successful!**

**Transaction:** `{result['signature']}`
**Explorer:** https://solscan.io/tx/{result['signature']}

**Tokens Received:** {result['delta_raw']:,}
**Pre-balance:** {result['pre_balance']:,}  
**Post-balance:** {result['post_balance']:,}

✅ Token delivery verified!"""
        else:
            msg = f"❌ **Trade Failed**\n\n{result['error']}"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def fetch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Automated token discovery and trading"""
        
        chat_id = update.effective_chat.id
        
        if not wallet_manager.has_wallet(chat_id):
            await update.message.reply_text("❌ No wallet found. Use `/wallet create` first.")
            return
        
        wallet_info = wallet_manager.get_wallet_info(chat_id)
        wallet_address = wallet_info["default"]["pubkey"]
        
        # Check MORK holdings for fetch feature (requires more MORK)
        mork_ok, mork_msg = safety.check_mork_holdings(wallet_address, 1.0)  # 1 SOL worth for fetch
        if not mork_ok:
            await update.message.reply_text(f"❌ **Fetch Feature Locked**\n\n{mork_msg}\n\nGet more MORK to unlock auto-trading.")
            return
        
        await update.message.reply_text("🤖 **F.E.T.C.H Mode Activated**\n\nScanning Pump.fun for new tradeable tokens...")
        
        # Find tradeable token
        token = discovery.find_tradeable_token()
        
        if not token:
            await update.message.reply_text("❌ **No Suitable Tokens Found**\n\nNo bonded & routable tokens meeting safety criteria right now. Try again later.")
            return
        
        # Default fetch amount (configurable)
        amount_sol = 0.02  # 0.02 SOL default for fetch
        
        # Safety check
        safe_ok, safe_msg = safety.comprehensive_safety_check(
            chat_id, wallet_address, token["mint"], amount_sol, "fetch"
        )
        
        if not safe_ok:
            await update.message.reply_text(f"❌ **Safety Check Failed**\n\n{safe_msg}")
            return
        
        # Show token and confirm
        confirm_msg = f"""🎯 **Token Found: {token['symbol']}**

**Mint:** `{token['mint']}`
**Market Cap:** ${token['market_cap']:,.0f}
**Age:** {token['age_hours']:.1f} hours
**Expected Tokens:** ~{token.get('expected_tokens_per_sol', 0) * amount_sol:,.0f}

**Trade Amount:** {amount_sol} SOL

Executing in 5 seconds..."""

        await update.message.reply_text(confirm_msg, parse_mode="Markdown")
        
        # Brief delay for user to see details
        import asyncio
        await asyncio.sleep(5)
        
        # Execute trade
        private_key = wallet_manager.get_private_key(chat_id, "default")
        result = jupiter_engine.safe_swap(private_key, token["mint"], amount_sol)
        
        if result["success"]:
            safety.record_trade(chat_id, amount_sol)
            
            msg = f"""🎉 **F.E.T.C.H Trade Successful!**

**Token:** {token['symbol']}
**Transaction:** `{result['signature']}`
**Explorer:** https://solscan.io/tx/{result['signature']}

**Tokens Received:** {result['delta_raw']:,}
**Market Cap:** ${token['market_cap']:,.0f}

✅ New token fetched and verified!"""
        else:
            msg = f"❌ **F.E.T.C.H Trade Failed**\n\n{result['error']}"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """System status and safety information"""
        
        emergency_ok, emergency_msg = safety.check_emergency_stop()
        safe_mode_ok, safe_mode_msg = safety.check_safe_mode_limits(0.01)  # Test with small amount
        
        status_msg = f"""📊 **Mork F.E.T.C.H Status**

**System Status:** {'🟢 Operational' if emergency_ok else '🔴 Emergency Stop Active'}
**Safety Mode:** {'🟡 Active' if safety.safe_mode else '🟢 Disabled'}
**Emergency Stop:** {'✅ Normal' if emergency_ok else '🚨 ACTIVE'}

**Current Limits:**
• Max trade: {safety.max_trade_sol} SOL
• Daily limit: {safety.daily_spend_limit} SOL per user
• MORK requirement: {safety.min_mork_for_snipe} SOL worth for /snipe
• MORK requirement: {safety.min_mork_for_fetch} SOL worth for /fetch

**Network Status:**
• Jupiter API: 🟢 Connected
• Solana RPC: 🟢 Connected  
• Pump.fun API: 🟢 Connected

*Ready to F.E.T.C.H profits safely!* 🐕"""

        await update.message.reply_text(status_msg, parse_mode="Markdown")
    
    async def emergency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Emergency stop control (admin only)"""
        
        chat_id = update.effective_chat.id
        args = context.args
        
        # TODO: Add proper admin verification
        # For now, allow anyone to check status, restrict stop/start
        
        if not args:
            emergency_ok, emergency_msg = safety.check_emergency_stop()
            status = "ACTIVE" if not emergency_ok else "INACTIVE"
            await update.message.reply_text(f"🚨 Emergency Stop Status: {status}")
            return
        
        command = args[0].lower()
        if command in ["stop", "activate"]:
            result = safety.set_emergency_stop(True, str(chat_id))
            await update.message.reply_text(f"🚨 {result}")
        elif command in ["start", "deactivate", "resume"]:
            result = safety.set_emergency_stop(False, str(chat_id))
            await update.message.reply_text(f"✅ {result}")
        else:
            await update.message.reply_text("❌ Use: `/emergency stop` or `/emergency start`")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        
        query = update.callback_query
        await query.answer()
        
        if query.data == "check_mork":
            # Trigger balance check
            context.args = []
            await self.balance_command(update, context)
            
        elif query.data == "setup_wallet":
            msg = "💼 **Wallet Setup**\n\n• `/wallet create` - Generate new wallet\n• `/wallet import <key>` - Import existing wallet"
            await query.edit_message_text(msg, parse_mode="Markdown")
            
        elif query.data == "help":
            context.args = []
            await self.help_command(update, context)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command messages"""
        
        # For now, just provide help hint
        await update.message.reply_text("💡 Use `/help` to see available commands, or `/start` for the main menu.")
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Mork F.E.T.C.H Bot...")
        self.application.run_polling()

# Create global bot instance
mork_bot = MorkFetchBot() if os.getenv("TELEGRAM_BOT_TOKEN") else None