# wallets.py
import os, json, time, base64, pathlib
from typing import Optional, Dict
from nacl.signing import SigningKey
import base58
import httpx

DATA_DIR = pathlib.Path("./data")
WALLETS_PATH = DATA_DIR / "wallets.json"
SOLANA_RPC = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

def _ensure_store():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WALLETS_PATH.exists():
        WALLETS_PATH.write_text(json.dumps({"version":1,"wallets":{}}))

def _load()->Dict:
    _ensure_store()
    return json.loads(WALLETS_PATH.read_text())

def _save(data:Dict):
    WALLETS_PATH.write_text(json.dumps(data, indent=2))

def _address_from_seed(seed:bytes)->str:
    pk = SigningKey(seed).verify_key  # 32‑byte ed25519 pubkey
    return base58.b58encode(bytes(pk)).decode()

def get_or_create_wallet(user_id:str)->Dict:
    data = _load()
    w = data["wallets"].get(user_id)
    if w: return w
    seed = os.urandom(32)
    addr = _address_from_seed(seed)
    entry = {
        "address": addr,
        "seed_b64": base64.b64encode(seed).decode(),  # NOTE: for MVP only; replace with KMS/SecretBox
        "created_at": int(time.time())
    }
    data["wallets"][user_id] = entry
    _save(data)
    return entry

def get_wallet(user_id:str)->Optional[Dict]:
    return _load()["wallets"].get(user_id)

async def get_balance(address:str)->float:
    # returns SOL (lamports -> SOL)
    try:
        payload = {"jsonrpc":"2.0","id":1,"method":"getBalance","params":[address]}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(SOLANA_RPC, json=payload)
        lamports = r.json()["result"]["value"]
        return float(lamports)/1_000_000_000.0
    except Exception:
        return 0.0

# Sync wrapper for the webhook
def get_balance_sol(address:str)->float:
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
        return (f"**Wallet created**\n"
                f"Address: `{addr}`\n\n"
                f"⚠️ Burner wallet for testing only. Do not send large amounts!")
    except Exception as e:
        return f"Error creating wallet: {str(e)}"

def cmd_wallet_addr(user_id) -> str:
    """Load wallet; if missing return guidance, else return addr in code block"""
    try:
        user_id_str = str(user_id)
        wallet = get_wallet(user_id_str)
        if not wallet:
            return "No wallet found. Run /wallet_new"
        return f"Address: `{wallet['address']}`"
    except Exception as e:
        return f"Error getting wallet address: {str(e)}"

def cmd_wallet_balance(user_id) -> str:
    """Load wallet; if missing return guidance, else RPC getBalance with 9 decimal formatting"""
    try:
        user_id_str = str(user_id)
        wallet = get_wallet(user_id_str)
        if not wallet:
            return "No wallet found. Run /wallet_new"
        
        addr = wallet["address"]
        balance = get_balance_sol(addr)
        return (f"**Balance**\n"
                f"Address: `{addr}`\n"
                f"SOL: {balance:.9f}")
    except Exception as e:
        import logging
        logging.warning("[WALLET] balance fetch failed: %s", e)
        return f"Error fetching balance: {str(e)}"

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
        return f"Error getting wallet summary: {str(e)}"