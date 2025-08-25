"""
Secure Wallet Management for Mork F.E.T.C.H Bot
Handles wallet encryption, storage, and secure key management
"""

import base64
import json
import logging
import os
import time

import base58
from cryptography.fernet import Fernet
from solders.keypair import Keypair

logger = logging.getLogger(__name__)


class WalletManager:
    """Secure wallet management with encrypted storage"""

    def __init__(self):
        self.wallets_file = "wallets.json"
        self.key_file = "wallet_encryption.key"
        self._ensure_encryption_key()

    def _ensure_encryption_key(self):
        """Create or load encryption key"""
        if os.path.exists(self.key_file):
            with open(self.key_file, "rb") as f:
                self.encryption_key = f.read()
        else:
            self.encryption_key = Fernet.generate_key()
            with open(self.key_file, "wb") as f:
                f.write(self.encryption_key)

        self.fernet = Fernet(self.encryption_key)

    def _load_wallets(self) -> dict:
        """Load encrypted wallets from storage"""
        if os.path.exists(self.wallets_file):
            try:
                with open(self.wallets_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading wallets: {e}")
                return {}
        return {}

    def _save_wallets(self, wallets: dict):
        """Save encrypted wallets to storage"""
        try:
            with open(self.wallets_file, "w") as f:
                json.dump(wallets, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving wallets: {e}")

    def create_wallet(self, chat_id: str, wallet_name: str) -> dict:
        """Create new wallet for user"""
        try:
            # Generate new keypair
            keypair = Keypair()
            pubkey = str(keypair.pubkey())
            private_key = base58.b58encode(bytes(keypair)).decode()

            # Encrypt private key
            encrypted_key = self.fernet.encrypt(private_key.encode()).decode()

            # Store wallet
            wallets = self._load_wallets()
            user_id = str(chat_id)

            if user_id not in wallets:
                wallets[user_id] = {}

            wallets[user_id][wallet_name] = {
                "pubkey": pubkey,
                "encrypted_private_key": encrypted_key,
                "created": int(time.time()) if "time" in globals() else 0,
            }

            self._save_wallets(wallets)

            logger.info(f"Created wallet for user {chat_id}: {pubkey}")
            return {"success": True, "pubkey": pubkey, "wallet_name": wallet_name}

        except Exception as e:
            logger.error(f"Wallet creation failed: {e}")
            return {"success": False, "error": str(e)}

    def import_wallet(self, chat_id: str, private_key: str, wallet_name: str) -> dict:
        """Import existing wallet from private key"""
        try:
            # Handle different private key formats
            if len(private_key) == 88:  # Base64 format
                try:
                    decoded_bytes = base64.b64decode(private_key)
                    keypair = Keypair.from_bytes(decoded_bytes)
                    private_key_b58 = base58.b58encode(bytes(keypair)).decode()
                except Exception as e:
                    return {"success": False, "error": f"Invalid base64 private key: {e}"}
            else:  # Assume base58 format
                try:
                    private_key_bytes = base58.b58decode(private_key)
                    keypair = Keypair.from_bytes(private_key_bytes)
                    private_key_b58 = private_key
                except Exception as e:
                    return {"success": False, "error": f"Invalid base58 private key: {e}"}

            pubkey = str(keypair.pubkey())

            # Encrypt private key
            encrypted_key = self.fernet.encrypt(private_key_b58.encode()).decode()

            # Store wallet
            wallets = self._load_wallets()
            user_id = str(chat_id)

            if user_id not in wallets:
                wallets[user_id] = {}

            wallets[user_id][wallet_name] = {
                "pubkey": pubkey,
                "encrypted_private_key": encrypted_key,
                "imported": True,
                "created": int(time.time()) if "time" in globals() else 0,
            }

            self._save_wallets(wallets)

            logger.info(f"Imported wallet for user {chat_id}: {pubkey}")
            return {"success": True, "pubkey": pubkey, "wallet_name": wallet_name}

        except Exception as e:
            logger.error(f"Wallet import failed: {e}")
            return {"success": False, "error": str(e)}

    def get_private_key(self, chat_id: str, wallet_name: str = "default") -> str | None:
        """Get decrypted private key for trading operations"""
        try:
            wallets = self._load_wallets()
            user_id = str(chat_id)

            if user_id in wallets and wallet_name in wallets[user_id]:
                encrypted_key = wallets[user_id][wallet_name]["encrypted_private_key"]
                private_key = self.fernet.decrypt(encrypted_key.encode()).decode()
                return private_key

            logger.warning(f"Wallet not found: {chat_id}/{wallet_name}")
            return None

        except Exception as e:
            logger.error(f"Error getting private key: {e}")
            return None

    def get_wallet_info(self, chat_id: str) -> dict:
        """Get wallet information for user"""
        try:
            wallets = self._load_wallets()
            user_id = str(chat_id)

            if user_id in wallets:
                wallet_info = {}
                for name, data in wallets[user_id].items():
                    wallet_info[name] = {
                        "pubkey": data["pubkey"],
                        "imported": data.get("imported", False),
                        "created": data.get("created", 0),
                    }
                return wallet_info

            return {}

        except Exception as e:
            logger.error(f"Error getting wallet info: {e}")
            return {}

    def has_wallet(self, chat_id: str, wallet_name: str = "default") -> bool:
        """Check if user has a wallet"""
        wallets = self._load_wallets()
        user_id = str(chat_id)
        return user_id in wallets and wallet_name in wallets[user_id]


# Global instance
wallet_manager = WalletManager()
