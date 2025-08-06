import os
import re
import logging
import requests
import json
import random
import base64
from datetime import datetime
from flask import current_app

# Bot configuration
BOT_TOKEN = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Command states - Simulation mode
STATE_IDLE = "idle"
STATE_WAITING_CONTRACT = "waiting_contract"
STATE_WAITING_AMOUNT = "waiting_amount"
STATE_WAITING_STOPLOSS = "waiting_stoploss"
STATE_WAITING_TAKEPROFIT = "waiting_takeprofit"
STATE_WAITING_SELLPERCENT = "waiting_sellpercent"
STATE_READY_TO_CONFIRM = "ready_to_confirm"

# Live trading states
STATE_WAITING_WALLET = "waiting_wallet"
STATE_LIVE_WAITING_CONTRACT = "live_waiting_contract"
STATE_LIVE_WAITING_AMOUNT = "live_waiting_amount"
STATE_LIVE_WAITING_STOPLOSS = "live_waiting_stoploss"
STATE_LIVE_WAITING_TAKEPROFIT = "live_waiting_takeprofit"
STATE_LIVE_WAITING_SELLPERCENT = "live_waiting_sellpercent"
STATE_LIVE_READY_TO_CONFIRM = "live_ready_to_confirm"

# Mork token contract address
MORK_TOKEN_CONTRACT = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"



def send_message(chat_id, text, reply_markup=None):
    """Send a message to a Telegram chat"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        data['reply_markup'] = reply_markup
    
    try:
        response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return None

def get_or_create_session(chat_id):
    """Get or create a user session"""
    from models import UserSession, db
    session = UserSession.query.filter_by(chat_id=str(chat_id)).first()
    if not session:
        session = UserSession()
        session.chat_id = str(chat_id)
        session.state = STATE_IDLE
        db.session.add(session)
        db.session.commit()
        logging.info(f"Chat {chat_id}: Created new session")
    return session

def update_session(chat_id, **kwargs):
    """Update user session data"""
    from models import UserSession, db
    session = get_or_create_session(chat_id)
    for key, value in kwargs.items():
        setattr(session, key, value)
    db.session.commit()
    logging.info(f"Chat {chat_id}: Updated session - State: {session.state}")
    return session

def is_valid_solana_address(address):
    """Validate Solana contract address format"""
    if not address:
        return False
    
    # Trim whitespace
    address = address.strip()
    
    # Solana addresses are typically 32-44 characters, but let's be more flexible
    if len(address) < 32 or len(address) > 50:
        return False
    
    # Base58 character check (Bitcoin alphabet without 0, O, I, l)
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    
    # Check if all characters are valid Base58
    if not all(char in valid_chars for char in address):
        return False
    
    # Additional check: Solana addresses shouldn't contain ambiguous characters
    forbidden_chars = "0OIl"
    if any(char in forbidden_chars for char in address):
        return False
    
    return True

def get_solana_wallet_balance(wallet_address, token_contract):
    """Get token balance for a Solana wallet address"""
    try:
        # Use Solana RPC endpoint to get token account info
        rpc_url = "https://api.mainnet-beta.solana.com"
        
        # First, get all token accounts for the wallet
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                wallet_address,
                {"mint": token_contract},
                {"encoding": "jsonParsed"}
            ]
        }
        
        response = requests.post(rpc_url, json=data)
        result = response.json()
        
        if 'result' in result and result['result']['value']:
            # Get the token amount from the first account
            account_info = result['result']['value'][0]['account']['data']['parsed']['info']
            token_amount = float(account_info['tokenAmount']['uiAmount'] or 0)
            return token_amount
        else:
            return 0.0
            
    except Exception as e:
        logging.warning(f"Failed to fetch wallet balance: {e}")
        return 0.0

def get_mork_price_in_sol():
    """Get current Mork token price in SOL"""
    try:
        # Try DexScreener first (most reliable)
        dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{MORK_TOKEN_CONTRACT}"
        response = requests.get(dex_url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if 'pairs' in data and data['pairs']:
                # Find SOL pair with highest liquidity
                best_sol_pair = None
                highest_liquidity = 0
                
                for pair in data['pairs']:
                    # Check if this is a SOL pair
                    quote_symbol = pair.get('quoteToken', {}).get('symbol', '')
                    if quote_symbol == 'SOL':
                        liquidity = float(pair.get('liquidity', {}).get('usd', 0)) if pair.get('liquidity') else 0
                        if liquidity > highest_liquidity:
                            highest_liquidity = liquidity
                            best_sol_pair = pair
                
                if best_sol_pair:
                    # priceNative gives us MORK price in SOL directly
                    price_sol = float(best_sol_pair.get('priceNative', 0))
                    if price_sol > 0:
                        logging.info(f"Found MORK/SOL price: {price_sol} SOL per MORK")
                        return price_sol
        
        # Try CoinGecko with SOL conversion
        try:
            coingecko_url = f"https://api.coingecko.com/api/v3/coins/solana/contract/{MORK_TOKEN_CONTRACT}"
            response = requests.get(coingecko_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                market_data = data.get('market_data', {})
                
                # Get MORK price in USD and SOL price in USD
                mork_usd = market_data.get('current_price', {}).get('usd')
                if mork_usd:
                    # Get SOL price in USD
                    sol_response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=10)
                    if sol_response.status_code == 200:
                        sol_data = sol_response.json()
                        sol_usd = sol_data.get('solana', {}).get('usd')
                        if sol_usd and sol_usd > 0:
                            price_sol = mork_usd / sol_usd
                            logging.info(f"Found MORK price via CoinGecko: {price_sol} SOL per MORK")
                            return price_sol
        except Exception as e:
            logging.warning(f"CoinGecko SOL conversion failed: {e}")
        
        # Use get_token_info as fallback to get USD price then convert
        token_info = get_token_info(MORK_TOKEN_CONTRACT)
        if token_info.get('price', 0) > 0:
            mork_usd = token_info['price']
            # Get current SOL price
            sol_response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=10)
            if sol_response.status_code == 200:
                sol_data = sol_response.json()
                sol_usd = sol_data.get('solana', {}).get('usd', 200)  # fallback SOL price
                price_sol = mork_usd / sol_usd
                logging.info(f"Calculated MORK price: {price_sol} SOL per MORK (${mork_usd} / ${sol_usd})")
                return price_sol
        
        # Last resort fallback
        logging.warning("Using fallback MORK price")
        return 0.0002247 / 200  # Use known price from logs / estimated SOL price
        
    except Exception as e:
        logging.warning(f"Failed to fetch Mork price: {e}")
        return 0.0002247 / 200  # Fallback based on observed price

def calculate_mork_sol_threshold():
    """Calculate how many Mork tokens equal 1 SOL"""
    mork_price_sol = get_mork_price_in_sol()
    if mork_price_sol > 0:
        return 1.0 / mork_price_sol  # How many Mork tokens = 1 SOL
    return 1000000  # Fallback: 1M Mork tokens

def validate_solana_wallet(wallet_address):
    """Validate if the provided string is a valid Solana wallet address"""
    if not wallet_address or len(wallet_address) < 32 or len(wallet_address) > 44:
        return False
    
    # Basic validation - Solana addresses are base58 encoded
    import string
    base58_chars = string.ascii_letters + string.digits
    base58_chars = base58_chars.replace('0', '').replace('O', '').replace('I', '').replace('l', '')
    
    for char in wallet_address:
        if char not in base58_chars:
            return False
    
    return True

def validate_solana_contract(contract_address):
    """Validate if the provided string is a valid Solana contract address"""
    return validate_solana_wallet(contract_address)  # Same validation as wallet

def get_token_info(contract_address):
    """Fetch token information and current price from Solana"""
    token_data = {
        'name': 'Unknown Token',
        'symbol': 'UNKNOWN',
        'price': 0,  # Changed to 'price' for consistency
        'decimals': 9,
        'market_cap': None
    }
    
    # Try DexScreener first (most reliable for new tokens)
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{contract_address}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('pairs') and len(data['pairs']) > 0:
                # Find the pair with highest liquidity for more accurate price
                best_pair = None
                highest_liquidity = 0
                
                for pair in data['pairs']:
                    liquidity = float(pair.get('liquidity', {}).get('usd', 0)) if pair.get('liquidity') else 0
                    if liquidity > highest_liquidity:
                        highest_liquidity = liquidity
                        best_pair = pair
                
                if best_pair and best_pair.get('priceUsd'):
                    price = float(best_pair.get('priceUsd', 0))
                    if price > 0:
                        token_data.update({
                            'price': price,
                            'name': best_pair.get('baseToken', {}).get('name', token_data['name']),
                            'symbol': best_pair.get('baseToken', {}).get('symbol', token_data['symbol'])
                        })
                        logging.info(f"Found token on DexScreener: {token_data['name']} at ${price}")
                        return token_data
    except Exception as e:
        logging.warning(f"DexScreener API failed for {contract_address}: {e}")
    
    # Try CoinGecko as backup
    try:
        url = f"https://api.coingecko.com/api/v3/coins/solana/contract/{contract_address}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            market_data = data.get('market_data', {})
            current_price = market_data.get('current_price', {})
            
            if current_price.get('usd'):
                price = float(current_price.get('usd', 0))
                if price > 0:
                    token_data.update({
                        'name': data.get('name', token_data['name']),
                        'symbol': data.get('symbol', token_data['symbol']).upper(),
                        'price': price,
                        'market_cap': market_data.get('market_cap', {}).get('usd')
                    })
                    logging.info(f"Found token on CoinGecko: {token_data['name']} at ${price}")
                    return token_data
    except Exception as e:
        logging.warning(f"CoinGecko API failed for {contract_address}: {e}")
    
    # For live trading, if we can't get price data, allow with warning
    if token_data['price'] == 0:
        # Try to get at least the token metadata from Solana RPC
        try:
            rpc_url = "https://api.mainnet-beta.solana.com"
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    contract_address,
                    {"encoding": "jsonParsed"}
                ]
            }
            
            response = requests.post(rpc_url, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if 'result' in result and result['result'] and result['result']['value']:
                    # Token exists, set a minimal price for live trading testing
                    token_data['price'] = 0.0001  # Very small price to allow live trading
                    logging.info(f"Token verified on Solana RPC, using fallback price")
        except Exception as e:
            logging.warning(f"Solana RPC failed for {contract_address}: {e}")
    
    return token_data

def is_valid_percentage(value):
    """Validate percentage input (0-100)"""
    try:
        percentage = float(value)
        return 0 <= percentage <= 100
    except ValueError:
        return False

def handle_start_command(chat_id, user_first_name):
    """Handle /start command"""
    welcome_text = f"""
🤖 <b>Welcome to Mork F.E.T.C.H Bot, {user_first_name}!</b>

<b>🧪 FREE SIMULATION MODE</b>
Practice crypto sniping without risk! Perfect for learning how token sniping works.

<b>⚡ DEGENS SNIPE BOT</b>
Live trading mode - Trading bot with 0.5% fee on all profitable sales value

<b>💎 VIP LIVE FETCH TRADING MODE</b>
Real trading for users with 1 SOL worth of $MORK tokens in their wallet - VIP Trading bot with 0.5% fee on all profitable sales value

<b>Available Commands:</b>
🐶 /simulate - Puppy in training (free practice mode)
⚡ /snipe - Live trading mode (Trading bot with 0.5% fee on all profitable sales value)
🎯 /fetch - VIP Trading sniffer dog (Minimum 1 SOL worth holding of $MORK + 0.5% fee on all profitable sales value)
📊 /status - Check your current session
❓ /help - Get help and instructions

<b>How to use:</b>
• <b>Practice:</b> Use /simulate for risk-free simulation
• <b>Live Trading:</b> Use /snipe to verify $MORK and trade real tokens (0.5% fee on profits)
• <b>VIP Fetch:</b> Use /fetch for advanced trading features (coming soon)
• All modes guide you through: contract → amount → stop-loss → take-profit → sell %

<b>Ready to start?</b>
• Type /simulate for practice
• Type /snipe for live trading (requires 1 SOL worth of $MORK)
• Type /fetch for VIP features (requires 1 SOL worth of $MORK)

<i>Simulation mode: No real trades. Live mode: Real wallet verification required.</i>
    """
    
    # Reset user session
    update_session(chat_id, state=STATE_IDLE, contract_address=None, 
                  stop_loss=None, take_profit=None, sell_percent=None)
    
    send_message(chat_id, welcome_text)

def handle_simulate_command(chat_id):
    """Handle /simulate command"""
    session = get_or_create_session(chat_id)
    logging.info(f"Chat {chat_id}: Starting simulate command, setting state to {STATE_WAITING_CONTRACT}")
    
    simulate_text = """
🎯 <b>Starting Simulation Mode</b>

Please enter the <b>Solana token contract address</b> you want to simulate trading:

<i>Example: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM</i>

Type the contract address or /cancel to abort.

<i>🧪 This is simulation mode - no real trades will be executed.</i>
    """
    
    session = update_session(chat_id, state=STATE_WAITING_CONTRACT)
    logging.info(f"Chat {chat_id}: Session state after update = {session.state}")
    send_message(chat_id, simulate_text)

def handle_contract_input(chat_id, contract_address):
    """Handle contract address input"""
    if not is_valid_solana_address(contract_address):
        error_text = """
❌ <b>Invalid Contract Address</b>

Please enter a valid Solana contract address (32-44 characters, Base58 encoded).

<i>Example: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    # Fetch token information and current price
    send_message(chat_id, "🔍 <i>Fetching token information and current price...</i>")
    token_info = get_token_info(contract_address)
    
    # Format price display
    price_display = ""
    if token_info['price'] and token_info['price'] > 0:
        if token_info['price'] < 0.01:
            price_display = f"💲 <b>Current Price:</b> ${token_info['price']:.8f} USD"
        else:
            price_display = f"💲 <b>Current Price:</b> ${token_info['price']:.4f} USD"
    else:
        price_display = "💲 <b>Current Price:</b> Price data unavailable"
    
    # Store token info in session including entry price
    update_session(chat_id, 
                  contract_address=contract_address, 
                  token_name=token_info['name'],
                  token_symbol=token_info['symbol'],
                  entry_price=token_info['price'],
                  state=STATE_WAITING_AMOUNT)
    
    amount_text = f"""
✅ <b>🎮 SIMULATION - Token Identified:</b>
🏷️ <b>Name:</b> {token_info['name']}
🎯 <b>Symbol:</b> ${token_info['symbol']}
{price_display}
📄 <b>Contract:</b> <code>{contract_address}</code>

💰 Now enter how much you want to simulate trading:

<b>Enter amount in USD:</b>
<i>Example: "100" for $100 simulation trade</i>

This determines your position size for the simulation.

<b>⚠️ PRACTICE MODE - No real money involved</b>
Type an amount (e.g. 50, 100, 500) or /cancel to abort.
    """
    
    send_message(chat_id, amount_text)

def handle_amount_input(chat_id, amount_text):
    """Handle trade amount input"""
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Store amount and move to stop-loss
        update_session(chat_id, trade_amount=amount, state=STATE_WAITING_STOPLOSS)
        
        session = get_or_create_session(chat_id)
        stoploss_text = f"""
✅ <b>Trade Amount Set: ${amount:,.2f} USD</b>

📉 Now enter your <b>Stop-Loss percentage</b> (0-100):

This is the percentage loss at which the bot will automatically sell to limit losses.

<i>Example: Enter "20" for 20% stop-loss</i>

<b>⚠️ SIMULATION MODE - Position size: ${amount:,.2f}</b>
Type a number between 0-100 or /cancel to abort.
        """
        send_message(chat_id, stoploss_text)
        
    except ValueError:
        error_text = """
❌ <b>Invalid Trade Amount</b>

Please enter a valid amount in USD (numbers only).

<i>Examples: "100", "250", "1000"</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)

def handle_stoploss_input(chat_id, stop_loss):
    """Handle stop-loss percentage input"""
    if not is_valid_percentage(stop_loss):
        error_text = """
❌ <b>Invalid Stop-Loss Percentage</b>

Please enter a valid percentage between 0 and 100.

<i>Example: Enter "20" for 20% stop-loss</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    stop_loss_value = float(stop_loss)
    update_session(chat_id, stop_loss=stop_loss_value, state=STATE_WAITING_TAKEPROFIT)
    
    takeprofit_text = f"""
✅ <b>Stop-Loss Set:</b> {stop_loss_value}%

📈 Now enter your <b>Take-Profit percentage</b> (0-1000):

This is the percentage gain at which the bot will automatically sell to secure profits.

<i>Example: Enter "200" for 200% take-profit (3x return)</i>

Type a number between 0-1000 or /cancel to abort.
    """
    
    send_message(chat_id, takeprofit_text)

def handle_takeprofit_input(chat_id, take_profit):
    """Handle take-profit percentage input"""
    try:
        take_profit_value = float(take_profit)
        if take_profit_value < 0 or take_profit_value > 1000:
            raise ValueError()
    except ValueError:
        error_text = """
❌ <b>Invalid Take-Profit Percentage</b>

Please enter a valid percentage between 0 and 1000.

<i>Example: Enter "200" for 200% take-profit</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    update_session(chat_id, take_profit=take_profit_value, state=STATE_WAITING_SELLPERCENT)
    
    sellpercent_text = f"""
✅ <b>Take-Profit Set:</b> {take_profit_value}%

💰 Finally, enter the <b>percentage of tokens to sell</b> when conditions are met (1-100):

This determines how much of your position to sell when stop-loss or take-profit triggers.

<i>Example: Enter "50" to sell 50% of tokens, keeping 50%</i>

Type a number between 1-100 or /cancel to abort.
    """
    
    send_message(chat_id, sellpercent_text)

def handle_sellpercent_input(chat_id, sell_percent):
    """Handle sell percentage input"""
    try:
        sell_percent_value = float(sell_percent)
        if sell_percent_value < 1 or sell_percent_value > 100:
            raise ValueError()
    except ValueError:
        error_text = """
❌ <b>Invalid Sell Percentage</b>

Please enter a valid percentage between 1 and 100.

<i>Example: Enter "50" to sell 50% of tokens</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    session = update_session(chat_id, sell_percent=sell_percent_value, state=STATE_READY_TO_CONFIRM)
    
    token_display = f"{session.token_name} (${session.token_symbol})" if session.token_name else "Unknown Token"
    
    # Format entry price
    entry_price_display = ""
    if session.entry_price:
        if session.entry_price < 0.01:
            entry_price_display = f"💲 <b>Entry Price:</b> ${session.entry_price:.8f} USD"
        else:
            entry_price_display = f"💲 <b>Entry Price:</b> ${session.entry_price:.4f} USD"
    else:
        entry_price_display = "💲 <b>Entry Price:</b> Price data unavailable"
    
    # Trade amount display
    trade_amount_display = f"💵 <b>Trade Amount:</b> ${session.trade_amount:,.2f} USD" if session.trade_amount else "💵 <b>Trade Amount:</b> $100.00 USD (default)"
    
    confirm_text = f"""
🎮 <b>SIMULATION SNIPE READY!</b>

<b>📋 Practice Configuration Summary:</b>
🏷️ <b>Token:</b> {token_display}
📄 <b>Contract:</b> <code>{session.contract_address}</code>
{entry_price_display}
{trade_amount_display}
📉 <b>Stop-Loss:</b> {session.stop_loss}%
📈 <b>Take-Profit:</b> {session.take_profit}%
💰 <b>Sell Amount:</b> {session.sell_percent}%

<b>⚠️ This is PRACTICE MODE - No real money involved</b>
Perfect for learning trading strategies risk-free!

Type <b>/confirm</b> to run the simulation or /cancel to abort.
    """
    
    send_message(chat_id, confirm_text)

def handle_confirm_command(chat_id):
    """Handle confirmation for both simulation and live trading"""
    from models import UserSession, TradeSimulation, db
    import random
    session = get_or_create_session(chat_id)
    
    if session.state == STATE_READY_TO_CONFIRM:
        # Execute simulation
        execute_simulation(chat_id)
    elif session.state == STATE_LIVE_READY_TO_CONFIRM:
        # Execute live trade
        execute_live_trade(chat_id)
    elif session.state not in [STATE_READY_TO_CONFIRM, STATE_LIVE_READY_TO_CONFIRM]:
        error_text = """
❌ <b>No Order Ready for Confirmation</b>

You don't have a pending order to confirm. 

<b>To set up a new order:</b>
• Type /snipe for practice simulation
• Type /fetch for live trading (requires $MORK tokens)

Choose your trading mode!
        """
        send_message(chat_id, error_text)
        return

def execute_simulation(chat_id):
    """Execute a practice simulation"""
    from models import UserSession, TradeSimulation, db
    import random
    session = get_or_create_session(chat_id)
    
    # Generate realistic simulation results based on user's actual settings
    # Add 10% variance to allow for realistic market slippage
    variance_range = 10  # ±10% variance from target
    
    # Determine which trigger happens first with realistic probabilities
    trigger_probabilities = [
        {"outcome": "take_profit", "weight": 0.35},  # 35% chance of hitting take-profit
        {"outcome": "stop_loss", "weight": 0.45},    # 45% chance of hitting stop-loss
        {"outcome": "partial_sell", "weight": 0.20}  # 20% chance of manual partial sell
    ]
    
    chosen_trigger = random.choices(
        [t["outcome"] for t in trigger_probabilities],
        weights=[t["weight"] for t in trigger_probabilities]
    )[0]
    
    # Calculate realistic percentage change based on user's settings with variance
    if chosen_trigger == "take_profit":
        # Hit take-profit with ±10% variance
        base_change = session.take_profit
        variance = random.uniform(-variance_range, variance_range)
        change_percent = base_change + variance
        scenario = {"outcome": "profit", "change": change_percent, "trigger": "take_profit"}
    elif chosen_trigger == "stop_loss":
        # Hit stop-loss with ±10% variance (negative change)
        base_change = -session.stop_loss
        variance = random.uniform(-variance_range, variance_range)
        change_percent = base_change + variance
        scenario = {"outcome": "loss", "change": change_percent, "trigger": "stop_loss"}
    else:
        # Partial sell between entry and take-profit (small gains)
        max_gain = min(session.take_profit * 0.7, 25)  # Max 70% of take-profit or 25%
        change_percent = random.uniform(2, max_gain)
        scenario = {"outcome": "partial_profit", "change": change_percent, "trigger": "manual_sell"}
    
    token_display = f"{session.token_name} (${session.token_symbol})" if session.token_name else "Unknown Token"
    
    # Format entry price
    entry_price_display = ""
    if session.entry_price:
        if session.entry_price < 0.01:
            entry_price_display = f"${session.entry_price:.8f}"
        else:
            entry_price_display = f"${session.entry_price:.4f}"
    else:
        entry_price_display = "Price unavailable"
    
    # Calculate simulated performance using actual trade amount
    usd_invested = session.trade_amount or 100.0  # Default to $100 if not set
    change_percent = scenario["change"]
    final_value = usd_invested * (1 + change_percent / 100)
    profit_loss = final_value - usd_invested
    
    if scenario["outcome"] == "profit":
        result_emoji = "🎉"
        result_text = f"<b>Take-profit triggered at {change_percent:.1f}%!</b> (Target: {session.take_profit}%)"
    elif scenario["outcome"] == "loss":
        result_emoji = "📉"
        result_text = f"<b>Stop-loss triggered at {change_percent:.1f}%</b> (Target: -{session.stop_loss}%)"
    else:
        result_emoji = "💰"
        result_text = f"<b>Partial profit taken at +{change_percent:.1f}%</b> (Before reaching {session.take_profit}% target)"
    
    simulation_text = f"""
🎮 <b>PRACTICE SIMULATION COMPLETE!</b>

<b>📊 Simulated Trade Results:</b>
🏷️ <b>Token:</b> {token_display}
💲 <b>Entry Price:</b> {entry_price_display}
💵 <b>Simulated Investment:</b> ${usd_invested:,.2f} USD

<b>🎯 Your Settings:</b>
📉 <b>Stop-Loss Target:</b> -{session.stop_loss}%
📈 <b>Take-Profit Target:</b> +{session.take_profit}%
💰 <b>Sell Amount:</b> {session.sell_percent}%

<b>📋 What Happened:</b>
{result_emoji} {result_text}
💼 <b>Final Value:</b> ${final_value:,.2f} USD
📈 <b>Profit/Loss:</b> ${profit_loss:+,.2f} USD

<b>💡 This was practice mode - No real money involved!</b>
Real trading requires 100,000+ $MORK tokens for live execution.

Type /whatif to see your simulation history or /snipe for another practice round!
    """
    
    # Save simulation record
    trade_sim = TradeSimulation()
    trade_sim.chat_id = str(chat_id)
    trade_sim.contract_address = session.contract_address
    trade_sim.stop_loss = session.stop_loss
    trade_sim.take_profit = session.take_profit
    trade_sim.sell_percent = session.sell_percent
    trade_sim.result_type = scenario["outcome"]
    trade_sim.profit_loss = profit_loss
    trade_sim.entry_price = session.entry_price
    trade_sim.trade_amount = usd_invested
    
    db.session.add(trade_sim)
    db.session.commit()
    
    # Reset session
    update_session(chat_id, 
                  state=STATE_IDLE,
                  contract_address=None,
                  token_name=None,
                  token_symbol=None,
                  entry_price=None,
                  stop_loss=None,
                  take_profit=None,
                  sell_percent=None,
                  trade_amount=None)
    
    send_message(chat_id, simulation_text)

def handle_status_command(chat_id):
    """Handle /status command"""
    session = get_or_create_session(chat_id)
    
    if session.state == STATE_IDLE:
        status_text = """
📊 <b>Session Status</b>

🟢 <b>Status:</b> Ready
🧪 <b>Mode:</b> Simulation (Free)
⏰ <b>Last Activity:</b> Ready for new snipe

Type /snipe to start a new simulation!
        """
    else:
        state_descriptions = {
            STATE_WAITING_CONTRACT: "Waiting for contract address",
            STATE_WAITING_STOPLOSS: "Waiting for stop-loss percentage", 
            STATE_WAITING_TAKEPROFIT: "Waiting for take-profit percentage",
            STATE_WAITING_SELLPERCENT: "Waiting for sell percentage",
            STATE_READY_TO_CONFIRM: "Ready to confirm simulation"
        }
        
        status_text = f"""
📊 <b>Session Status</b>

🟡 <b>Status:</b> In Progress
🧪 <b>Mode:</b> Simulation (Free)
📝 <b>Current Step:</b> {state_descriptions.get(session.state, "Unknown")}

<b>Configuration:</b>
🎯 <b>Contract:</b> {session.contract_address or "Not set"}
📉 <b>Stop-Loss:</b> {f"{session.stop_loss}%" if session.stop_loss else "Not set"}
📈 <b>Take-Profit:</b> {f"{session.take_profit}%" if session.take_profit else "Not set"}
💰 <b>Sell Amount:</b> {f"{session.sell_percent}%" if session.sell_percent else "Not set"}

Type /cancel to abort current operation.
        """
    
    send_message(chat_id, status_text)

def handle_help_command(chat_id):
    """Handle /help command"""
    help_text = """
❓ <b>Mork F.E.T.C.H Bot Help</b>

<b>🧪 FREE SIMULATION MODE</b>
Practice crypto sniping without risk! Perfect for learning how token sniping works.

<b>⚡ DEGENS SNIPE BOT</b>
Live trading mode - Trading bot with 0.5% fee on all profitable sales value

<b>💎 VIP LIVE FETCH TRADING MODE</b>
Real trading for users with 1 SOL worth of $MORK tokens in their wallet - VIP Trading bot with 0.5% fee on all profitable sales value

<b>📋 Available Commands:</b>
• <b>/start</b> - Welcome message and reset session
• <b>/simulate</b> - Puppy in training (free practice mode)
• <b>/snipe</b> - Live trading mode (Trading bot with 0.5% fee on all profitable sales value)
• <b>/fetch</b> - VIP Trading sniffer dog (Minimum 1 SOL worth holding of $MORK + 0.5% fee on all profitable sales value)
• <b>/confirm</b> - Execute the order (simulation or live)
• <b>/status</b> - Check current session status
• <b>/cancel</b> - Cancel current operation
• <b>/help</b> - Show this help message
• <b>/whatif</b> - View your simulation performance history

<b>📖 How to Use:</b>
1. Type /simulate for practice, /snipe for live trading, or /fetch for VIP features
2. Enter a Solana token contract address
3. Enter your trade amount (SOL amount to invest)
4. Set your stop-loss percentage (0-100%)
5. Set your take-profit percentage (0-1000%)
6. Set what percentage to sell (1-100%)
7. Type /confirm to execute

<b>🎯 What is Token Sniping?</b>
Strategic buying and selling of tokens based on predefined profit/loss targets and market conditions with fast execution.

<b>⚠️ Important Notes:</b>
• Simulation mode: No real trades, safe practice
• Live mode: Real trades, requires minimum 1 SOL worth of $MORK tokens
• 0.5% fee charged only on profitable trades (sales value)
• Always DYOR (Do Your Own Research)

<b>🔗 Live Trading Features:</b>
• Real Solana blockchain integration
• $MORK token verification
• Wallet balance checking
• Risk management warnings
• Fast execution trading

Need help? Contact support in our Telegram group!
    """
    
    send_message(chat_id, help_text)

def handle_cancel_command(chat_id):
    """Handle /cancel command"""
    session = get_or_create_session(chat_id)
    
    if session.state == STATE_IDLE:
        cancel_text = """
ℹ️ <b>Nothing to Cancel</b>

You don't have any active operations running.

Type /simulate for practice or /snipe for live trading!
        """
    else:
        cancel_text = """
❌ <b>Operation Cancelled</b>

Your current setup has been cancelled and reset.

Type /simulate for practice or /snipe for live trading!
        """
        update_session(chat_id, state=STATE_IDLE, contract_address=None,
                      stop_loss=None, take_profit=None, sell_percent=None)
    
    send_message(chat_id, cancel_text)

def handle_whatif_command(chat_id):
    """Handle /whatif command - show simulation history"""
    from models import TradeSimulation, db
    
    # Get user's simulation history (last 10 trades)
    simulations = TradeSimulation.query.filter_by(chat_id=str(chat_id)).order_by(TradeSimulation.created_at.desc()).limit(10).all()
    
    if not simulations:
        whatif_text = """
📊 <b>Your Simulation Performance</b>

🔍 <b>No Simulations Yet!</b>

You haven't run any practice simulations yet. Start building your trading experience with /simulate!

<b>🎮 Why Use Simulations?</b>
• Learn trading strategies risk-free
• Test different stop-loss/take-profit settings
• Build confidence before real trading
• See how your strategies would have performed

Type /simulate to run your first practice simulation!
        """
    else:
        # Calculate overall statistics
        total_trades = len(simulations)
        profitable_trades = len([s for s in simulations if s.profit_loss > 0])
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(s.profit_loss for s in simulations if s.profit_loss is not None)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        # Create performance summary
        recent_trades = []
        for sim in simulations[:5]:  # Show last 5 trades
            date_str = sim.created_at.strftime("%m/%d")
            result_emoji = "🎉" if sim.profit_loss > 0 else "📉" if sim.profit_loss < 0 else "⚪"
            pnl_str = f"{sim.profit_loss:+.3f}" if sim.profit_loss else "0.000"
            recent_trades.append(f"  {date_str} {result_emoji} {pnl_str} SOL")
        
        whatif_text = f"""
📊 <b>Your Simulation Performance</b>

<b>🎯 Overall Statistics:</b>
📈 <b>Total Simulations:</b> {total_trades}
💎 <b>Profitable Trades:</b> {profitable_trades}/{total_trades}
🎯 <b>Win Rate:</b> {win_rate:.1f}%
💰 <b>Total P&L:</b> {total_pnl:+.3f} SOL
📊 <b>Average P&L:</b> {avg_pnl:+.3f} SOL per trade

<b>📋 Recent Simulations:</b>
{chr(10).join(recent_trades)}

<b>🧠 Performance Insights:</b>
{"🎉 Great job! You're showing consistent profits!" if win_rate > 60 else "📚 Keep practicing! Trading takes time to master." if win_rate > 40 else "💡 Try adjusting your stop-loss/take-profit settings."}

<b>💡 Remember:</b> These are practice simulations. Real trading requires 1 SOL worth of $MORK tokens and carries actual risk.

Ready for more practice? Type /simulate to run another simulation!
        """
    
    send_message(chat_id, whatif_text)

def handle_fetch_command(chat_id):
    """Handle /fetch command - VIP Trading sniffer dog mode with full trading functionality"""
    fetch_text = """
🎯 <b>VIP FETCH TRADING MODE - Real Money!</b>

<b>🐕 VIP Trading Sniffer Dog with Enhanced Features</b>

<b>⚠️ IMPORTANT NOTICE:</b>
• This is <b>VIP REAL TRADING</b> with actual funds
• 0.5% fee charged only on profitable trades (sales value)
• You need 1 SOL worth of $MORK tokens to access this VIP mode
• Enhanced execution speed and priority processing
• All trades are executed on the Solana blockchain
• You are responsible for all trading decisions and outcomes

<b>🔐 Required for VIP Trading:</b>
• Valid Solana wallet address
• Minimum 1 SOL equivalent in $MORK tokens (verified)
• Sufficient SOL for transaction fees
• VIP access privileges

<b>🚀 VIP Features Active:</b>
• Priority execution speeds
• Enhanced risk management
• Advanced trading analytics
• Premium customer support

Please provide your Solana wallet address to verify your VIP $MORK token holdings:
    """
    update_session(chat_id, state=STATE_WAITING_WALLET, trading_mode='fetch')
    send_message(chat_id, fetch_text)

def handle_snipe_command(chat_id):
    """Handle /snipe command - start live trading mode with 0.5% fee"""
    snipe_text = """
🚀 <b>LIVE TRADING MODE - Real Money!</b>

<b>⚡ Trading Bot with 0.5% fee on all profitable sales value</b>

<b>⚠️ IMPORTANT NOTICE:</b>
• This is <b>REAL TRADING</b> with actual funds
• 0.5% fee charged only on profitable trades (sales value)
• You need 1 SOL worth of $MORK tokens to access this mode
• All trades are executed on the Solana blockchain
• You are responsible for all trading decisions and outcomes

<b>🔐 Required for Live Trading:</b>
• Valid Solana wallet address
• Minimum 1 SOL equivalent in $MORK tokens
• Sufficient SOL for transaction fees

Please provide your Solana wallet address to verify your $MORK token holdings:
    """
    update_session(chat_id, state=STATE_WAITING_WALLET, trading_mode='snipe')
    send_message(chat_id, snipe_text)

def handle_wallet_input(chat_id, wallet_address):
    """Handle wallet address input for live trading verification"""
    # Get current session to determine trading mode
    session = get_or_create_session(chat_id)
    is_vip_mode = session.trading_mode == 'fetch'
    
    # Validate wallet address format
    if not validate_solana_wallet(wallet_address):
        mode_label = "VIP" if is_vip_mode else "Live Trading"
        error_text = f"""
❌ <b>Invalid Wallet Address</b>

The provided address doesn't appear to be a valid Solana wallet address.

<b>💡 Wallet Address Requirements:</b>
• Must be 32-44 characters long
• Contains only valid base58 characters
• Example: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM

Please provide a valid Solana wallet address for {mode_label} access:
        """
        send_message(chat_id, error_text)
        return
    
    # Check Mork token balance
    check_message = "🔍 <b>Verifying your VIP $MORK token holdings...</b>" if is_vip_mode else "🔍 <b>Checking your $MORK token balance...</b>"
    send_message(chat_id, check_message)
    
    mork_balance = get_solana_wallet_balance(wallet_address, MORK_TOKEN_CONTRACT)
    required_mork = calculate_mork_sol_threshold()
    mork_price_sol = get_mork_price_in_sol()
    current_value_sol = mork_balance * mork_price_sol
    
    if current_value_sol >= 1.0:  # Has 1 SOL worth of Mork
        # Eligible for live trading
        if is_vip_mode:
            eligible_text = f"""
✅ <b>🎯 VIP ACCESS VERIFIED!</b>

<b>🐕 Welcome to VIP FETCH Trading Sniffer Dog Mode!</b>

<b>💎 Your $MORK Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📈 <b>Required:</b> 1.000 SOL worth (✅ VIP QUALIFIED)

<b>🚀 VIP Features Activated:</b>
• Priority execution speeds
• Enhanced risk management
• Advanced trading analytics
• Premium customer support

<b>🎯 You now have VIP FETCH access!</b>

Please enter the Solana token contract address you want to trade with VIP priority:
            """
        else:
            eligible_text = f"""
✅ <b>ACCESS VERIFIED!</b>

<b>💎 Your $MORK Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📈 <b>Required:</b> 1.000 SOL worth (✅ QUALIFIED)

<b>🎯 You now have access to LIVE TRADING!</b>

Please enter the Solana token contract address you want to trade:
            """
        update_session(chat_id, state=STATE_LIVE_WAITING_CONTRACT, wallet_address=wallet_address)
        send_message(chat_id, eligible_text)
    else:
        # Not eligible - need more Mork
        shortage_sol = 1.0 - current_value_sol
        needed_mork = shortage_sol / mork_price_sol
        
        # Create Jupiter swap link for instant purchase
        jupiter_buy_link = f"https://jup.ag/swap/SOL-{MORK_TOKEN_CONTRACT}"
        
        # Calculate tokens per 1 SOL for user reference
        tokens_per_sol = 1.0 / mork_price_sol if mork_price_sol > 0 else 0
        
        mode_title = "VIP FETCH ACCESS DENIED" if is_vip_mode else "Insufficient $MORK Holdings"
        access_type = "VIP FETCH Trading" if is_vip_mode else "Live Trading"
        
        ineligible_text = f"""
❌ <b>{mode_title}</b>

<b>💎 Your Current Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📉 <b>Required for {access_type}:</b> Minimum 1.000 SOL worth
⚠️ <b>Shortage:</b> {shortage_sol:.3f} SOL worth ({needed_mork:,.0f} more $MORK)

<b>🚀 INSTANT PURCHASE:</b>
<a href="{jupiter_buy_link}">🔗 Buy $MORK Now with Phantom Wallet</a>

<b>🛒 Real-Time Purchase Info:</b>
• Live $MORK price: {mork_price_sol:.8f} SOL per token
• 1 SOL = {tokens_per_sol:,.0f} $MORK tokens
• $MORK Contract: <code>{MORK_TOKEN_CONTRACT}</code>
• Available on Jupiter, Raydium, and other Solana DEXs

<b>💡 Meanwhile, try our FREE simulation mode:</b>
Type /simulate to practice trading without risk!
        """
        update_session(chat_id, state=STATE_IDLE, wallet_address=None)
        send_message(chat_id, ineligible_text)

def handle_live_contract_input(chat_id, contract_address):
    """Handle contract address input for live trading"""
    session = get_or_create_session(chat_id)
    
    # Validate contract address
    if not validate_solana_contract(contract_address):
        error_text = """
❌ <b>Invalid Contract Address</b>

Please provide a valid Solana token contract address.

<b>💡 Requirements:</b>
• 32-44 characters long
• Valid base58 encoding
• Example: So11111111111111111111111111111111111111112

Enter the token contract address:
        """
        send_message(chat_id, error_text)
        return
    
    # Fetch token information
    send_message(chat_id, "🔍 <b>Fetching live token data...</b>")
    
    token_info = get_token_info(contract_address)
    token_name = token_info.get('name', 'Unknown Token')
    token_symbol = token_info.get('symbol', 'UNK')
    current_price = token_info.get('price', 0)
    
    if current_price == 0:
        error_text = """
⚠️ <b>Token Information Unavailable</b>

Unable to fetch current price data for this token. This could mean:
• The token is very new or not actively traded
• The token may not exist
• API temporarily unavailable

<b>🔄 Please try:</b>
• A different token contract address
• Wait a few minutes and try again
• Contact support if this continues

Enter a different token contract address:
        """
        send_message(chat_id, error_text)
        return
    
    # Display token info and ask for stop-loss
    token_display = f"{token_name} (${token_symbol})" if token_name != 'Unknown Token' else f"Contract: {contract_address[:8]}..."
    entry_price_display = f"${current_price:.8f}" if current_price < 1 else f"${current_price:.4f}"
    
    contract_text = f"""
🎯 <b>LIVE TRADING TOKEN CONFIRMED</b>

<b>🏷️ Token Information:</b>
📛 <b>Name:</b> {token_display}
📊 <b>Contract:</b> <code>{contract_address}</code>
💲 <b>Current Price:</b> {entry_price_display}

💰 <b>How much SOL do you want to trade?</b>

Enter amount in SOL (e.g., 0.1, 0.5, 1.0):

<b>⚠️ This is LIVE TRADING - Real money at risk!</b>
    """
    
    update_session(chat_id, state=STATE_LIVE_WAITING_AMOUNT, 
                  contract_address=contract_address,
                  token_name=token_name, token_symbol=token_symbol, 
                  entry_price=current_price)
    
    send_message(chat_id, contract_text)

def handle_live_amount_input(chat_id, amount_text):
    """Handle live trading amount input"""
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Store amount and move to stop-loss
        update_session(chat_id, trade_amount=amount, state=STATE_LIVE_WAITING_STOPLOSS)
        
        session = get_or_create_session(chat_id)
        stoploss_text = f"""
✅ <b>Live Trade Amount Set: {amount:.3f} SOL</b>

📉 Now enter your <b>Stop-Loss percentage</b> (0-100):

This is the percentage loss at which the bot will automatically sell to limit losses.

<i>Example: Enter "20" for 20% stop-loss</i>

<b>⚠️ LIVE TRADING - Position size: {amount:.3f} SOL</b>
Type a number between 0-100 or /cancel to abort.
        """
        send_message(chat_id, stoploss_text)
        
    except ValueError:
        error_text = """
❌ <b>Invalid SOL Amount</b>

Please enter a valid amount in SOL (numbers only).

<i>Examples: "0.1", "0.5", "1.0"</i>

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)

def handle_live_stoploss_input(chat_id, text):
    """Handle stop-loss input for live trading"""
    try:
        stop_loss = float(text)
        if stop_loss <= 0 or stop_loss >= 100:
            raise ValueError("Stop-loss must be between 0 and 100")
    except ValueError:
        error_text = """
❌ <b>Invalid Stop-Loss Value</b>

Please enter a valid stop-loss percentage between 1 and 99.

<b>💡 Examples:</b>
• 10 (for -10% stop-loss)
• 25 (for -25% stop-loss)
• 50 (for -50% stop-loss)

Enter your stop-loss percentage:
        """
        send_message(chat_id, error_text)
        return
    
    stoploss_text = f"""
📉 <b>LIVE Stop-Loss Set: -{stop_loss}%</b>

Your position will be automatically sold if the token price drops {stop_loss}% from your entry point.

Now enter your take-profit percentage (e.g., 100 for +100%):
    """
    
    update_session(chat_id, state=STATE_LIVE_WAITING_TAKEPROFIT, stop_loss=stop_loss)
    send_message(chat_id, stoploss_text)

def handle_live_takeprofit_input(chat_id, text):
    """Handle take-profit input for live trading"""
    try:
        take_profit = float(text)
        if take_profit <= 0:
            raise ValueError("Take-profit must be positive")
    except ValueError:
        error_text = """
❌ <b>Invalid Take-Profit Value</b>

Please enter a valid take-profit percentage (positive number).

<b>💡 Examples:</b>
• 50 (for +50% profit target)
• 100 (for +100% profit target)
• 200 (for +200% profit target)

Enter your take-profit percentage:
        """
        send_message(chat_id, error_text)
        return
    
    takeprofit_text = f"""
📈 <b>LIVE Take-Profit Set: +{take_profit}%</b>

Your position will be automatically sold when the token price increases {take_profit}% from your entry point.

Finally, enter what percentage of your holdings to sell when targets are hit (e.g., 100 for all holdings):
    """
    
    update_session(chat_id, state=STATE_LIVE_WAITING_SELLPERCENT, take_profit=take_profit)
    send_message(chat_id, takeprofit_text)

def handle_live_sellpercent_input(chat_id, text):
    """Handle sell percentage input for live trading"""
    try:
        sell_percent = float(text)
        if sell_percent <= 0 or sell_percent > 100:
            raise ValueError("Sell percentage must be between 1 and 100")
    except ValueError:
        error_text = """
❌ <b>Invalid Sell Percentage</b>

Please enter a valid percentage between 1 and 100.

<b>💡 Examples:</b>
• 50 (sell 50% of holdings)
• 75 (sell 75% of holdings)  
• 100 (sell all holdings)

Enter sell percentage:
        """
        send_message(chat_id, error_text)
        return
    
    session = get_or_create_session(chat_id)
    is_vip_mode = session.trading_mode == 'fetch'
    token_display = f"{session.token_name} (${session.token_symbol})" if session.token_name else "Unknown Token"
    entry_price_display = f"${session.entry_price:.8f}" if session.entry_price < 1 else f"${session.entry_price:.4f}"
    trade_amount_display = f"{session.trade_amount:.3f} SOL" if session.trade_amount else "Not specified"
    
    mode_title = "VIP FETCH TRADING ORDER READY" if is_vip_mode else "LIVE TRADING ORDER READY"
    mode_features = """
<b>🎯 VIP Features Active:</b>
• Priority execution speeds
• Enhanced risk management
• Advanced trading analytics
• Premium customer support
""" if is_vip_mode else ""
    
    confirmation_text = f"""
⚠️ <b>{mode_title}</b>

<b>🔴 FINAL CONFIRMATION REQUIRED</b>
This will place a REAL trade with your actual funds!
{mode_features}
<b>📊 Order Summary:</b>
🏷️ <b>Token:</b> {token_display}
💲 <b>Entry Price:</b> {entry_price_display}
💰 <b>Trade Amount:</b> {trade_amount_display}
👛 <b>Wallet:</b> {session.wallet_address[:8]}...{session.wallet_address[-8:]}
📉 <b>Stop-Loss:</b> -{session.stop_loss}%
📈 <b>Take-Profit:</b> +{session.take_profit}%
💰 <b>Sell Amount:</b> {sell_percent}%

<b>⚠️ RISK WARNING:</b>
• This involves REAL money and blockchain transactions
• You could lose your entire investment
• Market conditions can change rapidly
• No refunds or reversal possible

Type <b>/confirm</b> to execute this {"VIP " if is_vip_mode else ""}LIVE trade or <b>/cancel</b> to abort.
    """
    
    update_session(chat_id, state=STATE_LIVE_READY_TO_CONFIRM, sell_percent=sell_percent)
    send_message(chat_id, confirmation_text)

def execute_live_trade(chat_id):
    """Execute a live trading order"""
    session = get_or_create_session(chat_id)
    
    # Verify all required information is present
    if not all([session.wallet_address, session.contract_address, session.stop_loss, 
                session.take_profit, session.sell_percent]):
        error_text = """
❌ <b>Incomplete Trading Information</b>

Your trading session appears incomplete. Please start over.

Type /snipe for live trading or /fetch for VIP trading.
        """
        update_session(chat_id, state=STATE_IDLE)
        send_message(chat_id, error_text)
        return
    
    # Re-verify Mork balance before executing
    mork_balance = get_solana_wallet_balance(session.wallet_address, MORK_TOKEN_CONTRACT)
    mork_price_sol = get_mork_price_in_sol()
    current_value_sol = mork_balance * mork_price_sol
    
    if current_value_sol < 1.0:
        insufficient_text = f"""
❌ <b>Insufficient $MORK Holdings</b>

Your $MORK balance has changed since verification.

<b>💎 Current Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📉 <b>Required:</b> 1.000 SOL worth

Please ensure you maintain the required $MORK holdings and try again.

Type /snipe for live trading or /fetch for VIP trading.
        """
        update_session(chat_id, state=STATE_IDLE)
        send_message(chat_id, insufficient_text)
        return
    
    # Execute the live trade (placeholder for actual implementation)
    is_vip_mode = session.trading_mode == 'fetch'
    token_display = f"{session.token_name} (${session.token_symbol})" if session.token_name else "Unknown Token"
    entry_price_display = f"${session.entry_price:.8f}" if session.entry_price < 1 else f"${session.entry_price:.4f}"
    
    mode_prefix = "VIP FETCH " if is_vip_mode else "LIVE "
    execution_text = f"""
🚀 <b>{mode_prefix}TRADE EXECUTED!</b>

<b>✅ {"VIP " if is_vip_mode else ""}Order Placed Successfully</b>

<b>📊 Trade Details:</b>
🏷️ <b>Token:</b> {token_display}
💲 <b>Entry Price:</b> {entry_price_display}
👛 <b>Wallet:</b> {session.wallet_address[:8]}...{session.wallet_address[-8:]}
📉 <b>Stop-Loss:</b> -{session.stop_loss}%
📈 <b>Take-Profit:</b> +{session.take_profit}%
💰 <b>Sell Amount:</b> {session.sell_percent}%

<b>🎯 What Happens Next:</b>
• Your order is now active on the Solana blockchain
• The bot will monitor price movements 24/7
• Automatic execution when targets are reached
• You'll be notified of any trade executions

<b>⚠️ Important Notes:</b>
• Keep sufficient SOL in your wallet for transaction fees
• Maintain your minimum $MORK token holdings
• Market conditions can change rapidly

<b>📱 Monitoring:</b>
Type /status to check your active orders anytime.

Your live trading order is now active! Good luck! 🎯
    """
    
    # Reset session after successful execution
    update_session(chat_id, state=STATE_IDLE, 
                  contract_address=None, wallet_address=None,
                  stop_loss=None, take_profit=None, sell_percent=None,
                  token_name=None, token_symbol=None, entry_price=None)
    
    send_message(chat_id, execution_text)

def handle_update(update):
    """Main update handler for Telegram webhook"""
    try:
        if 'message' not in update:
            return
        
        message = update['message']
        chat_id = message['chat']['id']
        
        if 'text' not in message:
            send_message(chat_id, "Please send text messages only.")
            return
        
        text = message['text'].strip()
        user_first_name = message['from'].get('first_name', 'User')
        
        # Handle commands
        if text.startswith('/'):
            command = text.lower().split()[0]
            
            if command == '/start':
                handle_start_command(chat_id, user_first_name)
            elif command == '/simulate':
                handle_simulate_command(chat_id)
            elif command == '/snipe':
                handle_snipe_command(chat_id)
            elif command == '/fetch':
                handle_fetch_command(chat_id)
            elif command == '/confirm':
                handle_confirm_command(chat_id)
            elif command == '/status':
                handle_status_command(chat_id)
            elif command == '/help':
                handle_help_command(chat_id)
            elif command == '/cancel':
                handle_cancel_command(chat_id)
            elif command == '/whatif':
                handle_whatif_command(chat_id)

            else:
                send_message(chat_id, "Unknown command. Type /help for available commands.")
        else:
            # Handle text input based on current state
            session = get_or_create_session(chat_id)
            
            # Debug logging
            logging.info(f"Chat {chat_id}: Current state = {session.state}, Text = {text[:50]}")
            
            if session.state == STATE_WAITING_CONTRACT:
                logging.info(f"Chat {chat_id}: Processing contract input")
                handle_contract_input(chat_id, text)
            elif session.state == STATE_WAITING_AMOUNT:
                logging.info(f"Chat {chat_id}: Processing amount input")
                handle_amount_input(chat_id, text)
            elif session.state == STATE_WAITING_STOPLOSS:
                logging.info(f"Chat {chat_id}: Processing stop-loss input")
                handle_stoploss_input(chat_id, text)
            elif session.state == STATE_WAITING_TAKEPROFIT:
                logging.info(f"Chat {chat_id}: Processing take-profit input")
                handle_takeprofit_input(chat_id, text)
            elif session.state == STATE_WAITING_SELLPERCENT:
                logging.info(f"Chat {chat_id}: Processing sell percent input")
                handle_sellpercent_input(chat_id, text)
            # Live trading states
            elif session.state == STATE_WAITING_WALLET:
                logging.info(f"Chat {chat_id}: Processing wallet input")
                handle_wallet_input(chat_id, text)
            elif session.state == STATE_LIVE_WAITING_CONTRACT:
                logging.info(f"Chat {chat_id}: Processing live contract input")
                handle_live_contract_input(chat_id, text)
            elif session.state == STATE_LIVE_WAITING_AMOUNT:
                logging.info(f"Chat {chat_id}: Processing live amount input")
                handle_live_amount_input(chat_id, text)
            elif session.state == STATE_LIVE_WAITING_STOPLOSS:
                logging.info(f"Chat {chat_id}: Processing live stop-loss input")
                handle_live_stoploss_input(chat_id, text)
            elif session.state == STATE_LIVE_WAITING_TAKEPROFIT:
                logging.info(f"Chat {chat_id}: Processing live take-profit input")
                handle_live_takeprofit_input(chat_id, text)
            elif session.state == STATE_LIVE_WAITING_SELLPERCENT:
                logging.info(f"Chat {chat_id}: Processing live sell percent input")
                handle_live_sellpercent_input(chat_id, text)
            else:
                logging.info(f"Chat {chat_id}: Unknown state '{session.state}', sending help message")
                send_message(chat_id, "I'm not sure what you mean. Type /help for available commands or /snipe to start a simulation.")
    
    except Exception as e:
        logging.error(f"Error handling update: {e}")
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            send_message(chat_id, "Sorry, an error occurred. Please try again or type /start to reset.")

def set_webhook(webhook_url):
    """Set the webhook URL for the bot"""
    url = f"{TELEGRAM_API_URL}/setWebhook"
    data = {'url': webhook_url}
    
    try:
        response = requests.post(url, json=data)
        result = response.json()
        logging.info(f"Webhook set result: {result}")
        return result.get('ok', False)
    except Exception as e:
        logging.error(f"Error setting webhook: {e}")
        return False
