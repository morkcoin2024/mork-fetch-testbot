"""
wallet.py - Secure Wallet Management
Handles wallet creation, import, and secure storage
Never transmits private keys outside the process
"""
import os
import json
import base64
import base58
import logging
from typing import Optional, Dict
from cryptography.fernet import Fernet
from solders.keypair import Keypair

logger = logging.getLogger(__name__)

class WalletManager:
    def __init__(self, encryption_key: Optional[bytes] = None):
        """Initialize wallet manager with encryption key"""
        if encryption_key is None:
            # Generate or load encryption key
            key_file = "wallet_encryption.key"
            if os.path.exists(key_file):
                with open(key_file, "rb") as f:
                    encryption_key = f.read()
            else:
                encryption_key = Fernet.generate_key()
                with open(key_file, "wb") as f:
                    f.write(encryption_key)
                    
        self.fernet = Fernet(encryption_key)
        self.wallet_store_path = "wallets.json"
        
    def create_wallet(self, chat_id: str, label: str = "Main") -> Dict:
        """Create a new wallet for user"""
        try:
            # Generate new keypair
            keypair = Keypair()
            pubkey = str(keypair.pubkey())
            private_key_b58 = base58.b58encode(bytes(keypair)).decode('utf-8')
            
            # Encrypt private key
            encrypted_privkey = self.fernet.encrypt(private_key_b58.encode()).decode()
            
            wallet_data = {
                "pubkey": pubkey,
                "enc_privkey": encrypted_privkey,
                "label": label,
                "created_at": int(time.time())
            }
            
            # Store wallet
            self._store_wallet(chat_id, wallet_data)
            
            logger.info(f"Created wallet for {chat_id}: {pubkey[:8]}...")
            
            return {
                "success": True,
                "pubkey": pubkey,
                "label": label
            }
            
        except Exception as e:
            logger.error(f"Failed to create wallet: {e}")
            return {"success": False, "error": str(e)}
            
    def import_wallet(self, chat_id: str, private_key_b58: str, label: str = "Imported") -> Dict:
        """Import existing wallet from base58 private key"""
        try:
            # Validate private key
            keypair = Keypair.from_base58_string(private_key_b58)
            pubkey = str(keypair.pubkey())
            
            # Encrypt private key
            encrypted_privkey = self.fernet.encrypt(private_key_b58.encode()).decode()
            
            wallet_data = {
                "pubkey": pubkey,
                "enc_privkey": encrypted_privkey,
                "label": label,
                "created_at": int(time.time())
            }
            
            # Store wallet
            self._store_wallet(chat_id, wallet_data)
            
            logger.info(f"Imported wallet for {chat_id}: {pubkey[:8]}...")
            
            return {
                "success": True,
                "pubkey": pubkey,
                "label": label
            }
            
        except Exception as e:
            logger.error(f"Failed to import wallet: {e}")
            return {"success": False, "error": f"Invalid private key: {e}"}
            
    def get_wallet(self, chat_id: str) -> Optional[Dict]:
        """Get wallet data for user (without decrypting private key)"""
        try:
            wallets = self._load_wallets()
            wallet_data = wallets.get(chat_id)
            
            if wallet_data:
                return {
                    "pubkey": wallet_data["pubkey"],
                    "label": wallet_data.get("label", "Main"),
                    "created_at": wallet_data.get("created_at", 0)
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get wallet: {e}")
            return None
            
    def get_private_key(self, chat_id: str) -> Optional[str]:
        """Decrypt and return private key (use sparingly)"""
        try:
            wallets = self._load_wallets()
            wallet_data = wallets.get(chat_id)
            
            if not wallet_data:
                return None
                
            # Decrypt private key
            encrypted_privkey = wallet_data["enc_privkey"].encode()
            private_key_b58 = self.fernet.decrypt(encrypted_privkey).decode()
            
            return private_key_b58
            
        except Exception as e:
            logger.error(f"Failed to decrypt private key: {e}")
            return None
            
    def delete_wallet(self, chat_id: str) -> bool:
        """Delete user's wallet"""
        try:
            wallets = self._load_wallets()
            if chat_id in wallets:
                del wallets[chat_id]
                self._save_wallets(wallets)
                logger.info(f"Deleted wallet for {chat_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete wallet: {e}")
            return False
            
    def _load_wallets(self) -> Dict:
        """Load wallets from storage"""
        try:
            if os.path.exists(self.wallet_store_path):
                with open(self.wallet_store_path, "r") as f:
                    return json.load(f)
            return {}
        except:
            return {}
            
    def _save_wallets(self, wallets: Dict):
        """Save wallets to storage"""
        with open(self.wallet_store_path, "w") as f:
            json.dump(wallets, f, indent=2)
            
    def _store_wallet(self, chat_id: str, wallet_data: Dict):
        """Store wallet data for user"""
        wallets = self._load_wallets()
        wallets[chat_id] = wallet_data
        self._save_wallets(wallets)

# Global wallet manager instance
import time
wallet_manager = WalletManager()

# Convenience functions
def create_wallet(chat_id: str, label: str = "Main") -> Dict:
    return wallet_manager.create_wallet(chat_id, label)

def import_wallet(chat_id: str, private_key_b58: str, label: str = "Imported") -> Dict:
    return wallet_manager.import_wallet(chat_id, private_key_b58, label)

def get_wallet(chat_id: str) -> Optional[Dict]:
    return wallet_manager.get_wallet(chat_id)

def get_private_key(chat_id: str) -> Optional[str]:
    return wallet_manager.get_private_key(chat_id)