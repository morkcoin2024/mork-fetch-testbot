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
from config import ASSISTANT_ADMIN_TELEGRAM_ID, ASSISTANT_GIT_BRANCH
from assistant_dev import assistant_codegen, apply_unified_diffs, maybe_run_commands, safe_restart_if_needed, get_file_tail, git_approve_merge, revert_to_backup
from backup_manager import create_backup, list_backups, restore_backup, prune_backups



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
        # Lightweight assistant command
        from alerts.telegram import cmd_assistant
        self.app.add_handler(CommandHandler("assistant", cmd_assistant))
        self.app.add_handler(CommandHandler("assistant_diff", self.assistant_diff_command))
        self.app.add_handler(CommandHandler("assistant_approve", self.assistant_approve_command))
        self.app.add_handler(CommandHandler("assistant_backup", self.assistant_backup_command))
        self.app.add_handler(CommandHandler("assistant_toggle", self.assistant_toggle_command))
        
        # Rules management commands
        if self.telegram_available:
            self.app.add_handler(CommandHandler("rules_show", self.rules_show_command))
            self.app.add_handler(CommandHandler("rules_profile", self.rules_profile_command))
            self.app.add_handler(CommandHandler("rules_set", self.rules_set_command))
            self.app.add_handler(CommandHandler("rules_reload", self.rules_reload_command))
        
        # Additional backup handlers as standalone functions
        from alerts.telegram import cmd_assistant_list_backups, cmd_assistant_revert
        self.app.add_handler(CommandHandler("assistant_list_backups", cmd_assistant_list_backups))
        self.app.add_handler(CommandHandler("assistant_revert", cmd_assistant_revert))
        
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
        
        # Check failsafe toggle
        from config import ASSISTANT_FAILSAFE
        if ASSISTANT_FAILSAFE == "ON":
            await update.message.reply_text("🚫 Assistant patching is currently DISABLED via failsafe toggle.")
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

        # Extract backup info from stdout if present
        backup_name = None
        if "Created backup:" in apply_res.stdout:
            for line in apply_res.stdout.split("\n"):
                if "Created backup:" in line:
                    backup_name = line.replace("Created backup:", "").strip()
                    break

        # Maybe run commands
        cmd_out = maybe_run_commands(commands)

        # Log the execution results
        from assistant_dev import audit_log
        audit_log(f"EXECUTION: user_id:{user_id} applied:{len(apply_res.applied_files)} failed:{len(apply_res.failed_files)} commands:{len(commands)} restart:{restart}")
        
        # Log backup if created
        if backup_name:
            audit_log(f"ASSISTANT_BACKUP: user_id:{user_id} auto-backup {backup_name}")
        
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
        
        # Add backup information to summary
        if backup_name:
            summary.append(f"💾 Backup: {backup_name}")
        elif apply_res.dry_run:
            from config import ASSISTANT_WRITE_GUARD
            if ASSISTANT_WRITE_GUARD.upper() == "OFF":
                summary.append("🧪 Dry-run only. No backup created. Toggle ASSISTANT_WRITE_GUARD=ON to write & auto-backup.")
        
        await update.message.reply_text("\n\n".join(summary)[:4000])

        # Optional preview of first diff
        if diffs:
            preview = diffs[0]
            await update.message.reply_text("Diff preview (first patch):\n\n" + preview[:3500])

        # Restart if requested
        safe_restart_if_needed(restart)
    
    async def assistant_toggle_command(self, update, context):
        """Handle /assistant_toggle ON|OFF command"""
        user_id = update.effective_user.id
        if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Not authorized.")
            return
        
        arg = update.message.text.split(maxsplit=1)
        if len(arg) != 2 or arg[1].strip().upper() not in {"ON", "OFF"}:
            await update.message.reply_text("Usage: /assistant_toggle ON|OFF")
            return
        
        mode = arg[1].strip().upper()
        import os
        os.environ["ASSISTANT_FAILSAFE"] = mode
        await update.message.reply_text(f"🔄 Failsafe set to {mode}.")
        
        from assistant_dev import audit_log
        audit_log(f"FAILSAFE_TOGGLE: user_id:{user_id} set to {mode}")
        # Optional: persist to .env or your secrets store here
    
    async def assistant_diff_command(self, update, context):
        """Handle /assistant_diff <path> command"""
        user_id = update.effective_user.id
        
        # Strict admin-only access control
        if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            from assistant_dev import audit_log
            audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
            return
        
        # Extract file path
        file_path = update.message.text.partition(" ")[2].strip()
        if not file_path:
            await update.message.reply_text("Usage: /assistant_diff <file_path>")
            return
        
        # Get file content
        content = get_file_tail(file_path, 100)
        
        # Format for Telegram
        response = f"📄 **{file_path}** (last 100 lines):\n\n```\n{content}\n```"
        
        # Split long messages
        if len(response) > 4000:
            response = response[:3900] + "\n... (truncated)\n```"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
        from assistant_dev import audit_log
        audit_log(f"FILE_INSPECT: user_id:{user_id} viewed {file_path}")
    
    async def assistant_approve_command(self, update, context):
        """Handle /assistant_approve command for Git staging"""
        user_id = update.effective_user.id
        
        # Strict admin-only access control
        if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            from assistant_dev import audit_log
            audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
            return
        
        if not ASSISTANT_GIT_BRANCH:
            await update.message.reply_text("❌ Git staging not enabled. Set ASSISTANT_GIT_BRANCH environment variable.")
            return
        
        await update.message.reply_text("🔄 Approving and merging staged changes...")
        
        # Merge the staging branch
        if git_approve_merge(ASSISTANT_GIT_BRANCH):
            await update.message.reply_text(f"✅ Successfully merged branch `{ASSISTANT_GIT_BRANCH}` to main")
            from assistant_dev import audit_log
            audit_log(f"GIT_APPROVED: user_id:{user_id} merged branch {ASSISTANT_GIT_BRANCH}")
        else:
            await update.message.reply_text(f"❌ Failed to merge branch `{ASSISTANT_GIT_BRANCH}`")
            from assistant_dev import audit_log  
            audit_log(f"GIT_APPROVE_FAILED: user_id:{user_id} could not merge {ASSISTANT_GIT_BRANCH}")
    
    async def assistant_backup_command(self, update, context):
        """Handle /assistant_backup command"""
        user_id = update.effective_user.id
        
        # Strict admin-only access control
        if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            from assistant_dev import audit_log
            audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
            return
        
        command_args = update.message.text.split()
        
        if len(command_args) < 2:
            # List backups
            backups = list_backups(10)
            if not backups:
                await update.message.reply_text("📦 No backups available")
                return
            
            backup_list = "\n".join(f"{i+1}. {backup}" for i, backup in enumerate(backups))
            await update.message.reply_text(f"📦 **Available Backups:**\n\n```\n{backup_list}\n```\n\nUse: `/assistant_backup restore <name>`", parse_mode='Markdown')
            return
        
        action = command_args[1].lower()
        
        if action == "create":
            label = command_args[2] if len(command_args) > 2 else "manual"
            try:
                backup_name = create_backup(label)
                prune_backups(20)
                await update.message.reply_text(f"✅ Created backup: `{backup_name}`", parse_mode='Markdown')
                from assistant_dev import audit_log
                audit_log(f"BACKUP_CREATE: user_id:{user_id} created {backup_name}")
            except Exception as e:
                await update.message.reply_text(f"❌ Backup failed: {e}")
        
        elif action == "restore":
            if len(command_args) < 3:
                await update.message.reply_text("Usage: `/assistant_backup restore <backup_name>`")
                return
            
            backup_name = command_args[2]
            try:
                await update.message.reply_text("🔄 Restoring backup...")
                revert_to_backup(backup_name)
                await update.message.reply_text(f"✅ Restored backup: `{backup_name}`", parse_mode='Markdown')
                from assistant_dev import audit_log
                audit_log(f"BACKUP_RESTORE: user_id:{user_id} restored {backup_name}")
            except Exception as e:
                await update.message.reply_text(f"❌ Restore failed: {e}")
        
        else:
            await update.message.reply_text("Usage:\n`/assistant_backup` - List backups\n`/assistant_backup create [label]` - Create backup\n`/assistant_backup restore <name>` - Restore backup", parse_mode='Markdown')
    
    async def rules_show_command(self, update, context):
        """Handle /rules_show command"""
        user_id = update.effective_user.id
        if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Not authorized.")
            return
        
        try:
            from rules_loader import Rules
            rules = Rules()
            
            current_profile = rules.meta.get("default_profile", "conservative")
            profile_data = rules.profile()
            
            summary = f"""📋 **Rules Configuration**

**Version:** {rules.meta.get('version', 'unknown')}
**Active Profile:** {current_profile}

**Output Limits:**
• Top N: {rules.output.get('top_n', 10)}
• Min Score: {rules.output.get('min_score', 70)}

**Key Filters ({current_profile}):**
• Min Liquidity: ${profile_data.get('filters', {}).get('min_liquidity_usd', 0):,}
• Min Holders: {profile_data.get('filters', {}).get('min_holders', 0)}
• Max Dev Holdings: {profile_data.get('filters', {}).get('max_dev_holdings_pct', 0)}%
• Age Range: {profile_data.get('filters', {}).get('min_age_minutes', 0)}-{profile_data.get('filters', {}).get('max_age_minutes', 1440)} min

**Available Profiles:** {', '.join(rules.profiles.keys())}

Use /rules_profile <name> to switch profiles."""
            
            await update.message.reply_text(summary, parse_mode='Markdown')
            
            from assistant_dev import audit_log
            audit_log(f"RULES_SHOW: user_id:{user_id}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error loading rules: {str(e)}")
    
    async def rules_profile_command(self, update, context):
        """Handle /rules_profile command"""
        user_id = update.effective_user.id
        if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Not authorized.")
            return
        
        args = update.message.text.split(maxsplit=1)
        if len(args) != 2:
            await update.message.reply_text("Usage: /rules_profile <conservative|degen>")
            return
        
        profile_name = args[1].strip().lower()
        
        try:
            from rules_loader import Rules
            rules = Rules()
            
            if profile_name in rules.profiles:
                rules.set_profile(profile_name)
                rules.save()
                await update.message.reply_text(f"✅ Switched to {profile_name} profile")
                
                from assistant_dev import audit_log
                audit_log(f"RULES_PROFILE: user_id:{user_id} switched to {profile_name}")
            else:
                available = ', '.join(rules.profiles.keys())
                await update.message.reply_text(f"❌ Profile '{profile_name}' not found. Available: {available}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error switching profile: {str(e)}")
    
    async def rules_set_command(self, update, context):
        """Handle /rules_set command"""
        user_id = update.effective_user.id
        if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Not authorized.")
            return
        
        args = update.message.text.split(maxsplit=3)
        if len(args) != 4:
            await update.message.reply_text("Usage: /rules_set <profile> <filter_key> <value>\nExample: /rules_set conservative min_liquidity_usd 50000")
            return
        
        _, profile_name, filter_key, value_str = args
        
        try:
            from rules_loader import Rules
            rules = Rules()
            
            # Parse value
            try:
                if value_str.lower() in ['true', 'false']:
                    value = value_str.lower() == 'true'
                elif '.' in value_str:
                    value = float(value_str)
                else:
                    value = int(value_str)
            except ValueError:
                value = value_str  # Keep as string
            
            if rules.update_filter(profile_name, filter_key, value):
                rules.save()
                await update.message.reply_text(f"✅ Updated {profile_name}.{filter_key} = {value}")
                
                from assistant_dev import audit_log
                audit_log(f"RULES_SET: user_id:{user_id} {profile_name}.{filter_key}={value}")
            else:
                await update.message.reply_text(f"❌ Failed to update {profile_name}.{filter_key}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating rule: {str(e)}")
    
    async def rules_reload_command(self, update, context):
        """Handle /rules_reload command"""
        user_id = update.effective_user.id
        if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Not authorized.")
            return
        
        try:
            from rules_loader import Rules
            rules = Rules()
            
            if rules.reload():
                profile = rules.meta.get("default_profile", "conservative")
                await update.message.reply_text(f"✅ Rules reloaded successfully\nActive profile: {profile}")
                
                from assistant_dev import audit_log
                audit_log(f"RULES_RELOAD: user_id:{user_id}")
            else:
                await update.message.reply_text("❌ Failed to reload rules")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error reloading rules: {str(e)}")

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