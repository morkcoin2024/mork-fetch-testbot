# wallet.py — simple burner wallet per Telegram user (NOT for prod custody)
import json
import os
import time
from pathlib import Path

from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
WALLETS = DATA_DIR / "burners.json"
RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
_rpc = None


def _get_rpc():
    global _rpc
    if _rpc is None:
        _rpc = Client(RPC_URL, timeout=10)
    return _rpc


def _load():
    if WALLETS.exists():
        return json.loads(WALLETS.read_text())
    return {}


def _save(d):
    WALLETS.write_text(json.dumps(d, indent=2))


def ensure_burner(user_id: str):
    d = _load()
    if user_id in d:
        return d[user_id]
    kp = Keypair()
    entry = {"created": int(time.time()), "pubkey": str(kp.pubkey()), "secret": list(bytes(kp))}
    d[user_id] = entry
    _save(d)
    return entry


def get_pubkey(user_id: str):
    d = _load()
    e = d.get(user_id)
    return e["pubkey"] if e else None


def get_balance_sol(pubkey: str) -> float:
    try:
        pubkey_obj = Pubkey.from_string(pubkey)
        rpc = _get_rpc()
        response = rpc.get_balance(pubkey_obj)
        lamports = response.value
        return lamports / 1_000_000_000
    except Exception:
        return -1.0
