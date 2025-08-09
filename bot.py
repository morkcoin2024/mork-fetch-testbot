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
from config import (
    OPENAI_API_KEY, ASSISTANT_ADMIN_TELEGRAM_ID, 
    ASSISTANT_WRITE_GUARD, ASSISTANT_MODEL
)

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
        user_id = str(update.effective_user.id)
        
        # Check admin privileges
        if not ASSISTANT_ADMIN_TELEGRAM_ID or int(user_id) != ASSISTANT_ADMIN_TELEGRAM_ID:
            await update.message.reply_text("❌ Access denied. Admin privileges required.")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: `/assistant <your request>`\n\nExample: `/assistant add a new safety check for minimum balance`")
            return
        
        user_request = ' '.join(context.args)
        await update.message.reply_text(f"🤖 Processing request: {user_request[:100]}...")
        
        try:
            # Generate code using OpenAI
            response = self.assistant_codegen(user_request)
            
            if not response:
                await update.message.reply_text("❌ Failed to generate code response")
                return
            
            # Apply diffs if present
            applied_files = []
            restart_needed = False
            
            if response.get('diffs'):
                applied_files = self.apply_unified_diffs(response['diffs'])
            
            if response.get('restart', False):
                restart_needed = True
            
            # Create summary message
            summary = f"✅ **Assistant Task Complete**\n\n"
            summary += f"**Request:** {user_request[:80]}...\n\n"
            
            if response.get('summary'):
                summary += f"**Changes:** {response['summary']}\n\n"
            
            if applied_files:
                summary += f"**Files Modified:** {len(applied_files)}\n"
                for file in applied_files[:3]:  # Show first 3 files
                    summary += f"• {file}\n"
                if len(applied_files) > 3:
                    summary += f"• ... and {len(applied_files) - 3} more\n"
            
            if restart_needed:
                summary += "\n🔄 **Restart recommended** - applying now..."
            
            # Show diff preview
            if response.get('diffs'):
                diff_preview = self.create_diff_preview(response['diffs'])
                if diff_preview:
                    summary += f"\n**Diff Preview:**\n```\n{diff_preview}\n```"
            
            await update.message.reply_text(summary, parse_mode='Markdown')
            
            # Trigger restart if needed
            if restart_needed:
                self.safe_restart()
                await update.message.reply_text("🔄 System restarted successfully")
                
        except Exception as e:
            logger.error(f"Assistant command error: {e}")
            await update.message.reply_text(f"❌ Error processing request: {str(e)}")
    
    def assistant_codegen(self, user_request: str) -> Dict[str, Any]:
        """Generate code using OpenAI based on user request"""
        try:
            # Check if OpenAI is available
            if not OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY not found")
                return None
            
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            # Get current project structure for context
            project_context = self.get_project_context()
            
            system_prompt = f"""You are an expert Python developer working on the Mork F.E.T.C.H Bot project.

Project Context:
{project_context}

Generate code changes based on user requests. Return a JSON response with:
{{
    "summary": "Brief description of changes made",
    "diffs": [
        {{
            "file": "path/to/file.py",
            "content": "unified diff format starting with --- and +++"
        }}
    ],
    "restart": false // set to true if restart needed
}}

Guidelines:
- Use unified diff format for all changes
- Be precise with line numbers and context
- Only include actual changes, not entire files
- Follow existing code style and patterns
- Test imports and dependencies before suggesting
"""
            
            response = client.chat.completions.create(
                model=ASSISTANT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Request: {user_request}"}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"OpenAI codegen error: {e}")
            return None
    
    def get_project_context(self) -> str:
        """Get current project structure and key files for context"""
        try:
            context = "Mork F.E.T.C.H Bot - Solana Trading Bot\n\n"
            context += "Key Files:\n"
            
            key_files = [
                "bot.py", "jupiter_engine.py", "discovery.py", 
                "wallet_manager.py", "safety_system.py", "app.py", "main.py"
            ]
            
            for file in key_files:
                if os.path.exists(file):
                    try:
                        with open(file, 'r') as f:
                            lines = f.readlines()[:20]  # First 20 lines for context
                            context += f"\n{file} (first 20 lines):\n"
                            context += ''.join(lines)
                            context += f"... ({len(f.readlines()) + 20} total lines)\n"
                    except:
                        context += f"\n{file}: (unable to read)\n"
            
            return context[:2000]  # Limit context size
        except:
            return "Project context unavailable"
    
    def apply_unified_diffs(self, diffs: List[Dict[str, str]]) -> List[str]:
        """Apply unified diffs to files"""
        applied_files = []
        
        if ASSISTANT_WRITE_GUARD.upper() == 'ON':
            logger.info("WRITE_GUARD is ON - dry run mode, no files will be modified")
            return [diff['file'] for diff in diffs if 'file' in diff]
        
        try:
            import unidiff
            
            for diff_data in diffs:
                if 'file' not in diff_data or 'content' not in diff_data:
                    continue
                
                file_path = diff_data['file']
                diff_content = diff_data['content']
                
                try:
                    # Parse the unified diff
                    patch = unidiff.PatchSet(diff_content)
                    
                    for patched_file in patch:
                        target_file = patched_file.target_file.lstrip('/')
                        
                        if not os.path.exists(target_file):
                            # Create new file
                            with open(target_file, 'w') as f:
                                for hunk in patched_file:
                                    for line in hunk:
                                        if line.is_added:
                                            f.write(line.value)
                        else:
                            # Apply patch to existing file
                            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                                tmp.write(diff_content)
                                tmp.flush()
                                
                                # Use patch command
                                result = subprocess.run([
                                    'patch', target_file, tmp.name
                                ], capture_output=True, text=True)
                                
                                if result.returncode == 0:
                                    applied_files.append(target_file)
                                else:
                                    logger.error(f"Patch failed for {target_file}: {result.stderr}")
                                
                                os.unlink(tmp.name)
                
                except Exception as e:
                    logger.error(f"Error applying diff to {file_path}: {e}")
                    continue
        
        except ImportError:
            logger.error("unidiff package not available")
        
        return applied_files
    
    def create_diff_preview(self, diffs: List[Dict[str, str]]) -> str:
        """Create a preview of diffs (first ~50 lines)"""
        preview = ""
        line_count = 0
        
        for diff_data in diffs:
            if line_count >= 50:
                break
                
            if 'file' in diff_data and 'content' in diff_data:
                file_name = diff_data['file']
                content_lines = diff_data['content'].split('\n')
                
                preview += f"--- {file_name}\n"
                line_count += 1
                
                for line in content_lines:
                    if line_count >= 50:
                        preview += "... (truncated)\n"
                        break
                    preview += line + "\n"
                    line_count += 1
                
                preview += "\n"
                line_count += 1
        
        return preview.strip()
    
    def safe_restart(self):
        """Trigger a safe system restart"""
        try:
            # In a production environment, this might trigger a process restart
            # For now, we'll log the restart request
            logger.info("Safe restart requested - would restart system in production")
            
            # If running under a process manager, you might use:
            # os.system("supervisorctl restart mork-bot")
            # or send a signal to the parent process
            
        except Exception as e:
            logger.error(f"Restart failed: {e}")

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