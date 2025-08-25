# wallets.py
import base64
import json
import os
import pathlib
import time

import base58
import httpx
from nacl.signing import SigningKey

DATA_DIR = pathlib.Path("./data")
WALLETS_PATH = DATA_DIR / "wallets.json"
SOLANA_RPC = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")


def _ensure_store():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WALLETS_PATH.exists():
        WALLETS_PATH.write_text(json.dumps({"version": 1, "wallets": {}}))


def _load() -> dict:
    _ensure_store()
    return json.loads(WALLETS_PATH.read_text())


def _save(data: dict):
    WALLETS_PATH.write_text(json.dumps(data, indent=2))


def _address_from_seed(seed: bytes) -> str:
    pk = SigningKey(seed).verify_key  # 32‑byte ed25519 pubkey
    return base58.b58encode(bytes(pk)).decode()


def get_or_create_wallet(user_id: str) -> dict:
    data = _load()
    w = data["wallets"].get(user_id)
    if w:
        return w
    seed = os.urandom(32)
    addr = _address_from_seed(seed)
    entry = {
        "address": addr,
        "seed_b64": base64.b64encode(
            seed
        ).decode(),  # NOTE: for MVP only; replace with KMS/SecretBox
        "created_at": int(time.time()),
    }
    data["wallets"][user_id] = entry
    _save(data)
    return entry


def get_wallet(user_id: str) -> dict | None:
    return _load()["wallets"].get(user_id)


async def get_balance(address: str) -> float:
    # returns SOL (lamports -> SOL)
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(SOLANA_RPC, json=payload)
        lamports = r.json()["result"]["value"]
        return float(lamports) / 1_000_000_000.0
    except Exception:
        return 0.0


async def get_token_accounts(address: str) -> list:
    """Get all SPL token accounts for a wallet"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(SOLANA_RPC, json=payload)

        result = r.json()
        if "result" in result and "value" in result["result"]:
            return result["result"]["value"]
        return []
    except Exception as e:
        import logging

        logging.warning(f"[WALLET] get_token_accounts failed: {e}")
        return []


async def get_token_metadata(mint_address: str) -> dict:
    """Get token metadata (name, symbol, decimals) from mint address"""
    # Known token addresses for better display
    KNOWN_TOKENS = {
        "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH": {"symbol": "MORK", "name": "Mork"},
        "FUXtsxzXCyYMQnpZA11veLDECkSHeGvLXuJuC9Npbonk": {"symbol": "GEMINI", "name": "Gemini"},
        "Dhyf7Qu3Mpp9suh7MUF6bZKmpWAJmfmsMKRKVoTyFJ9B": {"symbol": "CLIPPY", "name": "Clippy"},
    }

    # Check if it's a known token first
    if mint_address in KNOWN_TOKENS:
        known = KNOWN_TOKENS[mint_address]
        return {"decimals": 6, "symbol": known["symbol"], "name": known["name"]}

    try:
        # Get token supply and decimals for unknown tokens
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getTokenSupply", "params": [mint_address]}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(SOLANA_RPC, json=payload)

        result = r.json()
        if "result" in result and "value" in result["result"]:
            decimals = result["result"]["value"]["decimals"]
            return {
                "decimals": decimals,
                "symbol": mint_address[:8],
                "name": f"Token {mint_address[:8]}",
            }
        return {"decimals": 9, "symbol": "UNKNOWN", "name": "Unknown Token"}
    except Exception:
        return {"decimals": 9, "symbol": "UNKNOWN", "name": "Unknown Token"}


# Sync wrapper for the webhook
def get_balance_sol(address: str) -> float:
    import asyncio

    try:
        return asyncio.run(get_balance(address))
    except Exception:
        return 0.0


# Command functions for webhook integration
def cmd_wallet_new(user_id) -> str:
    """Generate keypair, persist per-user, return Markdown-safe notice"""
    try:
        user_id_str = str(user_id)
        wallet = get_or_create_wallet(user_id_str)
        addr = wallet["address"]
        return (
            f"**Wallet created**\n"
            f"Address: `{addr}`\n\n"
            f"⚠️ Burner wallet for testing only. Do not send large amounts!"
        )
    except Exception as e:
        return f"Error creating wallet: {e!s}"


def cmd_wallet_addr(user_id) -> str:
    """Load wallet; if missing return guidance, else return addr in code block"""
    try:
        user_id_str = str(user_id)
        wallet = get_wallet(user_id_str)
        if not wallet:
            return "No wallet found. Run /wallet_new"
        return f"Address: `{wallet['address']}`"
    except Exception as e:
        return f"Error getting wallet address: {e!s}"


def cmd_wallet_balance(user_id) -> str:
    """Load wallet; show SOL + all SPL token balances"""
    try:
        user_id_str = str(user_id)
        wallet = get_wallet(user_id_str)
        if not wallet:
            return "No wallet found. Run /wallet_new"

        addr = wallet["address"]

        # Get SOL balance
        sol_balance = get_balance_sol(addr)

        # Get token balances
        import asyncio

        token_accounts = asyncio.run(get_token_accounts(addr))

        result = "**💰 Wallet Balance**\n"
        result += f"Address: `{addr[:12]}...{addr[-8:]}`\n\n"
        result += f"**SOL**: {sol_balance:.9f}\n"

        if token_accounts:
            result += f"\n**🪙 SPL Tokens** ({len(token_accounts)} found):\n"

            for account in token_accounts[:10]:  # Limit to first 10 tokens
                try:
                    token_data = account["account"]["data"]["parsed"]["info"]
                    mint = token_data["mint"]
                    token_amount = token_data["tokenAmount"]

                    # Get human-readable amount
                    amount = float(token_amount["uiAmount"] or 0)
                    _ = token_amount["decimals"]
                    if amount > 0:
                        # Try to get token metadata
                        metadata = asyncio.run(get_token_metadata(mint))
                        symbol = metadata.get("symbol", mint[:8])

                        if amount >= 1:
                            result += f"• **{symbol}**: {amount:,.2f}\n"
                        else:
                            result += f"• **{symbol}**: {amount:.6f}\n"

                except Exception as token_error:
                    import logging

                    logging.warning(f"[WALLET] token parsing error: {token_error}")
                    continue

            if len(token_accounts) > 10:
                result += f"... and {len(token_accounts) - 10} more tokens\n"
        else:
            result += "\n**🪙 SPL Tokens**: None found"

        return result

    except Exception as e:
        import logging

        logging.warning("[WALLET] balance fetch failed: %s", e)
        return f"Error fetching balance: {e!s}"


def cmd_wallet_summary(user_id) -> str:
    """Combine addr + balance; fall back to guidance if missing"""
    try:
        user_id_str = str(user_id)
        wallet = get_wallet(user_id_str)
        if not wallet:
            return "No wallet found. Run /wallet_new"

        addr = wallet["address"]
        balance = get_balance_sol(addr)
        return f"Address: `{addr[:12]}...` | SOL: {balance:.4f}"
    except Exception as e:
        import logging

        logging.warning("[WALLET] summary failed: %s", e)
        return f"Error getting wallet summary: {e!s}"


def cmd_wallet_export(user_id) -> str:
    """Export wallet details including private key - ADMIN ONLY"""
    try:
        user_id_str = str(user_id)
        wallet = get_wallet(user_id_str)
        if not wallet:
            return "No wallet found. Run /wallet_new"

        # Get the seed and derive private key
        seed_b64 = wallet["seed_b64"]
        seed_bytes = base64.b64decode(seed_b64)

        # Create signing key from seed
        signing_key = SigningKey(seed_bytes)
        private_key_bytes = bytes(signing_key)
        private_key_b58 = base58.b58encode(private_key_bytes).decode()

        addr = wallet["address"]
        created_at = wallet.get("created_at", "unknown")

        return (
            f"**🔐 Wallet Export**\n"
            f"Address: `{addr}`\n"
            f"Private Key: `{private_key_b58}`\n"
            f"Seed (Base64): `{seed_b64}`\n"
            f"Created: {created_at}\n\n"
            f"⚠️ **KEEP PRIVATE** - Never share these keys!"
        )

    except Exception as e:
        import logging

        logging.error("[WALLET] export failed: %s", e)
        return f"Error exporting wallet: {e!s}"
