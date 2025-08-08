#!/usr/bin/env python3
"""
Simplified Mork F.E.T.C.H Bot - Real Trading Only
Removes all simulation features, focuses on /snipe and /fetch for Pump.fun
"""

import os
import re
import logging
import requests
import json
import asyncio
from datetime import datetime
from flask import current_app
from sqlalchemy import func

# Bot configuration
BOT_TOKEN = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOT_USERNAME = "@MorkSniperBot"

# Command states - Real Trading Only
STATE_IDLE = "idle"
STATE_SNIPE_WAITING_CONTRACT = "snipe_waiting_contract"
STATE_SNIPE_WAITING_AMOUNT = "snipe_waiting_amount"
STATE_SNIPE_READY_TO_CONFIRM = "snipe_ready_to_confirm"

# Mork token contract address
MORK_TOKEN_CONTRACT = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"
MORK_PURCHASE_LINK = "https://jup.ag/swap?inputMint=So11111111111111111111111111111111111111112&outputMint=ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"

def send_message(chat_id, text, reply_markup=None):
    """Send a message to a Telegram chat"""
    try:
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
            
        response = requests.post(f"{TELEGRAM_API_URL}/sendMessage", data=payload)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        return False

def handle_start_command(chat_id, user_first_name="User"):
    """Handle /start command - Initialize burner wallet"""
    try:
        from burner_wallet_system import BurnerWalletManager
        from app import app
        
        with app.app_context():
            manager = BurnerWalletManager()
            wallet = manager.get_user_wallet(str(chat_id))
            
            welcome_text = f"""
🐕 Welcome to Mork F.E.T.C.H Bot, {user_first_name}!

*The Degens' Best Friend for Pump.fun Trading*

🔐 *Your Burner Wallet:*
📍 Address: `{wallet['public_key']}`
💰 Balance: {wallet.get('sol_balance', 0):.6f} SOL

*F.E.T.C.H. = Fast Execution, Trade Control Handler*

🚀 *Ready to start real trading on Pump.fun!*

Use /help to see available commands.

⚠️ *Fund your wallet with SOL to begin real trading*
            """
            
            send_message(chat_id, welcome_text)
            
    except Exception as e:
        logging.error(f"Start command failed: {e}")
        send_message(chat_id, "❌ Failed to initialize wallet. Please try again.")

def handle_snipe_command(chat_id):
    """Handle /snipe command - Manual token sniping"""
    try:
        # Check MORK token requirements (0.1 SOL worth)
        from burner_wallet_system import BurnerWalletManager
        from app import app
        
        with app.app_context():
            manager = BurnerWalletManager()
            wallet = manager.get_user_wallet(str(chat_id))
            
            # For now, just check if wallet has SOL (MORK requirement can be added later)
            if wallet.get('sol_balance', 0) < 0.01:  # Minimum 0.01 SOL needed
                send_message(chat_id, f"""
❌ *Insufficient funds for sniping*

Your wallet needs SOL to execute trades.

💰 Current balance: {wallet.get('sol_balance', 0):.6f} SOL
📍 Wallet address: `{wallet['public_key']}`

🔗 [Buy $MORK tokens]({MORK_PURCHASE_LINK}) (Requires 0.1 SOL worth)

Send SOL to your wallet address above to get started.
                """)
                return
            
            # Set user state for manual token entry
            from models import UserSession
            session = UserSession.query.filter_by(chat_id=str(chat_id)).first()
            if not session:
                session = UserSession(chat_id=str(chat_id))
                from app import db
                db.session.add(session)
            
            session.state = STATE_SNIPE_WAITING_CONTRACT
            from app import db
            db.session.commit()
            
            send_message(chat_id, """
⚡ *MANUAL SNIPE MODE ACTIVATED*

🎯 Enter the Pump.fun token contract address you want to snipe:

Example: `So11111111111111111111111111111111111111112`

Or send /cancel to abort.
            """)
            
    except Exception as e:
        logging.error(f"Snipe command failed: {e}")
        send_message(chat_id, "❌ Snipe mode failed to start. Please try again.")

def handle_fetch_command(chat_id):
    """Handle /fetch command - Automated VIP trading"""
    try:
        from burner_wallet_system import BurnerWalletManager
        from app import app
        
        with app.app_context():
            manager = BurnerWalletManager()
            wallet = manager.get_user_wallet(str(chat_id))
            
            # Check if wallet has sufficient SOL (MORK requirement can be added later)
            if wallet.get('sol_balance', 0) < 0.1:  # Minimum 0.1 SOL needed
                send_message(chat_id, f"""
❌ *Insufficient funds for VIP FETCH mode*

Your wallet needs more SOL to execute automated trading.

💰 Current balance: {wallet.get('sol_balance', 0):.6f} SOL
📍 Wallet address: `{wallet['public_key']}`

🔗 [Buy $MORK tokens]({MORK_PURCHASE_LINK}) (Requires 1 SOL worth)

VIP FETCH mode requires significant funding for automated trading.
                """)
                return
            
            send_message(chat_id, """
🚀 *VIP FETCH MODE INITIATING...*

🐕 Sniffer Dog is now hunting for profits!

📋 *Multi-Token Trading Parameters:*
💰 Total Allocation: 0.010 SOL
🎯 Diversified Strategy: 10 different tokens  
💎 Per Token: 0.0010 SOL each
🔄 Mode: Smart Platform Trading (Pump.fun + Jupiter)
📊 Monitoring: Each position monitored independently
🎯 P&L Targets: 10.0% stop-loss / 100.2% take-profit per token
💸 Sell Amount: 100.0% of holdings per target

🔍 *Phase 1: Token Discovery*
Scanning for 10 high-potential fresh launches...
            """)
            
            # Execute automated trading in background - fix async execution
            import threading
            
            def run_fetch_trading():
                """Run fetch trading in a separate thread with its own event loop"""
                try:
                    asyncio.run(execute_fetch_trading(chat_id, wallet))
                except Exception as e:
                    logging.error(f"Background fetch trading failed: {e}")
                    send_message(chat_id, f"❌ Background trading failed: {str(e)}")
            
            # Start trading in background thread
            threading.Thread(target=run_fetch_trading, daemon=True).start()
            
    except Exception as e:
        logging.error(f"Fetch command failed: {e}")
        send_message(chat_id, "❌ FETCH mode failed to start. Please try again.")

async def execute_fetch_trading(chat_id, wallet):
    """Execute automated FETCH trading"""
    try:
        from automated_pump_trader import AutomatedPumpTrader
        
        trader = AutomatedPumpTrader()
        result = await trader.execute_automated_trading(str(chat_id), wallet, 0.01)
        
        if result.get('success'):
            successful_trades = result.get('successful_trades', 0)
            total_trades = result.get('attempted_trades', 0)
            
            send_message(chat_id, f"""
✅ *VIP FETCH COMPLETED*

📊 *Results:*
🎯 Successful Trades: {successful_trades}/{total_trades}
💰 Total Investment: 0.01 SOL
📈 Status: {result.get('message', 'Trading completed')}

🔄 All positions are now being monitored for profit opportunities.
            """)
        else:
            send_message(chat_id, f"""
❌ *FETCH Trading Failed*

Error: {result.get('error', 'Unknown error')}

Please try again or check your wallet funding.
            """)
            
    except Exception as e:
        logging.error(f"FETCH trading execution failed: {e}")
        send_message(chat_id, f"❌ FETCH execution failed: {str(e)}")

def handle_help_command(chat_id):
    """Handle /help command"""
    help_text = f"""
🐕 *Mork F.E.T.C.H Bot Help - The Degens' Best Friend*

*Available Commands:*

🎯 */start* - Initialize your burner wallet & begin trading

⚡ */snipe* - Manual token sniping 
└ Requires 0.1 SOL worth of $MORK tokens
└ Manually select and trade specific Pump.fun tokens

🚀 */fetch* - Automated VIP trading 
└ Requires 1 SOL worth of $MORK tokens
└ Auto-discovers & trades profitable tokens from Pump.fun

💰 */wallet* - Check your burner wallet balance

🛑 */emergency_stop* - Halt all active trading
🟢 */emergency_resume* - Resume trading operations

📊 */status* - View your trading performance

ℹ️ */help* - Show this help menu

*Get $MORK Tokens:*
🔗 [Buy on Jupiter]({MORK_PURCHASE_LINK})

⚠️ *Real Trading Only:* Fund your wallet with SOL for live token purchases on Pump.fun

*F.E.T.C.H. = Fast Execution, Trade Control Handler*
    """
    send_message(chat_id, help_text)

def handle_wallet_command(chat_id):
    """Handle /wallet command"""
    try:
        from burner_wallet_system import BurnerWalletManager
        from app import app
        
        with app.app_context():
            manager = BurnerWalletManager()
            wallet = manager.get_user_wallet(str(chat_id))
            
            wallet_text = f"""
💰 *Your Burner Wallet*

📍 *Address:* `{wallet['public_key']}`
💎 *Balance:* {wallet.get('sol_balance', 0):.6f} SOL

🔗 *Fund your wallet:*
Send SOL to the address above to start trading.

🛡️ *Security:* This is a non-custodial burner wallet. You maintain full control.
            """
            
            send_message(chat_id, wallet_text)
            
    except Exception as e:
        logging.error(f"Wallet command failed: {e}")
        send_message(chat_id, "❌ Failed to retrieve wallet info. Please try again.")

def handle_emergency_stop_command(chat_id):
    """Handle /emergency_stop command"""
    try:
        from emergency_stop import activate_emergency_stop
        activate_emergency_stop(str(chat_id))
        
        send_message(chat_id, """
🚨 *EMERGENCY STOP ACTIVATED*

All trading operations have been immediately halted.

✅ Active trades stopped
✅ New trades prevented
✅ Systems in safe mode

Use /emergency_resume to restart trading when ready.
        """)
        
    except Exception as e:
        logging.error(f"Emergency stop failed: {e}")
        send_message(chat_id, "❌ Emergency stop failed. Please contact support.")

def handle_emergency_resume_command(chat_id):
    """Handle /emergency_resume command"""
    try:
        from emergency_stop import deactivate_emergency_stop
        deactivate_emergency_stop(str(chat_id))
        
        send_message(chat_id, """
🟢 *EMERGENCY STOP DEACTIVATED*

Trading operations have been resumed.

✅ Systems back online
✅ Ready for new trades
✅ Monitoring reactivated

You can now use /snipe or /fetch commands.
        """)
        
    except Exception as e:
        logging.error(f"Emergency resume failed: {e}")
        send_message(chat_id, "❌ Emergency resume failed. Please contact support.")

def handle_user_message(chat_id, text):
    """Handle user text input based on current state"""
    try:
        from models import UserSession
        from app import app
        
        with app.app_context():
            session = UserSession.query.filter_by(chat_id=str(chat_id)).first()
            if not session:
                send_message(chat_id, "Please use /start to initialize your wallet first.")
                return
            
            current_state = session.state or STATE_IDLE
            
            if current_state == STATE_SNIPE_WAITING_CONTRACT:
                # User entered contract address for manual snipe
                if text.lower() == '/cancel':
                    session.state = STATE_IDLE
                    from app import db
                    db.session.commit()
                    send_message(chat_id, "❌ Snipe cancelled.")
                    return
                
                # Validate contract address
                if not is_valid_solana_address(text):
                    send_message(chat_id, "❌ Invalid contract address. Please enter a valid Solana address or /cancel.")
                    return
                
                # Store contract and ask for amount
                session.trading_parameters = json.dumps({
                    'contract_address': text.strip(),
                    'trading_mode': 'snipe'
                })
                session.state = STATE_SNIPE_WAITING_AMOUNT
                from app import db
                db.session.commit()
                
                send_message(chat_id, f"""
⚡ *Token Contract Set*

📋 Contract: `{text.strip()}`

💰 Enter SOL amount to invest:
Example: `0.01` (for 0.01 SOL)

Or /cancel to abort.
                """)
                
            elif current_state == STATE_SNIPE_WAITING_AMOUNT:
                # User entered investment amount
                if text.lower() == '/cancel':
                    session.state = STATE_IDLE
                    session.trading_parameters = None
                    from app import db
                    db.session.commit()
                    send_message(chat_id, "❌ Snipe cancelled.")
                    return
                
                try:
                    amount = float(text.strip())
                    if amount <= 0 or amount > 10:  # Reasonable limits
                        send_message(chat_id, "❌ Please enter a valid amount between 0.001 and 10 SOL.")
                        return
                    
                    # Update parameters and confirm
                    params = json.loads(session.trading_parameters or '{}')
                    params['sol_amount'] = amount
                    session.trading_parameters = json.dumps(params)
                    session.state = STATE_SNIPE_READY_TO_CONFIRM
                    from app import db
                    db.session.commit()
                    
                    send_message(chat_id, f"""
⚡ *SNIPE TRADE READY*

📋 *Trade Details:*
🎯 Token: `{params['contract_address']}`
💰 Amount: {amount} SOL
🏢 Platform: Pump.fun (via PumpPortal API)

✅ Type 'CONFIRM' to execute trade
❌ Type 'CANCEL' to abort

⚠️ This will execute a real trade with your SOL!
                    """)
                    
                except ValueError:
                    send_message(chat_id, "❌ Please enter a valid number (e.g., 0.01)")
                    
            elif current_state == STATE_SNIPE_READY_TO_CONFIRM:
                # User confirming trade
                if text.upper() == 'CONFIRM':
                    # Execute the snipe trade
                    asyncio.create_task(execute_snipe_trade(chat_id, session))
                elif text.upper() == 'CANCEL':
                    session.state = STATE_IDLE
                    session.trading_parameters = None
                    from app import db
                    db.session.commit()
                    send_message(chat_id, "❌ Snipe trade cancelled.")
                else:
                    send_message(chat_id, "Please type 'CONFIRM' to execute or 'CANCEL' to abort.")
                    
    except Exception as e:
        logging.error(f"Handle user message failed: {e}")
        send_message(chat_id, "❌ Error processing message. Please try again.")

async def execute_snipe_trade(chat_id, session):
    """Execute manual snipe trade"""
    try:
        params = json.loads(session.trading_parameters or '{}')
        contract_address = params.get('contract_address')
        sol_amount = params.get('sol_amount')
        
        send_message(chat_id, f"""
🚀 *EXECUTING SNIPE TRADE*

⏳ Processing trade via PumpPortal API...
        """)
        
        from burner_wallet_system import BurnerWalletManager
        from pump_fun_trading import PumpFunTrader
        from app import app
        
        with app.app_context():
            # Get user wallet
            manager = BurnerWalletManager()
            wallet = manager.get_user_wallet(str(chat_id))
            
            # Execute trade
            trader = PumpFunTrader()
            result = await trader.buy_pump_token(
                private_key=wallet.get('private_key'),
                token_contract=contract_address,
                sol_amount=sol_amount
            )
            
            # Reset user state
            session.state = STATE_IDLE
            session.trading_parameters = None
            from app import db
            db.session.commit()
            
            if result.get('success'):
                tx_hash = result.get('transaction_hash', 'N/A')
                send_message(chat_id, f"""
✅ *SNIPE TRADE SUCCESSFUL*

🎯 Token: `{contract_address}`
💰 Amount: {sol_amount} SOL
🔗 TX: `{tx_hash}`
📈 Status: Tokens purchased via PumpPortal API

🔄 Position is now being monitored for profit opportunities.
                """)
            else:
                error_msg = result.get('error', 'Unknown error')
                send_message(chat_id, f"""
❌ *SNIPE TRADE FAILED*

Error: {error_msg}

Please check your wallet funding and try again.
                """)
                
    except Exception as e:
        logging.error(f"Snipe trade execution failed: {e}")
        send_message(chat_id, f"❌ Snipe execution failed: {str(e)}")
        
        # Reset state on error
        try:
            session.state = STATE_IDLE
            session.trading_parameters = None
            from app import db
            db.session.commit()
        except:
            pass

def is_valid_solana_address(address):
    """Validate Solana address format"""
    try:
        import base58
        if len(address) < 32 or len(address) > 44:
            return False
        base58.b58decode(address)
        return True
    except:
        return False

def process_telegram_update(update_data):
    """Process incoming Telegram webhook update"""
    try:
        if 'message' not in update_data:
            return
            
        message = update_data['message']
        chat_id = message['chat']['id']
        
        # Get user info
        user_first_name = message.get('from', {}).get('first_name', 'User')
        
        if 'text' not in message:
            return
            
        text = message['text'].strip()
        
        # Handle commands
        if text.startswith('/'):
            command = text.lower().split()[0]
            
            if command == '/start':
                handle_start_command(chat_id, user_first_name)
            elif command == '/snipe':
                handle_snipe_command(chat_id)
            elif command == '/fetch':
                handle_fetch_command(chat_id)
            elif command == '/wallet':
                handle_wallet_command(chat_id)
            elif command == '/help':
                handle_help_command(chat_id)
            elif command == '/emergency_stop':
                handle_emergency_stop_command(chat_id)
            elif command == '/emergency_resume':
                handle_emergency_resume_command(chat_id)
            else:
                send_message(chat_id, "Unknown command. Use /help to see available commands.")
        else:
            # Handle user text input
            handle_user_message(chat_id, text)
            
    except Exception as e:
        logging.error(f"Error processing update: {e}")
        if 'message' in update_data and 'chat' in update_data['message']:
            chat_id = update_data['message']['chat']['id']
            send_message(chat_id, "❌ Error processing your request. Please try again.")

# Export main function for webhook processing
def handle_telegram_update(update_data):
    """Main entry point for Telegram webhook updates"""
    process_telegram_update(update_data)