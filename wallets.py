"""
Minimal burner wallet helper for Mork F.E.T.C.H Bot
Generates ed25519 keypairs and stores per-user wallets safely
"""
import os
import json
import time
import base58
from pathlib import Path
from nacl.signing import SigningKey
from nacl.encoding import RawEncoder
import httpx
import logging

WALLETS_DIR = Path("./data")
WALLETS_FILE = WALLETS_DIR / "wallets.json"

log = logging.getLogger(__name__)

def ensure_data_dir():
    """Create data directory if it doesn't exist"""
    WALLETS_DIR.mkdir(exist_ok=True)

def load_wallets():
    """Load wallets from JSON file"""
    ensure_data_dir()
    if not WALLETS_FILE.exists():
        return {}
    try:
        with open(WALLETS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"Failed to load wallets: {e}")
        return {}

def save_wallets(wallets):
    """Save wallets to JSON file"""
    ensure_data_dir()
    try:
        with open(WALLETS_FILE, 'w') as f:
            json.dump(wallets, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save wallets: {e}")

def ensure_burner(user_id):
    """Ensure user has a burner wallet, create if needed"""
    user_id = str(user_id)
    wallets = load_wallets()
    
    if user_id not in wallets:
        # Generate new ed25519 keypair
        signing_key = SigningKey.generate()
        private_key = signing_key.encode(encoder=RawEncoder)
        public_key = signing_key.verify_key.encode(encoder=RawEncoder)
        
        # Encode keys as base58
        private_b58 = base58.b58encode(private_key).decode('utf-8')
        public_b58 = base58.b58encode(public_key).decode('utf-8')
        
        wallets[user_id] = {
            "private_key": private_b58,  # Never expose this in chat
            "public_key": public_b58,
            "created_at": str(int(time.time()))
        }
        save_wallets(wallets)
        log.info(f"Created new burner wallet for user {user_id}")
    
    return wallets[user_id]

def get_pubkey(user_id):
    """Get user's public key (address)"""
    user_id = str(user_id)
    wallets = load_wallets()
    if user_id in wallets:
        return wallets[user_id]["public_key"]
    return None

def get_balance_sol(pubkey):
    """Get SOL balance for address"""
    rpc_url = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [pubkey]
        }
        
        with httpx.Client(timeout=5.0) as client:
            response = client.post(rpc_url, json=payload)
            
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "value" in data["result"]:
                lamports = data["result"]["value"]
                sol = lamports / 1_000_000_000  # Convert lamports to SOL
                return sol
            else:
                log.warning(f"Unexpected RPC response: {data}")
                return -1.0
        else:
            log.warning(f"RPC request failed: {response.status_code}")
            return -1.0
            
    except Exception as e:
        log.error(f"Balance check failed: {e}")
        return -1.0