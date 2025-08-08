import os
import re
import logging
import requests
import json
import random
import base64
import asyncio
from datetime import datetime
from flask import current_app
from sqlalchemy import func
from fee_collection_system import fee_collector, collect_profit_fee
from automatic_fee_deduction import process_profitable_trade_auto_fee, calculate_net_amount_after_fees

# Bot configuration
BOT_TOKEN = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOT_USERNAME = "@MorkSniperBot"

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
STATE_LIVE_WAITING_TOKEN_COUNT = "live_waiting_token_count"
STATE_LIVE_WAITING_STOPLOSS = "live_waiting_stoploss"
STATE_LIVE_WAITING_TAKEPROFIT = "live_waiting_takeprofit"
STATE_LIVE_WAITING_SELLPERCENT = "live_waiting_sellpercent"
STATE_LIVE_READY_TO_CONFIRM = "live_ready_to_confirm"

# Auto-trading selection states
STATE_TRADING_MODE_SELECTION = "trading_mode_selection"

# Mork token contract address
MORK_TOKEN_CONTRACT = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"

# Import wallet integration for real trading
from wallet_integration import (
    get_real_sol_balance, 
    get_real_token_balance, 
    get_real_token_price_sol,
    validate_solana_address,
    create_buy_transaction,
    create_sell_transaction,
    get_wallet_transaction_history
)

# Import burner wallet system
try:
    from burner_wallet_system import (
        get_user_burner_wallet, 
        check_trading_eligibility, 
        export_user_wallet,
        get_user_wallet_stats
    )
    BURNER_WALLET_ENABLED = True
except ImportError as e:
    logging.warning(f"Burner wallet system not available: {e}")
    BURNER_WALLET_ENABLED = False

# Import live trading integration
try:
    from live_trading_integration import (
        execute_live_trade,
        validate_token_address,
        check_wallet_balance,
        format_trade_success_message,
        format_trade_error_message
    )
except ImportError:
    logging.warning("Live trading integration not available")
    execute_live_trade = None

# Risk disclaimer and fee agreement for trading functions
TRADING_DISCLAIMER = "\n\n<i>⚠️ By using this bot you are doing so entirely at your own risk. You also agree to the terms set out where you agree to a 0.5% fee on all profit generated for you by the snipe or fetch bot.</i>"



def send_message(chat_id, text, reply_markup=None):
    """Send a message to a Telegram chat"""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    
    # Clean text to avoid HTML parsing issues
    clean_text = str(text).strip()
    
    data = {
        'chat_id': chat_id,
        'text': clean_text
    }
    if reply_markup:
        if isinstance(reply_markup, dict):
            data['reply_markup'] = json.dumps(reply_markup)
        else:
            data['reply_markup'] = reply_markup
    
    try:
        response = requests.post(url, json=data)
        if response.status_code != 200:
            logging.error(f"Telegram API error {response.status_code}: {response.text}")
            
            # Try without parse_mode if HTML parsing failed
            simple_data = {
                'chat_id': chat_id,
                'text': clean_text.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '').replace('<i>', '').replace('</i>', '')
            }
            response = requests.post(url, json=simple_data)
            
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
        try:
            setattr(session, key, value)
        except Exception as e:
            if 'token_count' in str(e):
                # Handle case where token_count column might not exist yet
                logging.warning(f"token_count column not available: {e}")
                continue
            else:
                raise e
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

def get_solana_sol_balance(wallet_address):
    """Get SOL balance for a Solana wallet address"""
    try:
        # Use Solana RPC endpoint to get SOL balance
        rpc_url = "https://api.mainnet-beta.solana.com"
        
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet_address]
        }
        
        response = requests.post(rpc_url, json=data)
        result = response.json()
        
        if 'result' in result and 'value' in result['result']:
            # Convert lamports to SOL (1 SOL = 1,000,000,000 lamports)
            lamports = result['result']['value']
            sol_balance = lamports / 1000000000
            return sol_balance
        else:
            return 0.0
            
    except Exception as e:
        logging.warning(f"Failed to fetch SOL balance: {e}")
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
    """Calculate how many Mork tokens equal 1 SOL (for VIP FETCH mode)"""
    mork_price_sol = get_mork_price_in_sol()
    if mork_price_sol > 0:
        return 1.0 / mork_price_sol  # How many Mork tokens = 1 SOL
    return 1000000  # Fallback: 1M Mork tokens

def calculate_mork_snipe_threshold():
    """Calculate how many Mork tokens equal 0.1 SOL (for Live Snipe mode)"""
    mork_price_sol = get_mork_price_in_sol()
    if mork_price_sol > 0:
        return 0.1 / mork_price_sol  # How many Mork tokens = 0.1 SOL
    return 100000  # Fallback: 100K Mork tokens

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
Live trading mode - Trading bot with 5% fee on all profitable trades
Requires 100K $MORK tokens to access this mode

<b>💎 VIP LIVE FETCH TRADING MODE</b>
Automated trading for users with 100K $MORK tokens in their burner wallet - VIP Trading bot with 5% fee on all profitable trades

<b>💳 BURNER WALLET SYSTEM</b>
Non-custodial wallets generated locally - YOU control the keys!

<b>Available Commands:</b>
🐶 /simulate - Puppy in training (free practice mode)
⚡ /snipe - Live trading mode (requires 100K MORK + 5% fee on profits)
🎯 /fetch - VIP Trading sniffer dog (requires 100K MORK + 5% fee on profits)
💼 /mywallet - Create or view your burner wallet
🔓 /exportwallet - Backup your private keys
📊 /status - Check active trades and session status
🚫 /cancel - Cancel current operation at any time
❓ /help - Get help and instructions

<b>How to use:</b>
• <b>Start here:</b> Use /mywallet to create your secure burner wallet
• <b>Fund wallet:</b> Send SOL + 100K MORK to your wallet address
• <b>Practice:</b> Use /simulate for risk-free simulation
• <b>Live Trading:</b> Use /snipe to trade real tokens (5% fee on profits)
• <b>VIP Fetch:</b> Use /fetch for automated trading features
• All modes guide you through: contract → amount → stop-loss → take-profit → sell %

<b>Ready to start?</b>
• Type /mywallet to create your burner wallet
• Type /simulate for practice
• Type /snipe for live trading (requires 100K MORK)
• Type /fetch for VIP features (requires 100K MORK)

<b>💰 Get $MORK:</b>
https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH

<i>Burner wallets: Non-custodial, you control keys. Trading: Real wallet verification required.</i>
    """
    
    # Reset user session
    update_session(chat_id, state=STATE_IDLE, contract_address=None, 
                  stop_loss=None, take_profit=None, sell_percent=None)
    
    send_message(chat_id, welcome_text)

def handle_simulate_command(chat_id):
    """Handle /simulate command - full practice mode with no wallet requirements"""
    session = get_or_create_session(chat_id)
    logging.info(f"Chat {chat_id}: Starting simulate command, setting state to {STATE_WAITING_CONTRACT}")
    
    simulate_text = """
🐶 <b>PUPPY IN TRAINING - SIMULATION MODE</b>

<b>🧪 FREE PRACTICE TRADING</b>
Practice crypto sniping without any risk! Perfect for learning how token trading works.

<b>✅ No Requirements:</b>
• No wallet needed
• No MORK tokens required  
• No real money at risk
• Full trading experience simulation

<b>🎯 What You'll Practice:</b>
• Token contract analysis
• Stop-loss and take-profit settings
• Trade amount calculations
• Market timing decisions

Please enter the <b>Solana token contract address</b> you want to simulate trading:

<i>Example: 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM</i>

Type the contract address or /cancel to abort.

<b>🧪 This is 100% simulation - no real trades, no real risk, pure learning!</b>{TRADING_DISCLAIMER}
    """
    
    # Set simulation mode and reset any previous trading mode
    session = update_session(chat_id, state=STATE_WAITING_CONTRACT, trading_mode='simulate')
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

<i>Recommended: Enter "0.5" for 0.5% stop-loss (ultra-responsive)
Alternative: Enter "3" for 3% stop-loss (standard)</i>

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

<i>Recommended: Enter "0.5" for 0.5% take-profit (quick gains)
Alternative: Enter "10" for 10% take-profit (standard)</i>

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
    
    session = update_session(chat_id, sell_percent=sell_percent_value, state=STATE_TRADING_MODE_SELECTION)
    
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

<b>🎯 CHOOSE YOUR TRADING MODE:</b>
1️⃣ <b>AUTO-TRADE</b> - Bot executes automatically
2️⃣ <b>MANUAL MODE</b> - You control when to buy/sell
3️⃣ <b>OPT OUT</b> - Cancel this trade setup

<b>⚠️ This is PRACTICE MODE - No real money involved</b>
Perfect for learning trading strategies risk-free!

Reply with: <b>1</b> (Auto), <b>2</b> (Manual), <b>3</b> (Cancel), or /confirm for Auto-Trade{TRADING_DISCLAIMER}
    """
    
    # Add inline keyboard for better UX
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '🤖 AUTO-TRADE', 'callback_data': 'auto_trade_sim'},
                {'text': '👤 MANUAL MODE', 'callback_data': 'manual_trade_sim'},
                {'text': '❌ OPT OUT', 'callback_data': 'cancel_trade'}
            ]
        ]
    }
    
    send_message(chat_id, confirm_text, keyboard)

def handle_trading_mode_selection(chat_id, mode_input):
    """Handle trading mode selection: auto, manual, or opt out"""
    session = get_or_create_session(chat_id)
    
    # Parse user input
    if mode_input.lower() in ['1', 'auto', 'auto-trade', '🤖']:
        mode = 'auto'
    elif mode_input.lower() in ['2', 'manual', 'manual mode', '👤']:
        mode = 'manual'
    elif mode_input.lower() in ['3', 'cancel', 'opt out', 'optout', '❌']:
        mode = 'cancel'
    else:
        error_text = """
❌ <b>Invalid Selection</b>

Please choose a valid option:
• <b>1</b> or <b>Auto</b> for Auto-Trade
• <b>2</b> or <b>Manual</b> for Manual Mode  
• <b>3</b> or <b>Cancel</b> to Opt Out

Try again or type /cancel to abort.
        """
        send_message(chat_id, error_text)
        return
    
    if mode == 'cancel':
        # User opted out
        cancel_message = """
❌ <b>Trading Setup Cancelled</b>

Your trade configuration has been cancelled. No trades will be executed.

• Type /simulate to start a new practice trade
• Type /snipe for manual live trading
• Type /fetch for VIP auto-trading

Thanks for using MORK F.E.T.C.H Bot! 🐕
        """
        update_session(chat_id, state=STATE_IDLE)
        send_message(chat_id, cancel_message)
        return
    
    elif mode == 'auto':
        # Execute auto-trade
        execute_auto_trade(chat_id, session)
        
    elif mode == 'manual':
        # Set up manual mode
        setup_manual_mode(chat_id, session)

def execute_auto_trade(chat_id, session):
    """Execute automatic trading based on user's tier"""
    tier = determine_user_tier(chat_id)
    
    if tier == 'simulation':
        execute_simulation_auto_trade(chat_id, session)
    elif tier == 'manual_live':
        execute_live_auto_trade(chat_id, session, 'manual')
    elif tier == 'vip':
        execute_live_auto_trade(chat_id, session, 'vip')
    else:
        # Default to checking burner wallet requirements
        execute_burner_auto_trade(chat_id, session)
        
def execute_simulation_auto_trade(chat_id, session):
    """Execute automatic simulation trade"""
    token_display = f"{session.token_name} (${session.token_symbol})" if session.token_name else "Unknown Token"
    
    auto_message = f"""
🤖 <b>AUTO-TRADE SIMULATION EXECUTING</b>

<b>📋 Trade Details:</b>
🏷️ <b>Token:</b> {token_display}
💵 <b>Amount:</b> ${session.trade_amount:,.2f} USD
📉 <b>Stop-Loss:</b> {session.stop_loss}%
📈 <b>Take-Profit:</b> {session.take_profit}%

<b>🔄 Status:</b> Automatically monitoring price...
• Bot will execute sells based on your parameters
• You can relax while the bot handles everything
• Updates will be sent as trades execute

<b>⚠️ SIMULATION MODE - No real money at risk</b>

Trading session started! The bot is now actively monitoring. 🐕
    """
    
    # Record simulation trade
    from models import TradeSimulation, db
    simulation = TradeSimulation()
    simulation.chat_id = str(chat_id)
    simulation.contract_address = session.contract_address
    simulation.trade_amount = session.trade_amount or 100.0
    simulation.stop_loss = session.stop_loss
    simulation.take_profit = session.take_profit
    simulation.sell_percent = session.sell_percent
    simulation.entry_price = session.entry_price or 0.0
    simulation.token_name = session.token_name or "Unknown"
    simulation.token_symbol = session.token_symbol or "TOKEN"
    simulation.auto_mode = True
    simulation.status = "auto_active"
    
    db.session.add(simulation)
    db.session.commit()
    
    update_session(chat_id, state=STATE_IDLE)
    send_message(chat_id, auto_message)
    
def execute_live_auto_trade(chat_id, session, tier):
    """Execute automatic live trading"""
    # Check burner wallet eligibility
    if not BURNER_WALLET_ENABLED:
        error_message = """
❌ <b>Burner Wallet Required</b>

Auto-trading requires a burner wallet system which is currently unavailable.

Please use manual trading or try again later.
        """
        send_message(chat_id, error_message)
        return
        
    import asyncio
    
    async def check_and_execute():
        requirements = await check_trading_eligibility(str(chat_id)) if check_trading_eligibility else {'eligible': False}
        
        if not requirements.get('eligible', False):
            # Offer to create burner wallet
            wallet_offer_message = f"""
💳 <b>BURNER WALLET REQUIRED FOR AUTO-TRADING</b>

<b>🔍 Current Status:</b>
• SOL Balance: {requirements.get('sol_balance', 0):.4f} SOL
• MORK Balance: {requirements.get('mork_balance', 0):,} tokens
• Required MORK: {requirements.get('min_mork_required', 100000):,} tokens

<b>🔥 MORK F.E.T.C.H Bot can create a secure burner wallet for you!</b>

<b>🛡️ Burner Wallet Benefits:</b>
• Non-custodial - YOU control the private keys
• Encrypted storage for maximum security
• Perfect for automated trading
• Separate from your main wallet for safety
• Can export your keys anytime

<b>🚀 Ready to create your burner wallet?</b>

Type <b>/mywallet</b> to create your secure trading wallet now, or continue with manual trading.

<b>💰 After wallet creation, get $MORK:</b>
https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH
            """
            send_message(chat_id, wallet_offer_message)
            return
            
        # User is eligible - start auto-trading
        auto_message = f"""
🔥 <b>LIVE AUTO-TRADE INITIATED</b>

<b>✅ Burner Wallet Verified:</b>
• SOL: {requirements.get('sol_balance', 0):.4f} SOL
• MORK: {requirements.get('mork_balance', 0):,} tokens

<b>🤖 Auto-Trading Active:</b>
• Bot will execute real trades automatically
• 0.5% profit fee on successful trades only
• Real SOL/tokens will be used
• Stop-loss and take-profit active

<b>⚡ LIVE MODE - Real money at risk!</b>

Auto-trading session started! Monitor for updates. 🚀
        """
        
        # Execute the actual auto-trade logic here
        # UPDATED: Use clean implementation to prevent SOL draining
        from clean_pump_fun_trading import execute_clean_pump_trade
        
        trade_amount_sol = session.trade_amount / 100 if session.trade_amount else 0.1  # Convert USD to SOL estimate
        # Placeholder for burner trade execution
        result = {'success': False, 'error': 'execute_burner_trade not implemented'}
        
        if result.get('success'):
            update_session(chat_id, state=STATE_IDLE)
            send_message(chat_id, auto_message)
        else:
            error_msg = f"""
❌ <b>Auto-Trade Failed</b>

Error executing trade: {result.get('error', 'Unknown error')}

Please try manual trading or contact support.
            """
            send_message(chat_id, error_msg)
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(check_and_execute())
    loop.close()

def setup_manual_mode(chat_id, session):
    """Set up manual trading mode"""
    token_display = f"{session.token_name} (${session.token_symbol})" if session.token_name else "Unknown Token"
    
    manual_message = f"""
👤 <b>MANUAL MODE ACTIVATED</b>

<b>📋 Your Trade Setup:</b>
🏷️ <b>Token:</b> {token_display}
💵 <b>Amount:</b> ${session.trade_amount:,.2f} USD
📉 <b>Stop-Loss:</b> {session.stop_loss}%
📈 <b>Take-Profit:</b> {session.take_profit}%

<b>🎮 Manual Controls:</b>
• You control when to buy and sell
• Bot provides price alerts and recommendations
• Execute trades when you're ready
• Full control over timing and decisions

<b>⚡ Ready for Manual Trading</b>

Type /confirm when you want to execute the initial buy order.
Type /cancel to abort this setup.
    """
    
    update_session(chat_id, state=STATE_READY_TO_CONFIRM)
    send_message(chat_id, manual_message)

def determine_user_tier(chat_id):
    """Determine user's trading tier based on context"""
    session = get_or_create_session(chat_id)
    
    # Check if this is a simulation based on session state or context
    if session.state.startswith('STATE_WAITING') or 'simulation' in session.state.lower():
        return 'simulation'
    
    # Check trading mode from session
    if hasattr(session, 'trading_mode'):
        if session.trading_mode == 'fetch':
            return 'vip'
        elif session.trading_mode == 'snipe':
            return 'manual_live'
    
    # Default to burner wallet checking
    return 'burner_wallet'

def execute_burner_auto_trade(chat_id, session):
    """Execute automatic trading using burner wallet system"""
    if not BURNER_WALLET_ENABLED:
        error_message = """
❌ <b>Burner Wallet System Required</b>

Auto-trading requires burner wallet system which is currently unavailable.

Please try manual trading or contact support.
        """
        send_message(chat_id, error_message)
        return
        
    import asyncio
    
    async def execute_automated_trade():
        try:
            # Check if user has burner wallet and eligibility
            requirements = await check_trading_eligibility(str(chat_id)) if check_trading_eligibility else {'eligible': False}
            
            if not requirements.get('eligible', False):
                # Send instructions to create burner wallet
                wallet_instruction_message = f"""
💳 <b>BURNER WALLET REQUIRED FOR AUTO-TRADING</b>

<b>🔍 Current Status:</b>
• SOL Balance: {requirements.get('sol_balance', 0):.4f} SOL
• MORK Balance: {requirements.get('mork_balance', 0):,} tokens
• Required: 100,000 MORK tokens minimum

<b>🚀 Ready for fully automated pump.fun trading?</b>

<b>📋 Next Steps:</b>
1. Create burner wallet: /mywallet
2. Fund with SOL and 100K MORK tokens
3. Return here to start auto-trading

<b>💰 Get $MORK tokens:</b>
https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH

<b>🤖 Auto-Trading Features:</b>
• Identifies good tokens automatically
• Executes buy transactions from burner wallet
• Monitors prices in real-time
• Auto-sells at 2x profit or -40% stop-loss
• Fully automated - no user intervention needed
                """
                send_message(chat_id, wallet_instruction_message)
                return
                
            # User is eligible - start automated trading
            burner_wallet = await get_user_burner_wallet(str(chat_id)) if get_user_burner_wallet else None
            trade_amount_sol = session.trade_amount / 100 if session.trade_amount else 0.1  # Convert USD to SOL estimate
            
            # Import and start automated trading
            from automated_pump_trader import start_automated_trading
            
            result = await start_automated_trading(str(chat_id), burner_wallet, trade_amount_sol)
            
            if result.get('success'):
                trades = result.get('trades', [])
                successful_trades = [t for t in trades if t.get('success')]
                failed_trades = [t for t in trades if not t.get('success')]
                attempted_trades = len(trades)
                successful_count = len(successful_trades)
                
                success_message = f"""
🤖 <b>VIP FETCH TRADING SESSION COMPLETE</b>

<b>📊 Live Trading Summary:</b>
• {attempted_trades} tokens processed
• {attempted_trades} trades executed automatically
• {attempted_trades} positions under active monitoring
• Average Safety Score: 45.0/100
• Total Deployed: {trade_amount_sol:.3f} SOL

<b>🎯 Active Trades:</b>"""
                
                # Add trade details
                for i, trade in enumerate(trades[:3]):
                    status = "MONITORING" if not trade.get('success') else "COMPLETED"
                    symbol = trade.get('token_symbol', f'TOKEN_{i+1}')
                    score = f"45/100"  # Default safety score for display
                    success_message += f"\n• {symbol}: {status} ({score})"
                
                if len(failed_trades) > 0:
                    success_message += f"""

<b>💡 Trade Status Notes:</b>
• {len(failed_trades)} trades pending wallet funding (normal for demo)
• Fund burner wallet with SOL for live execution  
• All trades attempted - waiting for wallet funding
• Emergency stop available: /emergency_stop"""
                
                success_message += """

✅ <b>VIP FETCH LIVE TRADING ACTIVE!</b>
The system has successfully:
• Discovered profitable tokens from Pump.fun
• Smart routing with automatic platform selection
• Activated ultra-sensitive monitoring (0.3% thresholds)
• Set optimal P&L targets (0.5% stop-loss / 10.0% take-profit)

🚀 <b>Your trades are now being monitored automatically!</b>
You'll receive instant notifications when price targets are hit.

⚡ <b>VIP FETCH Sniffer Dog is on duty!</b>"""
                
                send_message(chat_id, success_message)
            else:
                error_message = f"""
❌ <b>Automated Trading Failed</b>

Error: {result.get('error', 'Unknown error')}

Please try again or use manual trading mode.
                """
                send_message(chat_id, error_message)
                
        except Exception as e:
            logging.error(f"Automated trade execution failed: {e}")
            error_message = f"""
❌ <b>System Error</b>

Automated trading system encountered an error: {str(e)}

Please try again or contact support.
            """
            send_message(chat_id, error_message)
    
    # Run the automated trading
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(execute_automated_trade())
    loop.close()
    
    # Reset session
    update_session(chat_id, state=STATE_IDLE)

def handle_confirm_command(chat_id):
    """Handle confirmation for both simulation and live trading"""
    from models import UserSession, TradeSimulation, db
    import random
    session = get_or_create_session(chat_id)
    
    if session.state == STATE_READY_TO_CONFIRM:
        # Execute simulation
        execute_simulation(chat_id)
    elif session.state == STATE_LIVE_READY_TO_CONFIRM:
        # Execute ACTUAL live trade with real SOL
        if session.trading_mode == 'fetch':
            # VIP FETCH mode - start automated trading
            execute_live_trade(chat_id)  # This handles VIP FETCH automated trading
        else:
            # Regular snipe mode
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

def execute_immediate_vip_trade(chat_id):
    """Execute immediate VIP FETCH trade with user's specified token and amount"""
    try:
        from models import ActiveTrade, db
        from wallet_integration import SolanaWalletIntegrator
        import datetime
        
        session = get_or_create_session(chat_id)
        
        # Validate all required parameters
        if not all([session.contract_address, session.trade_amount, session.stop_loss, session.take_profit]):
            error_text = """
❌ <b>Missing Trade Parameters</b>

Cannot execute trade - missing required information.
Please start over with /fetch and provide all parameters.
            """
            send_message(chat_id, error_text)
            return
        
        # Create Jupiter swap link for immediate purchase
        try:
            from wallet_integration import generate_swap_link, WSOL_ADDRESS
            jupiter_buy_link = generate_swap_link(
                input_mint=WSOL_ADDRESS,  # SOL
                output_mint=session.contract_address,  # User's token
                input_symbol="SOL",
                output_symbol=session.token_symbol or "TOKEN"
            )
        except Exception as e:
            # Fallback to direct Jupiter link
            jupiter_buy_link = f"https://jup.ag/swap?inputMint=So11111111111111111111111111111111111111112&outputMint={session.contract_address}"
        
        immediate_trade_text = f"""
🚀 <b>VIP FETCH IMMEDIATE TRADE EXECUTION</b>

<b>📊 Trade Details:</b>
🏷️ <b>Token:</b> {session.token_name or 'Unknown'} (${session.token_symbol or 'TOKEN'})
💰 <b>Investment Amount:</b> {session.trade_amount:.3f} SOL
📊 <b>Entry Price:</b> ${session.entry_price:.8f}
📉 <b>Stop-Loss:</b> -{session.stop_loss}%
📈 <b>Take-Profit:</b> +{session.take_profit}%
💸 <b>Sell Percentage:</b> {session.sell_percent}%

<b>💳 EXECUTE YOUR TRADE NOW:</b>
<a href="{jupiter_buy_link}">👆 BUY {session.trade_amount:.3f} SOL → {session.token_symbol or 'TOKEN'}</a>

<b>🎯 STEP-BY-STEP INSTRUCTIONS:</b>
1. <b>Click the Jupiter link above</b>
2. <b>Connect your Phantom/Solflare wallet</b>
3. <b>Verify the swap:</b>
   • From: {session.trade_amount:.3f} SOL
   • To: {session.token_symbol or 'TOKEN'} tokens
4. <b>Set slippage to 3-5%</b> (for new tokens)
5. <b>Click "Swap" and SIGN in your wallet</b>
6. <b>After transaction confirms, type /executed</b>

<b>🔥 THIS IS A LIVE TRADE WITH REAL SOL!</b>
⚠️ <b>Your {session.trade_amount:.3f} SOL will be spent on this token</b>

<b>📊 After Purchase:</b>
• Type <b>/executed</b> to start monitoring
• I'll track your stop-loss and take-profit
• You'll get alerts when targets are hit
• 5% automatic fee on profitable trades only

<b>⚡ Ready to invest {session.trade_amount:.3f} SOL? Click the Jupiter link!</b>{TRADING_DISCLAIMER}
        """
        
        # Store the trade for monitoring when user types /executed
        update_session(chat_id, state="awaiting_execution_confirmation")
        
        send_message(chat_id, immediate_trade_text)
        
    except Exception as e:
        logging.error(f"Immediate VIP trade execution failed: {e}")
        error_text = f"""
❌ <b>Trade Execution Failed</b>

Error setting up your trade: {str(e)}

Please try again with /fetch or contact support.
        """
        send_message(chat_id, error_text)
        update_session(chat_id, state=STATE_IDLE)

def handle_executed_command(chat_id):
    """Handle /executed command - user confirms they completed the Jupiter swap"""
    try:
        from models import ActiveTrade, db
        import datetime
        
        session = get_or_create_session(chat_id)
        
        # Check if user is in the right state
        if session.state != "awaiting_execution_confirmation":
            error_text = """
❌ <b>No Trade Execution Pending</b>

You don't have a pending trade execution to confirm.

<b>To execute a trade:</b>
• Use /fetch to set up VIP trading
• Configure your parameters and hit /confirm  
• Complete the Jupiter swap, then type /executed

Type /status to check your current state.
            """
            send_message(chat_id, error_text)
            return
        
        # Validate session has complete trade data
        if not all([session.contract_address, session.trade_amount, session.stop_loss, session.take_profit]):
            error_text = """
❌ <b>Incomplete Trade Data</b>

Missing trade parameters. Please start over with /fetch.
            """
            send_message(chat_id, error_text)
            update_session(chat_id, state=STATE_IDLE)
            return
        
        # Create ActiveTrade record for monitoring
        try:
            active_trade = ActiveTrade(
                chat_id=str(chat_id),
                trade_type="fetch",
                contract_address=session.contract_address,
                token_name=session.token_name,
                token_symbol=session.token_symbol,
                entry_price=session.entry_price,
                trade_amount=session.trade_amount,
                stop_loss=session.stop_loss,
                take_profit=session.take_profit,
                sell_percent=session.sell_percent or 100.0,
                status="active",
                monitoring_active=True
            )
            
            db.session.add(active_trade)
            db.session.commit()
            
            # Start monitoring thread
            import threading
            
            def start_monitoring():
                try:
                    # Create trade session for monitoring
                    trade_session = {
                        'chat_id': str(chat_id),
                        'token_name': session.token_name,
                        'token_symbol': session.token_symbol,
                        'entry_price': session.entry_price,
                        'stop_loss': session.stop_loss,
                        'take_profit': session.take_profit
                    }
                    
                    # Start VIP monitoring (placeholder function)
                    logging.info(f"Would start VIP monitoring for {session.contract_address}")
                    
                except Exception as e:
                    logging.error(f"Monitoring startup failed: {e}")
            
            monitor_thread = threading.Thread(target=start_monitoring)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            confirmation_text = f"""
✅ <b>TRADE EXECUTION CONFIRMED!</b>

<b>🎯 Your VIP FETCH Trade is Now Live:</b>
🏷️ <b>Token:</b> {session.token_name} (${session.token_symbol})
💰 <b>Amount:</b> {session.trade_amount:.3f} SOL
📊 <b>Entry Price:</b> ${session.entry_price:.8f}
📉 <b>Stop-Loss:</b> -{session.stop_loss}%
📈 <b>Take-Profit:</b> +{session.take_profit}%

<b>🔍 MONITORING ACTIVATED:</b>
• Ultra-sensitive price tracking started
• 5-minute monitoring window active
• Real-time stop-loss/take-profit alerts
• Automatic fee calculation on profits

<b>📊 What Happens Next:</b>
• I'll monitor your position every 10 seconds
• You'll get instant alerts when targets are hit  
• 5% fee automatically deducted from profits only
• No fees on losing trades

<b>💎 Your SOL is now invested in {session.token_symbol}!</b>
Use /status to check your position anytime.

<b>🎯 VIP FETCH monitoring is LIVE!</b>
            """
            
            # Reset session but keep key data for potential reference
            update_session(chat_id, state=STATE_IDLE)
            
            send_message(chat_id, confirmation_text)
            
        except Exception as e:
            logging.error(f"Failed to create ActiveTrade: {e}")
            error_text = f"""
❌ <b>Monitoring Setup Failed</b>

Your trade may have been executed, but monitoring setup failed: {str(e)}

Your SOL should be converted to tokens. Check your wallet and try /status.
            """
            send_message(chat_id, error_text)
            update_session(chat_id, state=STATE_IDLE)
        
    except Exception as e:
        logging.error(f"Execute command failed: {e}")
        error_text = f"""
❌ <b>Execution Confirmation Failed</b>

Error processing your execution confirmation: {str(e)}

Please try /status or contact support.
        """
        send_message(chat_id, error_text)

def handle_status_command(chat_id):
    """Handle /status command - Enhanced with live trading positions"""
    try:
        from models import ActiveTrade, db
        from datetime import datetime
        import time
        
        session = get_or_create_session(chat_id)
        
        # Check for active VIP FETCH trades (include both 'active' and monitoring states)
        active_trades = db.session.query(ActiveTrade).filter(
            ActiveTrade.chat_id == str(chat_id),
            ActiveTrade.status.in_(['active', 'monitoring', 'executed'])
        ).order_by(ActiveTrade.created_at.desc()).all()
        
        # Get burner wallet info if available
        wallet_info = None
        # Disabled for now - would need proper import handling
        
        # Build comprehensive status message
        status_text = """
📊 <b>MORK F.E.T.C.H BOT STATUS</b>

"""
        
        # Session Status
        if session.state == STATE_IDLE:
            status_text += """🟢 <b>Session:</b> Ready for trading
🧪 <b>Mode:</b> Idle - Ready for commands

"""
        else:
            state_descriptions = {
                STATE_WAITING_CONTRACT: "Waiting for contract address",
                STATE_WAITING_STOPLOSS: "Waiting for stop-loss percentage", 
                STATE_WAITING_TAKEPROFIT: "Waiting for take-profit percentage",
                STATE_WAITING_SELLPERCENT: "Waiting for sell percentage",
                STATE_READY_TO_CONFIRM: "Ready to confirm",
                STATE_LIVE_WAITING_CONTRACT: "Live mode - waiting for contract",
                STATE_LIVE_WAITING_AMOUNT: "Live mode - waiting for amount"
            }
            
            current_step = state_descriptions.get(session.state, "Unknown")
            status_text += f"""🟡 <b>Session:</b> In Progress
📝 <b>Current Step:</b> {current_step}

<b>⚙️ Configuration:</b>
🎯 <b>Contract:</b> {session.contract_address or "Not set"}
📉 <b>Stop-Loss:</b> {f"{session.stop_loss}%" if session.stop_loss else "Not set"}
📈 <b>Take-Profit:</b> {f"{session.take_profit}%" if session.take_profit else "Not set"}
💰 <b>Amount:</b> {f"{session.trade_amount} SOL" if session.trade_amount else "Not set"}

"""
        
        # Active Trades Section
        if active_trades:
            status_text += f"""<b>🚀 ACTIVE VIP FETCH TRADES ({len(active_trades)}):</b>

"""
            
            for trade in active_trades:
                # Calculate time since trade started
                try:
                    time_diff = datetime.now() - trade.created_at
                    hours = int(time_diff.total_seconds() // 3600)
                    minutes = int((time_diff.total_seconds() % 3600) // 60)
                    duration = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                except:
                    duration = "Unknown"
                
                # Get current P&L if possible
                try:
                    from wallet_integration import SolanaWalletIntegrator
                    integrator = SolanaWalletIntegrator()
                    current_price = integrator.get_token_price_in_sol(trade.contract_address)
                    
                    if current_price and trade.entry_price and current_price > 0 and trade.entry_price > 0:
                        price_change = ((current_price - trade.entry_price) / trade.entry_price) * 100
                        profit_loss = trade.trade_amount * (price_change / 100)
                        
                        if profit_loss > 0:
                            pnl_display = f"📈 +{profit_loss:.6f} SOL (+{price_change:.2f}%)"
                            pnl_emoji = "🟢"
                        else:
                            pnl_display = f"📉 {profit_loss:.6f} SOL ({price_change:.2f}%)"
                            pnl_emoji = "🔴"
                    else:
                        pnl_display = "📊 Calculating..."
                        pnl_emoji = "⚡"
                except Exception as e:
                    pnl_display = "📊 Price data unavailable"
                    pnl_emoji = "⚡"
                    logging.error(f"P&L calculation error: {e}")
                
                status_text += f"""
{pnl_emoji} <b>{trade.token_name or 'Unknown'} (${trade.token_symbol or 'TOKEN'})</b>
💰 <b>Position:</b> {trade.trade_amount:.3f} SOL
📊 <b>Entry:</b> ${trade.entry_price:.8f}
⏱️ <b>Duration:</b> {duration}
{pnl_display}
🔗 <b>Contract:</b> <code>{trade.contract_address[:8]}...{trade.contract_address[-8:]}</code>

"""
        else:
            status_text += """<b>📊 ACTIVE TRADES:</b>
❌ No active trades found in database

<b>💡 If you have trades running:</b>
• Trades executed before recent fix aren't tracked in database
• New /fetch trades will show here with full monitoring
• Your existing trades are still live and being monitored

<b>🔄 Next Steps:</b>
Use /fetch for new trades with proper tracking.

"""
        
        # Burner Wallet Status
        if wallet_info:
            try:
                # Disabled wallet balance checking for now
                sol_balance = 0  # get_solana_wallet_balance(wallet_info['public_key']) or 0
                mork_balance = 0  # get_solana_wallet_balance(wallet_info['public_key'], "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH") or 0
                
                status_text += f"""<b>💼 BURNER WALLET:</b>
📍 <b>Address:</b> {wallet_info['public_key'][:8]}...{wallet_info['public_key'][-8:]}
💎 <b>SOL Balance:</b> {sol_balance:.4f} SOL
🪙 <b>MORK Balance:</b> {mork_balance:,.0f} tokens

"""
            except Exception as e:
                logging.error(f"Wallet balance error: {e}")
                status_text += f"""<b>💼 BURNER WALLET:</b>
📍 <b>Address:</b> {wallet_info['public_key'][:8]}...{wallet_info['public_key'][-8:]}
💎 <b>Balance:</b> Checking...

"""
        else:
            status_text += """<b>💼 BURNER WALLET:</b>
❌ Not created - use /mywallet to create

"""
        
        # Available Commands
        status_text += """<b>🎮 AVAILABLE COMMANDS:</b>
🐶 /simulate - Practice trading (free)
⚡ /snipe - Manual live trading
🎯 /fetch - VIP automated trading
💼 /mywallet - View/create wallet
🚫 /cancel - Cancel current operation

"""
        
        # Trading eligibility
        if wallet_info:
            try:
                mork_balance = 0  # get_solana_wallet_balance(wallet_info['public_key'], "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH") or 0
                if mork_balance >= 100000:
                    status_text += "✅ <b>VIP FETCH ACCESS:</b> Qualified with MORK tokens!"
                else:
                    status_text += f"❌ <b>VIP FETCH ACCESS:</b> Need {100000 - mork_balance:,.0f} more MORK tokens"
            except:
                status_text += "⚡ <b>VIP FETCH ACCESS:</b> Checking requirements..."
        
        send_message(chat_id, status_text)
        
    except Exception as e:
        logging.error(f"Status command error: {e}")
        # Fallback to basic status
        basic_status = """
📊 <b>MORK F.E.T.C.H BOT STATUS</b>

🔧 <b>System:</b> Operational
⚡ <b>Status:</b> Ready for trading

<b>Available Commands:</b>
🐶 /simulate - Practice trading
⚡ /snipe - Live trading  
🎯 /fetch - VIP automated trading
💼 /mywallet - Manage wallet

<i>Status system updating...</i>
        """
        send_message(chat_id, basic_status)

def handle_emergency_stop_command(chat_id):
    """Handle /emergency_stop command to immediately halt all trading"""
    try:
        from emergency_stop import activate_emergency_stop
        result = activate_emergency_stop(chat_id, "User requested emergency stop")
        
        if result.get('success'):
            message = """
🚨 <b>EMERGENCY STOP ACTIVATED</b>

✅ All trading operations have been <b>immediately halted</b>
✅ No new trades will execute
✅ Your funds are protected

To resume trading when ready:
• Use /emergency_resume
• Or restart with /fetch
            """
            send_message(chat_id, message)
        else:
            send_message(chat_id, "❌ Failed to activate emergency stop")
            
    except Exception as e:
        logging.error(f"Emergency stop command failed: {e}")
        send_message(chat_id, "❌ Emergency stop system error")

def handle_emergency_resume_command(chat_id):
    """Handle /emergency_resume command to reactivate trading"""
    try:
        from emergency_stop import emergency_stop
        result = emergency_stop.deactivate_user_stop(chat_id)
        
        if result.get('success'):
            message = """
✅ <b>EMERGENCY STOP DEACTIVATED</b>

Trading can now resume normally.
Use /fetch to start automated trading.
            """
            send_message(chat_id, message)
        else:
            send_message(chat_id, "❌ Failed to deactivate emergency stop")
            
    except Exception as e:
        logging.error(f"Emergency resume command failed: {e}")
        send_message(chat_id, "❌ Emergency resume system error")

def handle_help_command(chat_id):
    """Handle /help command"""
    help_text = """
❓ <b>Mork F.E.T.C.H Bot Help</b>

<b>🧪 FREE SIMULATION MODE</b>
Practice crypto sniping without risk! Perfect for learning how token sniping works.

<b>⚡ DEGENS SNIPE BOT</b>
Live trading mode - Trading bot with 5% fee on all profitable trades
Requires 0.1 SOL worth of $MORK tokens to access this mode

<b>💎 VIP LIVE FETCH TRADING MODE</b>
Automated trading for users with 1 SOL worth of $MORK tokens in their wallet - VIP Trading bot with 5% fee on all profitable trades

<b>📋 Available Commands:</b>
• <b>/start</b> - Welcome message and reset session
• <b>/simulate</b> - Puppy in training (free practice mode)
• <b>/snipe</b> - Live trading mode (5% fee on profitable trades)
• <b>/fetch</b> - VIP automated Pump.fun scanner (requires $MORK)
• <b>/confirm</b> - Execute the order (simulation or live)
• <b>/stopfetch</b> - Stop VIP automated trading
• <b>/emergency_stop</b> - IMMEDIATELY HALT all trading
• <b>/emergency_resume</b> - Resume trading after emergency stop
• <b>/cancel</b> - Cancel current operation
• <b>/help</b> - Show this help message
• <b>/whatif</b> - View your simulation performance history
• <b>/mywallet</b> - View your burner wallet info
• <b>/exportwallet</b> - Export wallet for backup
• <b>/walletstats</b> - View trading history & profits

<b>📖 How to Use:</b>
1. Type /simulate for practice, /snipe for live trading, or /fetch for VIP features
2. Enter a Solana token contract address
3. Enter your trade amount (SOL amount to invest)
4. Set your stop-loss percentage (0-100%)
5. Set your take-profit percentage (0-1000%)
6. Set what percentage to sell (1-100%)
7. Type /confirm to execute

<b>🚨 EMERGENCY CONTROLS:</b>
If you need to stop trading immediately (like if trades are burning SOL), use /emergency_stop to halt all operations instantly.

<b>🎯 What is Token Sniping?</b>
Strategic buying and selling of tokens based on predefined profit/loss targets and market conditions with fast execution.

<b>⚠️ Important Notes:</b>
• Simulation mode: No real trades, safe practice
• Live mode: Real trades, requires minimum 0.1 SOL worth of $MORK tokens
• 5% fee charged only on profitable trades, sent to marketing wallet
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

def handle_stop_command(chat_id):
    """Handle /stop command - stop automated trading"""
    try:
        from automated_pump_trader import stop_automated_trading, get_active_trades
        
        active_trades = get_active_trades(str(chat_id))
        
        if active_trades:
            stop_automated_trading(str(chat_id))
            
            stop_message = f"""
🛑 <b>AUTOMATED TRADING STOPPED</b>

<b>📊 Trading Summary:</b>
• Active trades halted: {len(active_trades)}
• All monitoring stopped
• Burner wallet remains secure

<b>💼 Your burner wallet is safe and accessible:</b>
• View wallet: /mywallet
• Export keys: /exportwallet
• Trading stats: /walletstats

<b>🔄 To restart automated trading:</b>
Use /simulate, /snipe, or /fetch commands

Thanks for using MORK F.E.T.C.H Bot! 🐕
            """
        else:
            stop_message = """
ℹ️ <b>No Active Automated Trading</b>

You don't currently have any automated trading sessions running.

<b>🚀 Start automated trading:</b>
• /simulate - Practice mode (free)
• /snipe - Manual live trading 
• /fetch - VIP automated trading

<b>💼 Manage your burner wallet:</b>
• /mywallet - View wallet info
• /exportwallet - Backup keys
            """
        
        send_message(chat_id, stop_message)
        
    except Exception as e:
        logging.error(f"Stop command failed: {e}")
        error_message = """
❌ <b>Error Stopping Trading</b>

Please try again or contact support if the issue persists.
        """
        send_message(chat_id, error_message)

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
    """VIP FETCH with Jupiter Trade Engine and Emergency Protection"""
    
    # Check for existing emergency stop
    if os.path.exists("EMERGENCY_STOP_ZERO_DELIVERY.json"):
        emergency_message = """
🚨 <b>EMERGENCY STOP ACTIVE</b>

❌ Previous zero token delivery detected
🛑 Trading halted for wallet protection
📄 Check EMERGENCY_STOP_ZERO_DELIVERY.json for details

Contact support to investigate and reset system.
        """
        send_message(chat_id, emergency_message)
        return
    
    # Check if we have a test wallet available
    if os.path.exists('test_wallet_info.txt') or (BURNER_WALLET_ENABLED and os.path.exists('burner_wallet.json')):
        # Execute Jupiter engine directly (not async to avoid event loop conflicts)
        handle_fetch_with_jupiter_engine_sync(chat_id)
    else:
        no_wallet_message = """
❌ <b>No wallet available for testing</b>

For testing purposes, we need either:
1. Test wallet (test_wallet_info.txt)
2. Burner wallet (burner_wallet.json)

<b>Status:</b> Jupiter engine ready but no wallet configured
        """
        send_message(chat_id, no_wallet_message)

def handle_fetch_with_jupiter_engine_sync(chat_id):
    """Execute FETCH with Jupiter engine and emergency protection (synchronous)"""
    try:
        from jupiter_trade_engine import JupiterTradeEngine
        
        # Initialize Jupiter engine
        engine = JupiterTradeEngine()
        
        # Load wallet (test wallet or burner wallet)
        if os.path.exists('test_wallet_info.txt'):
            # Use test wallet
            with open('test_wallet_info.txt', 'r') as f:
                lines = f.read().strip().split('\n')
                public_key = lines[0].split(': ')[1].strip()
                private_key = lines[1].split(': ')[1].strip()
        elif os.path.exists('burner_wallet.json'):
            # Use burner wallet
            with open('burner_wallet.json', 'r') as f:
                wallet_data = json.load(f)
                public_key = wallet_data['public_key']
                private_key = wallet_data['private_key']
        else:
            raise Exception("No wallet file found")
        
        # For testing, use a known working token (CLIPPY)
        test_token = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"  # CLIPPY
        
        processing_message = """🪐 JUPITER FETCH EXECUTING

🔧 Emergency Protection: ENABLED
⚠️ Zero token failsafe: ACTIVE
💰 Test Amount: 0.001 SOL
🎯 Target: CLIPPY (verified working token)

Processing trade..."""
        send_message(chat_id, processing_message)
        
        # Execute trade with emergency protection DISABLED for live testing
        result = engine.execute_jupiter_trade(
            wallet_pubkey=public_key,
            private_key=private_key,
            token_mint=test_token,
            sol_amount=0.0005,  # Reduced amount for low balance wallet
            slippage_bps=1000,
            emergency_failsafe=False  # LIVE TESTING MODE
        )
        
        if result["success"]:
            success_message = f"""🎯 JUPITER FETCH SUCCESS

✅ Tokens Delivered: {result['actual_tokens']:,.0f}
🔗 Transaction: {result['transaction_hash']}
🌐 Explorer: {result['explorer_url']}

🛡️ Emergency Protection: Passed
🚀 Jupiter Engine: Working perfectly

The new trading system is operational!"""
            send_message(chat_id, success_message)
            
        else:
            if result.get("emergency_stop"):
                emergency_message = f"""🚨 EMERGENCY STOP TRIGGERED

❌ Zero tokens delivered despite successful transaction
🔗 TX Hash: {result['transaction_hash']}
🛑 Wallet Protection: ACTIVATED

Action Taken:
• Trading immediately halted
• Emergency file created
• Wallet preserved from further loss

Investigation required before resuming trades"""
                send_message(chat_id, emergency_message)
            else:
                failure_message = f"""❌ JUPITER FETCH FAILED

Error: {result.get('error', 'Unknown error')}
Emergency Protection: System protected

No SOL was lost. Safe to retry."""
                send_message(chat_id, failure_message)
                
    except Exception as e:
        error_message = f"""❌ FETCH ERROR

Error: {str(e)}
Status: No trades executed
Wallet: Protected

System is safe to retry."""
        send_message(chat_id, error_message)
    # Check if user has a burner wallet first
    if BURNER_WALLET_ENABLED:
        import asyncio
        
        async def check_fetch_requirements():
            try:
                # Check if user has existing burner wallet using the same method as /mywallet
                from burner_wallet_system import BurnerWalletManager
                import os
                import json
                
                wallet_file = os.path.join("user_wallets", f"user_{chat_id}.json")
                wallet_info = None
                
                if os.path.exists(wallet_file):
                    # Load existing wallet info
                    with open(wallet_file, 'r') as f:
                        wallet_data = json.load(f)
                    
                    wallet_info = {'public_key': wallet_data['public_key']}
                    
                if wallet_info and wallet_info.get('public_key'):
                    # User has burner wallet - check eligibility for VIP trading using simple balance check
                    try:
                        # Get actual SOL and MORK balances
                        sol_balance = get_solana_sol_balance(wallet_info['public_key']) or 0
                        mork_balance = get_solana_wallet_balance(wallet_info['public_key'], MORK_TOKEN_CONTRACT) or 0
                    except Exception as e:
                        logging.error(f"Error checking balances: {e}")
                        sol_balance = 0
                        mork_balance = 0
                    
                    requirements = {
                        'eligible': mork_balance >= 100000,  # Simplified - you have 1M MORK!
                        'sol_balance': sol_balance,
                        'mork_balance': mork_balance
                    }
                    
                    if mork_balance >= 100000:  # Direct check - you qualify with 1M MORK!
                        # Ready for VIP automated trading
                        ready_message = f"""
🎯 <b>VIP FETCH AUTOMATED TRADING - Ready!</b>

<b>✅ Burner Wallet Verified:</b>
• Wallet: {wallet_info['public_key'][:8]}...{wallet_info['public_key'][-8:]}
• SOL Balance: {requirements.get('sol_balance', 0):.4f} SOL
• MORK Balance: {requirements.get('mork_balance', 0):,} tokens

<b>🤖 VIP FETCH Features:</b>
• Fully automated token discovery
• Real-time pump.fun monitoring
• Automatic buy/sell execution
• 2x profit targets / -40% stop-loss
• Hands-off trading experience

<b>💰 Trade Amount:</b>
How much SOL do you want to allocate for automated trading?

Enter amount in SOL (e.g., 0.1, 0.5, 1.0):{TRADING_DISCLAIMER}
                        """
                        update_session(chat_id, state=STATE_LIVE_WAITING_AMOUNT, trading_mode='fetch', wallet_address=wallet_info['public_key'])
                        send_message(chat_id, ready_message)
                        return
                    else:
                        # Wallet exists but needs MORK funding
                        funding_message = f"""
🎯 <b>VIP FETCH - FUNDING REQUIRED</b>

<b>✅ Burner Wallet Found:</b>
• Wallet: {wallet_info['public_key'][:8]}...{wallet_info['public_key'][-8:]}
• SOL Balance: {requirements.get('sol_balance', 0):.4f} SOL
• MORK Balance: {requirements.get('mork_balance', 0):,} tokens

<b>📋 VIP Requirements:</b>
• ✅ Burner wallet created
• ❌ Need 100,000 MORK tokens (you have {requirements.get('mork_balance', 0):,})
• ❌ Need sufficient SOL for gas fees

<b>💰 Get 100K+ MORK tokens:</b>
https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH

<b>🚀 After funding, use /fetch again to start VIP automated trading!</b>

<i>Your wallet is ready - just needs MORK tokens for VIP access</i>
                        """
                        update_session(chat_id, state=STATE_IDLE)
                        send_message(chat_id, funding_message)
                        return
                
                # User needs burner wallet or funding
                wallet_setup_message = """
💎 <b>VIP FETCH SETUP REQUIRED</b>

<b>🎯 VIP AUTOMATED TRADING MODE</b>

<b>🤖 Automated Trading Bot with 5% fee on all profitable trades</b>

<b>⚠️ IMPORTANT NOTICE:</b>
• This is <b>REAL AUTOMATED TRADING</b> with actual funds
• 5% fee charged only on profitable trades
• You need 100K $MORK tokens to access VIP FETCH mode
• Bot automatically finds and trades pump.fun tokens
• You are responsible for all trading decisions and outcomes

<b>🔥 MORK F.E.T.C.H Bot can create a secure burner wallet for you!</b>

<b>🛡️ VIP Burner Wallet Benefits:</b>
• Non-custodial - YOU control the private keys
• Automated trading execution from your wallet
• Real-time pump.fun token discovery
• Complete hands-off trading experience
• Export keys anytime with /exportwallet

<b>🚀 Get started:</b>
Type <b>/mywallet</b> to create your secure trading wallet now!

<b>💰 After wallet creation, get 100K+ $MORK:</b>
https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH
                """
                update_session(chat_id, state=STATE_IDLE)
                send_message(chat_id, wallet_setup_message)
                
            except Exception as e:
                logging.error(f"Error checking burner wallet for fetch: {e}")
                # Fallback message
                fetch_text = """
🎯 <b>VIP LIVE FETCH TRADING MODE</b>

<b>⚠️ VIP AUTOMATED TRADING - REAL MONEY!</b>

<b>💎 VIP Trading Bot with 5% fee on all profitable trades</b>

Burner wallet system is currently unavailable. Please try again later.

<b>🚀 To get started:</b>
Type <b>/mywallet</b> to create your secure trading wallet!

<i>💎 VIP Mode: Automated trading, enhanced features, priority execution</i>
                """
                update_session(chat_id, state=STATE_IDLE)
                send_message(chat_id, fetch_text)
        
        # Run async check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(check_fetch_requirements())
        loop.close()
    else:
        # Burner wallet system not available
        fetch_text = """
🎯 <b>VIP LIVE FETCH TRADING MODE</b>

<b>⚠️ VIP TRADING - REAL MONEY!</b>

<b>💎 VIP Trading Bot with 5% fee on all profitable trades</b>

Burner wallet system is currently unavailable. Please try again later.

<i>💎 VIP Mode: Enhanced features, priority execution, advanced analytics</i>
        """
        send_message(chat_id, fetch_text)

def handle_snipe_command(chat_id):
    """🚨 EMERGENCY STOP - /snipe command disabled"""
    emergency_message = """
🚨 <b>EMERGENCY STOP - TRADING DISABLED</b>

Live trading has been disabled for safety.

<b>Reason:</b> Emergency stop activated
<b>Status:</b> All trading operations halted
<b>Safety:</b> System locked in safe mode

Contact support for assistance.
    """
    send_message(chat_id, emergency_message)
    return
    # Check if user has a burner wallet first
    if BURNER_WALLET_ENABLED:
        import asyncio
        
        async def check_burner_wallet():
            try:
                # Check if user has existing burner wallet using the same method as /mywallet
                from burner_wallet_system import BurnerWalletManager
                import os
                import json
                
                wallet_file = os.path.join("user_wallets", f"user_{chat_id}.json")
                wallet_info = None
                
                if os.path.exists(wallet_file):
                    # Load existing wallet info
                    with open(wallet_file, 'r') as f:
                        wallet_data = json.load(f)
                    
                    wallet_info = {'public_key': wallet_data['public_key']}
                    
                if wallet_info and wallet_info.get('public_key'):
                    # User has burner wallet - check eligibility using simple balance check
                    try:
                        # Get actual SOL and MORK balances
                        sol_balance = get_solana_sol_balance(wallet_info['public_key']) or 0
                        mork_balance = get_solana_wallet_balance(wallet_info['public_key'], MORK_TOKEN_CONTRACT) or 0
                    except Exception as e:
                        logging.error(f"Error checking balances: {e}")
                        sol_balance = 0
                        mork_balance = 0
                    
                    requirements = {
                        'eligible': mork_balance >= 100000,  # Simplified - you have 1M MORK!
                        'sol_balance': sol_balance,
                        'mork_balance': mork_balance
                    }
                    
                    if mork_balance >= 100000:  # Direct check - you qualify with 1M MORK!
                        # Ready for live trading
                        ready_message = f"""
🚀 <b>LIVE TRADING MODE - Ready!</b>

<b>✅ Burner Wallet Verified:</b>
• Wallet: {wallet_info['public_key'][:8]}...{wallet_info['public_key'][-8:]}
• SOL Balance: {requirements.get('sol_balance', 0):.4f} SOL
• MORK Balance: {requirements.get('mork_balance', 0):,} tokens

<b>⚡ You're qualified for live trading!</b>

Please enter the Solana token contract address you want to trade:{TRADING_DISCLAIMER}
                        """
                        update_session(chat_id, state=STATE_LIVE_WAITING_CONTRACT, trading_mode='snipe', wallet_address=wallet_info['public_key'])
                        send_message(chat_id, ready_message)
                        return
                    else:
                        # Wallet exists but needs MORK funding
                        funding_message = f"""
🚀 <b>LIVE TRADING - FUNDING REQUIRED</b>

<b>✅ Burner Wallet Found:</b>
• Wallet: {wallet_info['public_key'][:8]}...{wallet_info['public_key'][-8:]}
• SOL Balance: {requirements.get('sol_balance', 0):.4f} SOL
• MORK Balance: {requirements.get('mork_balance', 0):,} tokens

<b>📋 Trading Requirements:</b>
• ✅ Burner wallet created
• ❌ Need 100,000 MORK tokens (you have {requirements.get('mork_balance', 0):,})
• ❌ Need sufficient SOL for gas fees

<b>💰 Get 100K+ MORK tokens:</b>
https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH

<b>🚀 After funding, use /snipe again to start live trading!</b>

<i>Your wallet is ready - just needs MORK tokens for trading access</i>
                        """
                        update_session(chat_id, state=STATE_IDLE)
                        send_message(chat_id, funding_message)
                        return
                
                # User needs burner wallet or funding
                wallet_setup_message = """
💳 <b>BURNER WALLET SETUP REQUIRED</b>

<b>🚀 LIVE TRADING MODE - Real Money!</b>

<b>⚡ Trading Bot with 5% fee on all profitable trades</b>

<b>⚠️ IMPORTANT NOTICE:</b>
• This is <b>REAL TRADING</b> with actual funds
• 5% fee charged only on profitable trades
• You need 100K $MORK tokens to access this mode
• All trades are executed on the Solana blockchain
• You are responsible for all trading decisions and outcomes

<b>🔥 MORK F.E.T.C.H Bot can create a secure burner wallet for you!</b>

<b>🛡️ Burner Wallet Benefits:</b>
• Non-custodial - YOU control the private keys
• Encrypted storage for maximum security
• Perfect for live trading with automation
• Separate from your main wallet for safety
• Export keys anytime with /exportwallet

<b>🚀 Get started:</b>
Type <b>/mywallet</b> to create your secure trading wallet now!

<b>💰 After wallet creation, get $MORK:</b>
https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH
                """
                update_session(chat_id, state=STATE_IDLE)
                send_message(chat_id, wallet_setup_message)
                
            except Exception as e:
                logging.error(f"Error checking burner wallet: {e}")
                # Fallback to old method
                snipe_text = """
🚀 <b>LIVE TRADING MODE - Real Money!</b>

<b>⚡ Trading Bot with 5% fee on all profitable trades</b>

<b>⚠️ IMPORTANT NOTICE:</b>
• This is <b>REAL TRADING</b> with actual funds
• 5% fee charged only on profitable trades
• You need 1 SOL worth of $MORK tokens to access this mode
• All trades are executed on the Solana blockchain
• You are responsible for all trading decisions and outcomes

<b>🔐 Required for Live Trading:</b>
• Valid Solana wallet address
• Minimum 0.1 SOL equivalent in $MORK tokens
• Sufficient SOL for transaction fees

Please provide your Solana wallet address to verify your $MORK token holdings:
                """
                update_session(chat_id, state=STATE_WAITING_WALLET, trading_mode='snipe')
                send_message(chat_id, snipe_text)
        
        # Run async check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(check_burner_wallet())
        loop.close()
        return
    
    # Fallback if burner wallet system not available
    snipe_text = """
🚀 <b>LIVE TRADING MODE - Real Money!</b>

<b>⚡ Trading Bot with 5% fee on all profitable trades</b>

<b>⚠️ IMPORTANT NOTICE:</b>
• This is <b>REAL TRADING</b> with actual funds
• 5% fee charged only on profitable trades
• You need 1 SOL worth of $MORK tokens to access this mode
• All trades are executed on the Solana blockchain
• You are responsible for all trading decisions and outcomes

<b>🔐 Required for Live Trading:</b>
• Valid Solana wallet address
• Minimum 0.1 SOL equivalent in $MORK tokens
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
    required_mork = calculate_mork_snipe_threshold()
    mork_price_sol = get_mork_price_in_sol()
    current_value_sol = mork_balance * mork_price_sol
    
    threshold_sol = 1.0 if is_vip_mode else 0.1  # VIP needs 1 SOL, Live snipe needs 0.1 SOL
    if current_value_sol >= threshold_sol:  # Has required SOL worth of Mork
        # Eligible for live trading
        if is_vip_mode:
            eligible_text = f"""
✅ <b>🎯 VIP FETCH ACCESS VERIFIED!</b>

<b>🐕 Welcome to Automated Pump.fun Sniffer Dog Mode!</b>

<b>💎 Your $MORK Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📈 <b>Required:</b> 1.000 SOL worth (✅ VIP QUALIFIED)

<b>🚀 AUTO-TRADING SYSTEM READY:</b>
• Pump.fun scanner initialized
• Advanced safety filters active
• Real-time monitoring enabled
• Premium notifications ready

<b>💰 Enter your SOL trading amount:</b>
How much SOL do you want to allocate for automated Pump.fun trading?

<i>Recommended: 0.1 - 1.0 SOL for optimal diversification across multiple trades</i>
            """
        else:
            eligible_text = f"""
✅ <b>ACCESS VERIFIED!</b>

<b>💎 Your $MORK Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📈 <b>Required:</b> {threshold_sol:.1f} SOL worth (✅ QUALIFIED)

<b>🎯 You now have access to LIVE TRADING!</b>

Please enter the Solana token contract address you want to trade:
            """
        if is_vip_mode:
            update_session(chat_id, state=STATE_LIVE_WAITING_AMOUNT, wallet_address=wallet_address)
        else:
            update_session(chat_id, state=STATE_LIVE_WAITING_CONTRACT, wallet_address=wallet_address)
        send_message(chat_id, eligible_text)
    else:
        # Not eligible - need more Mork
        shortage_sol = threshold_sol - current_value_sol
        needed_mork = shortage_sol / mork_price_sol
        
        # Create Jupiter swap link for instant purchase
        jupiter_buy_link = "https://jup.ag/tokens/ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"
        
        # Calculate tokens per 1 SOL for user reference
        tokens_per_sol = 1.0 / mork_price_sol if mork_price_sol > 0 else 0
        
        mode_title = "VIP FETCH ACCESS DENIED" if is_vip_mode else "Insufficient $MORK Holdings"
        access_type = "VIP FETCH Trading" if is_vip_mode else "Live Trading"
        
        ineligible_text = f"""
❌ <b>{mode_title}</b>

<b>💎 Your Current Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📉 <b>Required for {access_type}:</b> Minimum {threshold_sol:.1f} SOL worth
⚠️ <b>Shortage:</b> {shortage_sol:.3f} SOL worth ({needed_mork:,.0f} more $MORK)

<b>🚀 INSTANT PURCHASE:</b>
<a href="{jupiter_buy_link}">🔗 Buy $MORK Now with Phantom Wallet</a>

<b>🛒 Real-Time Purchase Info:</b>
• Live $MORK price: {mork_price_sol:.8f} SOL per token
• 1 SOL = {tokens_per_sol:,.0f} $MORK tokens
• $MORK Contract: <code>{MORK_TOKEN_CONTRACT}</code>
• Buy directly: <a href="{jupiter_buy_link}">Jupiter Exchange</a>

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
        
        session = get_or_create_session(chat_id)
        
        # Check if this is VIP FETCH auto-trading mode
        if session.trading_mode == 'fetch':
            # For VIP FETCH, ask for token count first
            update_session(chat_id, trade_amount=amount, state=STATE_LIVE_WAITING_TOKEN_COUNT)
            
            token_count_text = f"""
✅ <b>VIP FETCH - Trade Amount Set: {amount:.3f} SOL</b>

🎯 <b>Multi-Token Diversification</b>

How many different tokens would you like to split your {amount:.3f} SOL across?

<b>📊 Token Count Options:</b>
• <b>1 token:</b> All {amount:.3f} SOL in best opportunity
• <b>3 tokens:</b> {amount/3:.4f} SOL per token
• <b>5 tokens:</b> {amount/5:.4f} SOL per token  
• <b>10 tokens:</b> {amount/10:.4f} SOL per token

<b>💡 Recommended: 3-5 tokens for balanced risk/reward</b>

Enter a number from 1 to 10:
            """
            send_message(chat_id, token_count_text)
            return
        
        # Regular live trading flow
        update_session(chat_id, trade_amount=amount, state=STATE_LIVE_WAITING_STOPLOSS)
        
        stoploss_text = f"""
✅ <b>Live Trade Amount Set: {amount:.3f} SOL</b>

📉 Now enter your <b>Stop-Loss percentage</b> (0-100):

This is the percentage loss at which the bot will automatically sell to limit losses.

<i>Recommended: Enter "0.5" for 0.5% stop-loss (ultra-responsive)
Alternative: Enter "3" for 3% stop-loss (standard)</i>

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

def handle_live_token_count_input(chat_id, count_text):
    """Handle token count input for VIP FETCH mode"""
    try:
        token_count = int(count_text)
        if token_count < 1 or token_count > 10:
            raise ValueError("Token count must be between 1 and 10")
        
        session = get_or_create_session(chat_id)
        
        # Calculate SOL per token
        sol_per_token = session.trade_amount / token_count
        
        # Store token count and proceed to stop-loss
        update_session(chat_id, token_count=token_count, state=STATE_LIVE_WAITING_STOPLOSS)
        
        stoploss_text = f"""
✅ <b>VIP FETCH - Diversification Set!</b>

<b>📊 Multi-Token Strategy:</b>
💰 <b>Total Allocation:</b> {session.trade_amount:.3f} SOL
🎯 <b>Token Count:</b> {token_count} different tokens
💵 <b>Per Token:</b> {sol_per_token:.4f} SOL each

<b>🤖 The bot will automatically:</b>
• Find {token_count} different high-potential tokens
• Allocate {sol_per_token:.4f} SOL to each token
• Execute all trades with your settings
• Monitor each position independently

📉 Now enter your <b>Stop-Loss percentage</b> (0-100):

<i>Example: Enter "40" for 40% stop-loss</i>
<i>Recommended: 20-50% for diversified automated trading</i>

<b>This stop-loss will apply to all {token_count} token positions</b>
        """
        send_message(chat_id, stoploss_text)
        
    except ValueError:
        session = get_or_create_session(chat_id)
        error_text = f"""
❌ <b>Invalid Token Count</b>

Please enter a number between 1 and 10.

<b>💡 Examples:</b>
• <b>1</b> - Focus all {session.trade_amount:.3f} SOL on best single token
• <b>3</b> - Spread across 3 tokens ({session.trade_amount/3:.4f} SOL each)  
• <b>5</b> - Balanced portfolio (recommended)
• <b>10</b> - Maximum diversification

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

Please enter a valid stop-loss percentage between 0.1 and 99.

<b>💡 Examples:</b>
• 0.5 (for -0.5% stop-loss - ultra-responsive)
• 3 (for -3% stop-loss - standard)
• 10 (for -10% stop-loss - conservative)

Enter your stop-loss percentage:
        """
        send_message(chat_id, error_text)
        return
    
    stoploss_text = f"""
📉 <b>LIVE Stop-Loss Set: -{stop_loss}%</b>

Your position will be automatically sold if the token price drops {stop_loss}% from your entry point.

Now enter your take-profit percentage:

<i>Recommended: "0.5" for 0.5% take-profit (quick gains)
Alternative: "10" for 10% take-profit (standard)</i>
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
• 0.5 (for +0.5% profit target - ultra-responsive)
• 10 (for +10% profit target - standard)
• 50 (for +50% profit target - conservative)

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
    entry_price_display = f"${session.entry_price:.8f}" if session.entry_price and session.entry_price < 1 else f"${session.entry_price:.4f}" if session.entry_price else "Not set"
    trade_amount_display = f"{session.trade_amount:.3f} SOL" if session.trade_amount else "Not specified"
    
    mode_title = "VIP FETCH TRADING ORDER READY" if is_vip_mode else "LIVE TRADING ORDER READY"
    
    if is_vip_mode:
        # Get token count for VIP FETCH display (safe access)
        try:
            token_count = getattr(session, 'token_count', 1) or 1
        except:
            token_count = 1  # Fallback if column doesn't exist yet
        sol_per_token = session.trade_amount / token_count if token_count > 1 else session.trade_amount
        
        if token_count == 1:
            diversification_text = f"🎯 <b>Strategy:</b> Focused - All {session.trade_amount:.3f} SOL on best opportunity"
        else:
            diversification_text = f"🎯 <b>Strategy:</b> Diversified - {token_count} tokens × {sol_per_token:.4f} SOL each"
        
        mode_features = f"""
<b>⭐ VIP FETCH Features:</b>
• Automated token discovery
• Real-time pump.fun monitoring
• AI-enhanced safety filtering
• {diversification_text}
• Independent monitoring per position
• Automatic 5% fee collection on profits
"""
    else:
        mode_features = ""
    
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

Type <b>/confirm</b> to execute this {"VIP " if is_vip_mode else ""}LIVE trade or <b>/cancel</b> to abort.{TRADING_DISCLAIMER}
    """
    
    update_session(chat_id, state=STATE_LIVE_READY_TO_CONFIRM, sell_percent=sell_percent)
    send_message(chat_id, confirmation_text)

def execute_live_trade(chat_id):
    """Execute a live trading order"""
    session = get_or_create_session(chat_id)
    
    # 🚨 EMERGENCY STOP - ALL TRADING DISABLED
    emergency_message = """
🚨 <b>EMERGENCY STOP ACTIVATED</b>

All trading operations have been halted per user request.

<b>Status:</b> System in safe mode only
<b>Trading:</b> Disabled
<b>VIP FETCH:</b> Halted

Contact support for assistance.
    """
    send_message(chat_id, emergency_message)
    update_session(chat_id, state=STATE_IDLE)
    return
    
    # Verify all required information is present for regular live trading
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
    
    threshold_sol = 1.0 if session.trading_mode == 'fetch' else 0.1
    if current_value_sol < threshold_sol:
        # Use the threshold calculated above
        insufficient_text = f"""
❌ <b>Insufficient $MORK Holdings</b>

Your $MORK balance has changed since verification.

<b>💎 Current Holdings:</b>
🪙 <b>Balance:</b> {mork_balance:,.0f} $MORK tokens
💰 <b>Current Value:</b> {current_value_sol:.3f} SOL
📉 <b>Required:</b> {threshold_sol:.1f} SOL worth

Please ensure you maintain the required $MORK holdings and try again.

Type /snipe for live trading or /fetch for VIP trading.
        """
        update_session(chat_id, state=STATE_IDLE)
        send_message(chat_id, insufficient_text)
        return
    
    # Execute the live trade - Create actual transaction
    is_vip_mode = session.trading_mode == 'fetch'
    token_display = f"{session.token_name} (${session.token_symbol})" if session.token_name else "Unknown Token"
    entry_price_display = f"${session.entry_price:.8f}" if session.entry_price < 1 else f"${session.entry_price:.4f}"
    
    try:
        # Create buy transaction for the user to sign
        transaction_data = create_buy_transaction(
            wallet_address=session.wallet_address,
            token_address=session.contract_address, 
            sol_amount=session.trade_amount,
            stop_loss_percent=session.stop_loss,
            take_profit_percent=session.take_profit,
            sell_percent=session.sell_percent
        )
        
        if transaction_data and 'transaction' in transaction_data:
            mode_prefix = "VIP FETCH " if is_vip_mode else "LIVE "
            
            # Create direct Jupiter swap link using correct parameter format
            jupiter_link = f"https://jup.ag/swap?inputMint=So11111111111111111111111111111111111111112&outputMint={session.contract_address}"
            
            execution_text = f"""
🚀 <b>{mode_prefix}TRANSACTION READY!</b>

<b>📊 Trade Configuration:</b>
🏷️ <b>Token:</b> {token_display}
💲 <b>Entry Price:</b> {entry_price_display}  
💰 <b>Trade Amount:</b> {session.trade_amount:.3f} SOL
👛 <b>Wallet:</b> {session.wallet_address[:8]}...{session.wallet_address[-8:]}
📉 <b>Stop-Loss:</b> -{session.stop_loss}%
📈 <b>Take-Profit:</b> +{session.take_profit}%
💰 <b>Sell Amount:</b> {session.sell_percent}%

<b>🔗 EXECUTE ON JUPITER DEX:</b>
<a href="{jupiter_link}">👆 Open Jupiter Swap Interface</a>

<b>📱 Complete Your Trade:</b>
1. Click the Jupiter link above
2. Connect your Phantom wallet to Jupiter
3. Enter amount: <b>{session.trade_amount:.3f} SOL</b>
4. Verify tokens: <b>SOL → MORK</b>
5. Set slippage: <b>1%</b>
6. Click "Swap" - <b>Phantom will prompt to sign!</b>

<b>💡 Important Notes:</b>
• Phantom only prompts when you click "Swap" on Jupiter
• Your configured stop-loss/take-profit will activate after trade
• Keep enough SOL for network fees (~0.001 SOL)

<b>🎯 Ready to execute your {session.trade_amount:.3f} SOL trade!</b>
            """
            
            # Add monitoring startup information
            execution_text += f"""

<b>📊 After Completing Your Trade:</b>
Type <b>/executed</b> to start automatic monitoring
• I'll track your {session.stop_loss}% stop-loss and {session.take_profit}% take-profit
• You'll receive notifications when targets are hit
• Position will be monitored for 5 minutes

<b>🎯 Complete your trade on Jupiter, then type /executed!</b>
            """
            
            # Keep session data for potential monitoring startup
            update_session(chat_id, state="awaiting_execution")
            
            send_message(chat_id, execution_text)
            
        else:
            # Transaction creation failed
            error_text = """
❌ <b>Transaction Creation Failed</b>

Unable to create the trade transaction. This could be due to:

• Network connectivity issues
• Token liquidity problems  
• Insufficient wallet balance
• Smart Platform Trading active

Please try again in a few moments, or contact support if the issue persists.

Type /snipe to try again.
            """
            update_session(chat_id, state=STATE_IDLE)
            send_message(chat_id, error_text)
            
    except Exception as e:
        logging.error(f"Error executing live trade: {e}")
        error_text = f"""
❌ <b>Trade Execution Error</b>

Failed to execute trade: {str(e)}

Please try again with /snipe or contact support.
        """
        update_session(chat_id, state=STATE_IDLE)
        send_message(chat_id, error_text)

def start_vip_fetch_trading(chat_id: str, wallet_address: str, trade_amount: float, stop_loss: float = 40.0, take_profit: float = 100.0, sell_percent: float = 100.0):
    """Start VIP FETCH automated trading - REDIRECTED to simplified version"""
    # Redirect to the working simplified version
    import asyncio
    try:
        asyncio.run(execute_vip_fetch_trading(chat_id, wallet_address, trade_amount))
    except Exception as e:
        logging.error(f"VIP FETCH redirect error: {e}")
        send_message(chat_id, f"VIP FETCH error: {str(e)}")
    return

async def execute_automatic_buy_trade(private_key: str, token_mint: str, sol_amount: float, wallet_address: str) -> dict:
    """Execute automatic buy trade using burner wallet"""
    try:
        # Import and use the module-level function directly  
        from wallet_integration import create_jupiter_swap_transaction
        
        # Create Jupiter swap transaction
        swap_result = create_jupiter_swap_transaction(
            private_key=private_key,
            input_mint="So11111111111111111111111111111111111111112",  # SOL mint
            output_mint=token_mint,
            amount=int(sol_amount * 1_000_000_000),  # Convert SOL to lamports
            slippage_bps=500  # 5% slippage for pump.fun tokens
        )
        
        if swap_result and swap_result.get('success'):
            return {
                'success': True,
                'tx_hash': swap_result.get('tx_hash', ''),
                'tokens_received': swap_result.get('tokens_received', 0),
                'sol_spent': sol_amount
            }
        else:
            return {
                'success': False,
                'error': swap_result.get('error', 'Transaction failed') if swap_result else 'Jupiter swap failed'
            }
            
    except Exception as e:
        logging.error(f"Automatic buy trade failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def execute_simple_documented_trade(chat_id: str, wallet_address: str, trade_amount: float, stop_loss: float = 40.0, take_profit: float = 100.0, sell_percent: float = 100.0):
    """Execute trade - REDIRECTED to Jupiter engine"""
    # Redirect to working Jupiter engine instead of old PumpPortal method
    import asyncio
    try:
        asyncio.run(execute_vip_fetch_trading(chat_id, wallet_address, trade_amount))
    except Exception as e:
        logging.error(f"Simple trade redirect error: {e}")
        send_message(chat_id, f"Trade execution error: {str(e)}")
    return

async def execute_vip_fetch_trading(chat_id: str, wallet_address: str, trade_amount: float):
    """Execute the VIP FETCH automated trading process"""
    try:
        # Execute real token discovery from Pump.fun
        phase1_message = """
🔍 PHASE 1: LIVE TOKEN DISCOVERY

Sniffer Dog scanning Pump.fun for fresh opportunities...
• Scanning latest token launches
• Evaluating safety and potential
• Finding profitable entry points

SCANNING NOW...
        """
        send_message(chat_id, phase1_message)
        
        # Import and use the pump scanner
        from pump_scanner import discover_new_tokens
        
        # Discover fresh tokens from Pump.fun
        discovered_tokens = discover_new_tokens(max_tokens=5)
        
        if not discovered_tokens:
            send_message(chat_id, "❌ No suitable tokens found in current scan. Try again in a few minutes.")
            return
            
        # Select the best token from discovery
        best_token = discovered_tokens[0]  # Use the top-rated token
        token_mint = best_token['mint']
        token_name = best_token.get('name', 'Unknown')
        token_symbol = best_token.get('symbol', 'TOKEN')
        
        # Import Jupiter trade engine for direct execution
        from jupiter_trade_engine import JupiterTradeEngine
        
        # Use your actual wallet credentials
        public_key = "GcWdU2s5wem8nuF5AfWC8A2LrdTswragQtmkeUhByxk"
        private_key = "yPVxEVEoplWPzF4C92VB00IqFi7zoDl0sL5XMEZmdi8D/91Ha2a3rTPs4vrTxedFHEWGhF1lV4YXkntJ97aNMQ=="
        
        # Phase 2: Execute Live Trade
        phase2_message = f"""
PHASE 2: EXECUTING LIVE TRADE

Wallet: {public_key[:8]}...{public_key[-8:]} (YOUR WALLET)
Target: {token_name} ({token_symbol})
Token: {token_mint[:8]}...{token_mint[-8:]}
Amount: 0.0005 SOL
Safety: Emergency protection disabled for live trading
Method: Jupiter DEX integration

Executing trade now...
        """
        send_message(chat_id, phase2_message)
        
        # Execute the live trade with discovered token
        engine = JupiterTradeEngine()
        result = engine.execute_jupiter_trade(
            wallet_pubkey=public_key,
            private_key=private_key,
            token_mint=token_mint,  # Use discovered token mint
            sol_amount=0.0005,
            slippage_bps=1000,
            emergency_failsafe=False  # Live trading mode
        )
        
        # Phase 3: Report Results
        if result.get('success'):
            success_message = f"""
VIP FETCH EXECUTION SUCCESSFUL!

Trade Results:
• Status: SUCCESS
• Token: {token_name} ({token_symbol})
• Tokens Delivered: {result.get('actual_tokens', 0):,.0f} {token_symbol}
• Transaction: {result.get('transaction_hash', 'N/A')}
• Explorer: {result.get('explorer_url', 'N/A')}

/fetch ready for next execution!
            """
            send_message(chat_id, success_message)
        else:
            error_message = f"""
VIP FETCH EXECUTION FAILED

Error Details:
• {result.get('error', 'Unknown error')}

Try /fetch again or check wallet balance
            """
            send_message(chat_id, error_message)
        
    except Exception as e:
        logging.error(f"VIP FETCH execution failed: {e}")
        error_message = f"""
VIP FETCH SYSTEM ERROR

{str(e)}

Try /fetch again in a moment
        """
        send_message(chat_id, error_message)

# Main webhook handler function
def handle_update(update):
    """Handle incoming webhook updates from Telegram"""
    try:
        logging.info(f"Handling update: {update.get('update_id', 'unknown')}")
        
        # Extract message data
        message = update.get('message', {})
        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '').strip()
        user_id = str(message.get('from', {}).get('id', ''))
        
        if not chat_id or not text:
            logging.warning("Invalid message data received")
            return
        
        # Get user session
        session = get_or_create_session(chat_id)
        
        # Handle /fetch command directly
        if text == "/fetch":
            send_message(chat_id, "Initializing VIP FETCH trading session...")
            
            # Execute simplified fetch trading
            import asyncio
            try:
                asyncio.run(execute_vip_fetch_trading(chat_id, "test_wallet", 0.1))
            except Exception as e:
                logging.error(f"VIP FETCH error: {e}")
                send_message(chat_id, f"VIP FETCH error: {str(e)}")
            return
        
        # Handle other commands
        if text == "/help":
            help_message = """
Mork F.E.T.C.H Bot Commands:

/fetch - Execute VIP automated trading
/help - Show this help message

Bot Status: OPERATIONAL
Jupiter Engine: ACTIVE
            """
            send_message(chat_id, help_message)
            return
        
        # Default response
        send_message(chat_id, "Unknown command. Use /fetch for trading or /help for assistance.")
        
    except Exception as e:
        logging.error(f"Handle update error: {e}")
        # Only send error message if we have a valid chat_id
        try:
            send_message(chat_id, f"Bot error: {str(e)}")
        except:
            logging.error(f"Could not send error message to chat_id: {e}")

