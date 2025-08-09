"""
Mork F.E.T.C.H Bot - Telegram Interface
Production-ready bot with safety systems and Jupiter DEX integration
"""

import os
import logging
import json
import subprocess
import tempfile
from typing import List, Dict, Any
from config import ASSISTANT_ADMIN_TELEGRAM_ID
from assistant_dev import assistant_codegen, apply_unified_diffs, maybe_run_commands, safe_restart_if_needed



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MorkFetchBot:
    """Main bot class with graceful telegram import handling"""
    
    def __init__(self):
        self.app = None
        self.telegram_available = False
        
        # Try to import telegram components
        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
            self.telegram_available = True
            
            token = os.environ.get('TELEGRAM_BOT_TOKEN')
            if not token:
                logger.warning("TELEGRAM_BOT_TOKEN not found - bot disabled")
                return
            
            self.app = Application.builder().token(token).build()
            self.setup_handlers()
            logger.info("Telegram bot initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Telegram not available: {e}")
            self.telegram_available = False
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            self.telegram_available = False
    
    def setup_handlers(self):
        """Set up command handlers"""
        if not self.app or not self.telegram_available:
            return
        
        from telegram.ext import CommandHandler, MessageHandler, filters
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("wallet", self.wallet_command))
        self.app.add_handler(CommandHandler("snipe", self.snipe_command))
        self.app.add_handler(CommandHandler("fetch", self.fetch_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("emergency", self.emergency_command))
        self.app.add_handler(CommandHandler("assistant", self.assistant_command))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update, context):
        """Handle /start command"""
        if not self.telegram_available:
            return
        
        from jupiter_engine import jupiter_engine
        from wallet_manager import wallet_manager
        from safety_system import safety
        
        user_id = str(update.effective_user.id)
        
        welcome_message = f"""🐕 **Mork F.E.T.C.H Bot** - The Degens' Best Friend

*Fast Execution, Trade Control Handler*

**Your Trading Assistant is Ready!**

🎯 **Quick Commands:**
• `/balance` - Check your wallet
• `/snipe <mint> <sol>` - Manual trade
• `/fetch` - Auto-discover tokens
• `/help` - Full command list

⚡ **Getting Started:**
1. Import your wallet: `/wallet import <key>`
2. Check MORK holdings: `/balance`
3. Start trading: `/snipe` or `/fetch`

🛡️ **Safety Features:**
• Emergency stops & safe mode
• MORK holder gating (1 SOL worth required)
• Daily spending limits
• Real-time validation

Ready to fetch some profits? 🚀"""
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        logger.info(f"User {user_id} started bot")
    
    async def help_command(self, update, context):
        """Handle /help command"""
        help_text = """📖 **Mork F.E.T.C.H Bot Commands**

💼 **Wallet Management:**
• `/wallet create` - Generate new wallet
• `/wallet import <key>` - Import existing wallet
• `/balance` - Check SOL and MORK balances

🎯 **Trading Commands:**
• `/snipe <mint> <sol>` - Manual token sniping
• `/fetch` - Auto-discover and trade tokens
• `/validate <mint>` - Check if token is tradeable

🛡️ **Safety & System:**
• `/status` - System and safety status
• `/emergency stop` - Activate emergency stop
• `/emergency start` - Deactivate emergency stop

🤖 **Admin Commands:**
• `/assistant <request>` - AI-powered code generation (admin only)

📋 **Requirements:**
• Manual trading (/snipe): 0.1 SOL worth of MORK
• Auto trading (/fetch): 1.0 SOL worth of MORK

🔒 **Security:** Your private keys never leave this secure environment."""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def balance_command(self, update, context):
        """Handle /balance command"""
        from jupiter_engine import jupiter_engine
        from wallet_manager import wallet_manager
        from safety_system import safety
        
        user_id = str(update.effective_user.id)
        
        if not wallet_manager.has_wallet(user_id):
            await update.message.reply_text("❌ No wallet found. Use `/wallet create` or `/wallet import` first.")
            return
        
        try:
            wallet_info = wallet_manager.get_wallet_info(user_id)
            wallet_address = wallet_info["default"]["pubkey"]
            
            # Get SOL balance
            sol_balance = jupiter_engine.get_sol_balance(wallet_address)
            
            # Check MORK holdings
            mork_ok, mork_msg = safety.check_mork_holdings(wallet_address, 1.0)
            
            message = f"""💰 **Wallet Balance**

**Address:** `{wallet_address}`
**SOL Balance:** {sol_balance:.6f} SOL

**MORK Holdings:** {mork_msg}

**Trading Status:**
{'✅ Eligible for all trading' if mork_ok else '⚠️ Need more MORK for full access'}"""
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error checking balance: {str(e)}")
    
    async def wallet_command(self, update, context):
        """Handle /wallet command"""
        from wallet_manager import wallet_manager
        
        user_id = str(update.effective_user.id)
        
        if not context.args:
            await update.message.reply_text("Usage: `/wallet create` or `/wallet import <private_key>`")
            return
        
        action = context.args[0].lower()
        
        if action == "create":
            result = wallet_manager.create_wallet(user_id, "default")
            if result["success"]:
                await update.message.reply_text(f"✅ **Wallet Created**\n\nAddress: `{result['pubkey']}`\n\n⚠️ **Important:** Your private key is encrypted and stored securely. Never share it!")
            else:
                await update.message.reply_text(f"❌ Failed to create wallet: {result['error']}")
        
        elif action == "import":
            if len(context.args) < 2:
                await update.message.reply_text("Usage: `/wallet import <private_key>`")
                return
            
            private_key = context.args[1]
            result = wallet_manager.import_wallet(user_id, private_key, "default")
            
            if result["success"]:
                await update.message.reply_text(f"✅ **Wallet Imported**\n\nAddress: `{result['pubkey']}`\n\n🔒 Your private key is encrypted and secure.")
            else:
                await update.message.reply_text(f"❌ Failed to import wallet: {result['error']}")
        
        else:
            await update.message.reply_text("Unknown wallet command. Use `create` or `import`.")
    
    async def snipe_command(self, update, context):
        """Handle /snipe command"""
        from jupiter_engine import jupiter_engine
        from wallet_manager import wallet_manager
        from safety_system import safety
        
        user_id = str(update.effective_user.id)
        
        if len(context.args) < 2:
            await update.message.reply_text("Usage: `/snipe <token_mint> <sol_amount>`\n\nExample: `/snipe 7eMJmn1bTJnmhK4qZsZfMPUWuBhzQ5VXx1B1Cj6pump 0.01`")
            return
        
        if not wallet_manager.has_wallet(user_id):
            await update.message.reply_text("❌ No wallet found. Use `/wallet create` or `/wallet import` first.")
            return
        
        try:
            token_mint = context.args[0]
            amount_sol = float(context.args[1])
            
            wallet_info = wallet_manager.get_wallet_info(user_id)
            wallet_address = wallet_info["default"]["pubkey"]
            
            await update.message.reply_text(f"🎯 **Preparing Snipe**\n\nToken: `{token_mint[:8]}...`\nAmount: {amount_sol} SOL\n\nRunning safety checks...")
            
            # Safety checks
            safe_ok, safe_msg = safety.comprehensive_safety_check(
                user_id, wallet_address, token_mint, amount_sol, "snipe"
            )
            
            if not safe_ok:
                await update.message.reply_text(f"❌ **Safety Check Failed**\n\n{safe_msg}")
                return
            
            await update.message.reply_text("✅ Safety checks passed. Executing trade...")
            
            # Execute trade
            private_key = wallet_manager.get_private_key(user_id, "default")
            if not private_key:
                await update.message.reply_text("❌ Could not access wallet private key")
                return
            
            result = jupiter_engine.safe_swap(private_key, token_mint, amount_sol)
            
            if result["success"]:
                safety.record_trade(user_id, amount_sol)
                
                message = f"""🎉 **Snipe Successful!**

**Transaction:** `{result['signature']}`
**Tokens Received:** {result['delta_raw']:,}
**Status:** Trade completed and verified

Your tokens are now in your wallet! 🚀"""
                
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ **Trade Failed**\n\n{result['error']}")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid SOL amount. Use a number like 0.01")
        except Exception as e:
            await update.message.reply_text(f"❌ Error executing snipe: {str(e)}")
    
    async def fetch_command(self, update, context):
        """Handle /fetch command"""
        from jupiter_engine import jupiter_engine
        from discovery import discovery
        from wallet_manager import wallet_manager
        from safety_system import safety
        
        user_id = str(update.effective_user.id)
        
        if not wallet_manager.has_wallet(user_id):
            await update.message.reply_text("❌ No wallet found. Use `/wallet create` or `/wallet import` first.")
            return
        
        wallet_info = wallet_manager.get_wallet_info(user_id)
        wallet_address = wallet_info["default"]["pubkey"]
        
        # Check MORK holdings for FETCH
        mork_ok, mork_msg = safety.check_mork_holdings(wallet_address, 1.0)
        if not mork_ok:
            await update.message.reply_text(f"❌ **F.E.T.C.H Mode Locked**\n\n{mork_msg}\n\nRequirement: 1.0 SOL worth of MORK for automated trading.")
            return
        
        await update.message.reply_text("🤖 **F.E.T.C.H Mode Activated**\n\nScanning for tradeable tokens...")
        
        try:
            # Find tradeable token
            token = discovery.find_tradeable_token()
            
            if not token:
                await update.message.reply_text("❌ No suitable tokens found in current scan.\n\nThis is normal - will keep monitoring for opportunities.")
                return
            
            amount_sol = 0.02  # Default FETCH amount
            
            message = f"""🎯 **Token Discovered**

**Symbol:** {token['symbol']}
**Market Cap:** ${token['market_cap']:,.0f}
**Expected Tokens:** ~{token.get('expected_tokens_per_sol', 0):,.0f}

Executing F.E.T.C.H trade with {amount_sol} SOL..."""
            
            await update.message.reply_text(message)
            
            # Execute trade
            private_key = wallet_manager.get_private_key(user_id, "default")
            result = jupiter_engine.safe_swap(private_key, token["mint"], amount_sol)
            
            if result["success"]:
                safety.record_trade(user_id, amount_sol)
                
                success_message = f"""🎉 **F.E.T.C.H Successful!**

**Token:** {token['symbol']}
**Transaction:** `{result['signature']}`
**Tokens Received:** {result['delta_raw']:,}

The degen's best friend just fetched you some profits! 🐕🚀"""
                
                await update.message.reply_text(success_message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ **F.E.T.C.H Failed**\n\n{result['error']}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error in F.E.T.C.H mode: {str(e)}")
    
    async def status_command(self, update, context):
        """Handle /status command"""
        from safety_system import safety
        
        # Emergency stop
        emergency_ok, _ = safety.check_emergency_stop()
        
        # Safe mode
        safe_mode_status = "Active" if safety.safe_mode else "Disabled"
        
        status_message = f"""📊 **Mork F.E.T.C.H System Status**

🚨 **Emergency Stop:** {'Normal' if emergency_ok else 'ACTIVE'}
🛡️ **Safe Mode:** {safe_mode_status}
⚡ **Max Trade:** {safety.max_trade_sol} SOL
📊 **Daily Limit:** {safety.daily_spend_limit} SOL

🎯 **Trading Requirements:**
• Snipe: 0.1 SOL worth of MORK
• F.E.T.C.H: 1.0 SOL worth of MORK

🔗 **Systems:** All operational"""
        
        await update.message.reply_text(status_message)
    
    async def emergency_command(self, update, context):
        """Handle /emergency command"""
        from safety_system import safety
        
        user_id = str(update.effective_user.id)
        
        if not context.args:
            emergency_ok, _ = safety.check_emergency_stop()
            status = "ACTIVE" if not emergency_ok else "INACTIVE"
            await update.message.reply_text(f"🚨 **Emergency Stop:** {status}")
            return
        
        action = context.args[0].lower()
        
        if action in ["stop", "activate"]:
            result = safety.set_emergency_stop(True, user_id)
            await update.message.reply_text(f"🚨 **Emergency Stop Activated**\n\nAll trading disabled until manually resumed.")
        elif action in ["start", "resume"]:
            result = safety.set_emergency_stop(False, user_id)
            await update.message.reply_text(f"✅ **Emergency Stop Deactivated**\n\nTrading resumed with normal safety checks.")
        else:
            await update.message.reply_text("Usage: `/emergency stop` or `/emergency start`")
    
    async def assistant_command(self, update, context):
        """Handle /assistant command for AI-powered code generation"""
        # Delegate to standalone function (converted to async)
        try:
            await self._run_cmd_assistant(update, context)
        except Exception as e:
            logger.error(f"Assistant command error: {e}")
            await update.message.reply_text(f"❌ Error processing request: {str(e)}")
    
    async def _run_cmd_assistant(self, update, context):
        """Async wrapper for cmd_assistant"""
        user_id = update.effective_user.id
        
        # Strict admin-only access control
        if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            from assistant_dev import audit_log
            audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
            return

        request_text = update.message.text.partition(" ")[2].strip()
        if not request_text:
            await update.message.reply_text("Usage: /assistant <what you want changed>")
            return

        await update.message.reply_text("🤖 Thinking… generating patch.")
        result = assistant_codegen(request_text, user_id)
        plan = result.get("plan","(no plan)")
        diffs = result.get("diffs", [])
        commands = result.get("commands", [])
        restart = result.get("restart", "none")

        # Apply diffs
        apply_res = apply_unified_diffs(diffs)

        # Maybe run commands
        cmd_out = maybe_run_commands(commands)

        # Log the execution results
        from assistant_dev import audit_log
        audit_log(f"EXECUTION: user_id:{user_id} applied:{len(apply_res.applied_files)} failed:{len(apply_res.failed_files)} commands:{len(commands)} restart:{restart}")
        
        # Handle oversized diffs with helpful message
        if any("exceeds" in f for f in apply_res.failed_files):
            await update.message.reply_text("⚠️ **Size Limit Exceeded**\n\nSome diffs were too large (>50KB per diff, max 2 diffs). Please break your request into smaller, more focused changes.")
        
        # Summarize
        summary = [
            "✅ Plan:\n" + plan,
            f"✍️ Write mode: {'ON' if not apply_res.dry_run else 'DRY-RUN (no files written)'}",
            f"📝 Applied: {len(apply_res.applied_files)} files",
            (("❌ Failed: " + ", ".join(apply_res.failed_files)) if apply_res.failed_files else "❌ Failed: none"),
            (f"🔧 Commands run:\n{cmd_out[:1500]}..." if cmd_out else "🔧 Commands: none"),
            f"♻️ Restart: {restart}",
        ]
        await update.message.reply_text("\n\n".join(summary)[:4000])

        # Optional preview of first diff
        if diffs:
            preview = diffs[0]
            await update.message.reply_text("Diff preview (first patch):\n\n" + preview[:3500])

        # Restart if requested
        safe_restart_if_needed(restart)
    


    async def handle_message(self, update, context):
        """Handle non-command messages"""
        await update.message.reply_text("Use `/help` to see available commands or `/start` to begin.")
    
    async def process_webhook_update(self, update_data):
        """Process webhook update"""
        if not self.app or not self.telegram_available:
            return {"status": "error", "message": "Bot not initialized"}
        
        try:
            from telegram import Update
            update = Update.de_json(update_data, self.app.bot)
            await self.app.process_update(update)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return {"status": "error", "message": str(e)}

# Initialize bot
mork_bot = MorkFetchBot()