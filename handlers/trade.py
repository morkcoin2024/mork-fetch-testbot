"""
handlers/trade.py - Trading Commands
/snipe, /fetch, /sell, /positions with MORK holder gates and safety
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from wallet import get_wallet, get_private_key
from jupiter_engine import safe_swap_via_jupiter, _get_sol_balance, _get_token_balance
from discovery import find_routable_tokens, get_working_token, is_bonded_and_routable
from risk import comprehensive_safety_check, check_safe_mode
from spl.token.instructions import get_associated_token_address
from solders.pubkey import Pubkey

logger = logging.getLogger(__name__)

# MORK token mint (replace with actual MORK mint)
MORK_MINT = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"

def check_mork_holdings(pubkey: str, min_sol_worth: float) -> tuple[bool, str]:
    """
    Check if user holds enough MORK tokens (simplified for now)
    Returns (has_enough, message)
    """
    try:
        # For MVP, we'll simulate MORK check
        # TODO: Implement actual MORK balance check and price conversion
        
        # Get MORK token balance
        mork_mint = Pubkey.from_string(MORK_MINT)
        wallet_pubkey = Pubkey.from_string(pubkey)
        mork_ata = get_associated_token_address(wallet_pubkey, mork_mint)
        
        mork_balance = _get_token_balance(str(mork_ata))
        
        if mork_balance > 1000000:  # Simplified check - 1M+ MORK tokens
            return True, f"MORK requirement satisfied"
        else:
            return False, f"Need {min_sol_worth} SOL worth of MORK tokens to use this feature. Current: {mork_balance:,} MORK"
            
    except Exception as e:
        logger.warning(f"MORK check failed: {e}")
        # For development, allow bypass
        return True, "MORK check bypassed (development mode)"

async def snipe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual token snipe: /snipe <mint> <sol_amount>"""
    chat_id = str(update.effective_chat.id)
    
    # Check arguments
    if len(context.args) < 2:
        await update.message.reply_text(
            "**Usage:** `/snipe <mint> <sol_amount>`\n\n"
            "**Example:** `/snipe 7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump 0.05`\n\n"
            "Buys the specified token if it's bonded and routable.",
            parse_mode='Markdown'
        )
        return
    
    mint = context.args[0]
    try:
        sol_amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Invalid SOL amount. Use decimal format (e.g., 0.05)")
        return
    
    # Check wallet
    wallet = get_wallet(chat_id)
    if not wallet:
        await update.message.reply_text("❌ No wallet linked. Use /linkwallet first.")
        return
    
    pubkey = wallet['pubkey']
    
    # Check MORK holdings
    mork_ok, mork_msg = check_mork_holdings(pubkey, 0.1)  # 0.1 SOL worth for snipe
    if not mork_ok:
        await update.message.reply_text(f"🚫 **MORK Holder Gate**\n\n{mork_msg}")
        return
    
    # Safety checks
    safety_ok, safety_msg = comprehensive_safety_check(pubkey, mint, sol_amount)
    if not safety_ok:
        await update.message.reply_text(f"🚫 **Safety Check Failed**\n\n{safety_msg}")
        return
    
    # Check if token is bonded and routable
    await update.message.reply_text("🔍 Checking if token is bonded and routable...")
    
    is_routable, route_msg = is_bonded_and_routable(mint)
    if not is_routable:
        await update.message.reply_text(
            f"❌ **Not Bonded/Routable**\n\n{route_msg}\n\n"
            f"Token needs to be bonded on Raydium or have Jupiter liquidity to trade."
        )
        return
    
    # Execute trade
    await update.message.reply_text(f"💰 Buying {sol_amount} SOL worth...\n\n{route_msg}")
    
    private_key = get_private_key(chat_id)
    if not private_key:
        await update.message.reply_text("❌ Could not access wallet private key")
        return
    
    # Execute swap via Jupiter
    result = safe_swap_via_jupiter(
        private_key_b58=private_key,
        output_mint_str=mint,
        amount_in_sol=sol_amount,
        slippage_bps=150,
        min_post_delta_raw=1
    )
    
    if result["success"]:
        tokens_received = result["delta_raw"]
        signature = result["signature"]
        
        success_msg = f"""✅ **SNIPE SUCCESSFUL**

💰 **SOL Spent:** {sol_amount} SOL
🪙 **Tokens Received:** {tokens_received:,}
📊 **Entry Price:** {sol_amount / tokens_received:.12f} SOL per token

🔗 **Transaction:** `{signature}`
🔍 **Explorer:** https://solscan.io/tx/{signature}

Position is now active! Use /positions to view all holdings."""

        await update.message.reply_text(success_msg, parse_mode='Markdown')
        
        # TODO: Log trade to database
        logger.info(f"Snipe success: {chat_id} bought {tokens_received:,} tokens for {sol_amount} SOL")
        
    else:
        error_msg = f"""❌ **SNIPE FAILED**

**Error:** {result['error']}

If the issue persists, the token may not have sufficient liquidity or may not be properly bonded."""

        await update.message.reply_text(error_msg, parse_mode='Markdown')
        logger.error(f"Snipe failed: {chat_id} - {result['error']}")

async def fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-discover and buy token: /fetch"""
    chat_id = str(update.effective_chat.id)
    
    # Check wallet
    wallet = get_wallet(chat_id)
    if not wallet:
        await update.message.reply_text("❌ No wallet linked. Use /linkwallet first.")
        return
    
    pubkey = wallet['pubkey']
    
    # Check MORK holdings
    mork_ok, mork_msg = check_mork_holdings(pubkey, 1.0)  # 1.0 SOL worth for fetch
    if not mork_ok:
        await update.message.reply_text(f"🚫 **VIP MORK Holder Gate**\n\n{mork_msg}")
        return
    
    # Default fetch amount
    sol_amount = 0.05
    
    # Safety checks
    safety_ok, safety_msg = comprehensive_safety_check(pubkey, "pending", sol_amount)
    if not safety_ok:
        await update.message.reply_text(f"🚫 **Safety Check Failed**\n\n{safety_msg}")
        return
    
    # Discover routable tokens
    await update.message.reply_text("🔍 Discovering routable tokens from Pump.fun...")
    
    token = get_working_token()
    if not token:
        await update.message.reply_text(
            "❌ **No Routable Tokens Found**\n\n"
            "No tokens from recent Pump.fun launches are currently bonded and routable. "
            "Try again in a few minutes."
        )
        return
    
    mint = token['mint']
    symbol = token['symbol']
    name = token['name']
    
    await update.message.reply_text(
        f"✅ **Token Found**\n\n"
        f"**Name:** {name}\n"
        f"**Symbol:** {symbol}\n"
        f"**Mint:** `{mint}`\n"
        f"**Status:** {token.get('route_reason', 'Routable')}\n\n"
        f"💰 Buying {sol_amount} SOL worth..."
    )
    
    # Execute trade
    private_key = get_private_key(chat_id)
    if not private_key:
        await update.message.reply_text("❌ Could not access wallet private key")
        return
    
    result = safe_swap_via_jupiter(
        private_key_b58=private_key,
        output_mint_str=mint,
        amount_in_sol=sol_amount,
        slippage_bps=150,
        min_post_delta_raw=1
    )
    
    if result["success"]:
        tokens_received = result["delta_raw"]
        signature = result["signature"]
        
        success_msg = f"""✅ **F.E.T.C.H SUCCESSFUL**

🏷️ **{name} ({symbol})**

💰 **SOL Spent:** {sol_amount} SOL
🪙 **Tokens Received:** {tokens_received:,}
📊 **Entry Price:** {sol_amount / tokens_received:.12f} SOL per token

🔗 **Transaction:** `{signature}`
🔍 **Explorer:** https://solscan.io/tx/{signature}

🐕 Mork fetched you a winner! Position is now active."""

        await update.message.reply_text(success_msg, parse_mode='Markdown')
        logger.info(f"Fetch success: {chat_id} bought {symbol} - {tokens_received:,} tokens")
        
    else:
        error_msg = f"""❌ **F.E.T.C.H FAILED**

**Token:** {symbol}
**Error:** {result['error']}

Will try again on next /fetch command."""

        await update.message.reply_text(error_msg, parse_mode='Markdown')
        logger.error(f"Fetch failed: {chat_id} - {result['error']}")

async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's token positions"""
    chat_id = str(update.effective_chat.id)
    
    # Check wallet
    wallet = get_wallet(chat_id)
    if not wallet:
        await update.message.reply_text("❌ No wallet linked. Use /linkwallet first.")
        return
    
    pubkey = wallet['pubkey']
    
    await update.message.reply_text("📊 Loading your positions...")
    
    try:
        # Get SOL balance
        sol_balance = _get_sol_balance(pubkey)
        
        positions_text = [f"💰 **Your Portfolio**\n"]
        positions_text.append(f"**SOL Balance:** {sol_balance:.6f} SOL\n")
        
        # TODO: Get token positions from database or scan wallet
        # For now, show placeholder
        positions_text.append("🪙 **Token Positions:**")
        positions_text.append("_Positions tracking coming soon..._")
        positions_text.append("\nUse /snipe or /fetch to build positions!")
        
        await update.message.reply_text("\n".join(positions_text), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Positions command failed: {e}")
        await update.message.reply_text("❌ Failed to load positions. Try again later.")

# Register handlers
def register_trade_handlers(application):
    """Register all trading command handlers"""
    application.add_handler(CommandHandler("snipe", snipe_command))
    application.add_handler(CommandHandler("fetch", fetch_command))
    application.add_handler(CommandHandler("positions", positions_command))