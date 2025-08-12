# wallets.py
import os, json, time, base64, pathlib
from typing import Optional, Dict
from nacl.signing import SigningKey
from nacl.public import PublicKey
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

def _pubkey_from_seed(seed_bytes:bytes)->str:
    sk = SigningKey(seed_bytes)
    pk = sk.verify_key
    # Solana address is base58 of the 32-byte ed25519 public key
    return base58.b58encode(bytes(pk)).decode()

def get_or_create_wallet(user_id:str)->Dict:
    data = _load()
    if "wallets" not in data:
        data["wallets"] = {}
    
    w = data["wallets"].get(user_id)
    if w:
        return w
    
    # create new 32-byte seed; store **encrypted later** (for now, base64 with clear warning)
    seed = os.urandom(32)
    addr = _pubkey_from_seed(seed)
    entry = {
        "address": addr,
        "seed_b64": base64.b64encode(seed).decode(),  # TODO: replace with KMS/secret-box
        "created_at": int(time.time())
    }
    data["wallets"][user_id] = entry
    _save(data)
    return entry

def get_wallet(user_id:str)->Optional[Dict]:
    data = _load()
    if "wallets" not in data:
        return None
    return data["wallets"].get(user_id)

async def get_balance(address:str)->float:
    # returns SOL (lamports -> SOL)
    try:
        payload = {"jsonrpc":"2.0","id":1,"method":"getBalance","params":[address]}
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(SOLANA_RPC, json=payload)
        lamports = r.json()["result"]["value"]
        return float(lamports) / 1_000_000_000.0
    except Exception:
        return 0.0

# Sync wrapper for compatibility with existing webhook handlers
def get_balance_sol(address:str)->float:
    import asyncio
    try:
        return asyncio.run(get_balance(address))
    except Exception:
        return -1.0

# Legacy function names for compatibility
def ensure_burner(user_id:str)->Dict:
    """Legacy compatibility function"""
    wallet = get_or_create_wallet(user_id)
    return {"public_key": wallet["address"]}

def get_pubkey(user_id:str)->Optional[str]:
    """Legacy compatibility function"""
    wallet = get_wallet(user_id)
    return wallet["address"] if wallet else None