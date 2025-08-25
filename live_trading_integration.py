#!/usr/bin/env python3
"""
Live trading integration for Telegram bot
Integrates the working PumpPortal API with bot commands
"""
import logging

import base58
import requests


def execute_live_trade(public_key, private_key, token_address, amount_tokens):
    """
    Execute live trade using working PumpPortal parameters

    Args:
        public_key: User's wallet public key
        private_key: User's wallet private key
        token_address: Token contract address
        amount_tokens: Number of tokens to buy

    Returns:
        dict: Trade result with success status and details
    """
    try:
        logging.info(f"Executing live trade: {amount_tokens} tokens of {token_address}")

        # Step 1: Generate transaction with working parameters
        trade_params = {
            "publicKey": public_key,
            "action": "buy",
            "mint": token_address,
            "amount": amount_tokens,
            "denominatedInSol": "false",  # Key working parameter
            "slippage": 15,
            "priorityFee": 0.001,
            "pool": "auto",
        }

        api_response = requests.post(
            url="https://pumpportal.fun/api/trade-local", data=trade_params, timeout=30
        )

        if api_response.status_code != 200:
            return {
                "success": False,
                "error": f"API Error: {api_response.text}",
                "stage": "api_generation",
            }

        # Step 2: Create and sign transaction
        from solders.commitment_config import CommitmentLevel
        from solders.keypair import Keypair
        from solders.rpc.config import RpcSendTransactionConfig
        from solders.rpc.requests import SendVersionedTransaction
        from solders.transaction import VersionedTransaction

        # Create keypair (using ChatGPT's working fix)
        decoded_key = base58.b58decode(private_key)
        keypair = Keypair.from_seed(decoded_key)

        # Create transaction
        tx = VersionedTransaction(
            VersionedTransaction.from_bytes(api_response.content).message, [keypair]
        )

        # Step 3: Broadcast transaction
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)

        send_response = requests.post(
            url="https://api.mainnet-beta.solana.com/",
            headers={"Content-Type": "application/json"},
            data=SendVersionedTransaction(tx, config).to_json(),
            timeout=60,
        )

        if send_response.status_code == 200:
            response_json = send_response.json()

            if "result" in response_json:
                tx_hash = response_json["result"]

                return {
                    "success": True,
                    "transaction_hash": tx_hash,
                    "tokens_purchased": amount_tokens,
                    "token_address": token_address,
                    "explorer_url": f"https://solscan.io/tx/{tx_hash}",
                    "message": f"✅ Successfully purchased {amount_tokens} tokens!\n🔍 View: https://solscan.io/tx/{tx_hash}",
                }
            else:
                error = response_json.get("error", {})
                return {
                    "success": False,
                    "error": f"Transaction failed: {error}",
                    "stage": "execution",
                }
        else:
            return {
                "success": False,
                "error": f"Broadcast failed: {send_response.text}",
                "stage": "broadcast",
            }

    except Exception as e:
        logging.error(f"Live trade execution failed: {e}")
        return {"success": False, "error": str(e), "stage": "general"}


def validate_token_address(token_address):
    """Validate if token exists on pump.fun"""
    try:
        response = requests.get(f"https://pump.fun/coin/{token_address}", timeout=10)
        return response.status_code == 200
    except:
        return False


def check_wallet_balance(public_key):
    """Check SOL balance of wallet"""
    try:
        from solana.rpc.api import Client
        from solders.pubkey import Pubkey as PublicKey

        client = Client("https://api.mainnet-beta.solana.com")
        pubkey = PublicKey.from_string(public_key)
        balance_response = client.get_balance(pubkey)

        if balance_response.value:
            return balance_response.value / 1_000_000_000
        return 0
    except:
        return 0


def format_trade_success_message(result):
    """Format success message for Telegram"""
    return f"""🎉 **TRADE SUCCESSFUL!**

💰 **Tokens Purchased:** {result['tokens_purchased']:,}
🪙 **Token:** {result['token_address'][:8]}...
📊 **Transaction Hash:** `{result['transaction_hash']}`

🔍 **View on Explorer:**
https://solscan.io/tx/{result['transaction_hash']}

✅ Your tokens have been added to your wallet!"""


def format_trade_error_message(result):
    """Format error message for Telegram"""
    stage = result.get("stage", "unknown")
    error = result.get("error", "Unknown error")

    return f"""❌ **TRADE FAILED**

🔧 **Stage:** {stage}
⚠️ **Error:** {error}

💡 **Next Steps:**
- Check wallet balance
- Verify token address
- Try again with smaller amount

Need help? Contact support."""
