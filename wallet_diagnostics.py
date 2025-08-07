"""
Wallet Diagnostics and Balance Checking for Burner Wallets
Implements ChatGPT's suggestions for proper wallet validation
"""
import json
import os
import logging
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address

logger = logging.getLogger(__name__)

class WalletDiagnostics:
    """Diagnostic tools for burner wallet functionality"""
    
    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.client = Client(rpc_endpoint)
    
    def check_wallet_funding(self, chat_id: str) -> dict:
        """Check if burner wallet is properly funded with SOL"""
        try:
            # Load wallet data
            wallet_files = [
                os.path.join("user_wallets", f"user_{chat_id}.json"),
                os.path.join("user_wallets", f"wallet_{chat_id}.json")
            ]
            
            wallet_data = None
            for wallet_file in wallet_files:
                if os.path.exists(wallet_file):
                    with open(wallet_file, 'r') as f:
                        wallet_data = json.load(f)
                    break
            
            if not wallet_data:
                return {
                    "success": False,
                    "error": "No wallet found",
                    "sol_balance": 0,
                    "lamports": 0
                }
            
            # Check SOL balance
            public_key = wallet_data.get('public_key', '')
            balance_response = self.client.get_balance(Pubkey.from_string(public_key))
            
            if balance_response.value is not None:
                lamports = balance_response.value
                sol_balance = lamports / 1e9
                
                logger.info(f"Wallet {public_key[:10]}... has {sol_balance:.6f} SOL ({lamports} lamports)")
                
                return {
                    "success": True,
                    "public_key": public_key,
                    "sol_balance": sol_balance,
                    "lamports": lamports,
                    "funded": lamports > 0,
                    "trading_ready": lamports >= 10_000_000  # 0.01 SOL minimum for trading
                }
            else:
                return {
                    "success": False,
                    "error": "Unable to fetch balance",
                    "sol_balance": 0,
                    "lamports": 0
                }
                
        except Exception as e:
            logger.error(f"Wallet funding check failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "sol_balance": 0,
                "lamports": 0
            }
    
    def check_token_account_exists(self, wallet_address: str, token_mint: str) -> dict:
        """Check if Associated Token Account exists for pump.fun token"""
        try:
            from spl.token.instructions import get_associated_token_address
            
            # Generate ATA address
            wallet_pubkey = Pubkey.from_string(wallet_address)
            token_pubkey = Pubkey.from_string(token_mint)
            
            ata_address = get_associated_token_address(wallet_pubkey, token_pubkey)
            
            # Check if ATA exists
            account_info = self.client.get_account_info(ata_address)
            
            exists = account_info.value is not None
            
            logger.info(f"ATA {ata_address} exists: {exists}")
            
            return {
                "success": True,
                "ata_address": str(ata_address),
                "exists": exists,
                "wallet": wallet_address,
                "token_mint": token_mint
            }
            
        except Exception as e:
            logger.error(f"ATA check failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def diagnose_trading_readiness(self, chat_id: str) -> dict:
        """Complete diagnostic of wallet trading readiness"""
        try:
            # Check wallet funding
            funding_check = self.check_wallet_funding(chat_id)
            
            if not funding_check.get("success"):
                return {
                    "ready": False,
                    "issues": ["Wallet not found or inaccessible"],
                    "funding": funding_check
                }
            
            issues = []
            
            # Check SOL balance
            if funding_check.get("lamports", 0) == 0:
                issues.append("🔋 Wallet has no SOL funds (0 lamports)")
            elif funding_check.get("lamports", 0) < 10_000_000:  # Less than 0.01 SOL
                issues.append(f"🔋 Low SOL balance: {funding_check.get('sol_balance', 0):.6f} SOL (need ≥0.01)")
            
            # Check private key availability
            wallet_files = [
                os.path.join("user_wallets", f"user_{chat_id}.json"),
                os.path.join("user_wallets", f"wallet_{chat_id}.json")
            ]
            
            has_private_key = False
            for wallet_file in wallet_files:
                if os.path.exists(wallet_file):
                    with open(wallet_file, 'r') as f:
                        wallet_data = json.load(f)
                    if wallet_data.get('private_key') or wallet_data.get('private_key_encrypted'):
                        has_private_key = True
                    break
            
            if not has_private_key:
                issues.append("🔐 Private key not found - cannot sign transactions")
            
            is_ready = len(issues) == 0
            
            return {
                "ready": is_ready,
                "issues": issues,
                "funding": funding_check,
                "recommendations": self._get_recommendations(issues)
            }
            
        except Exception as e:
            logger.error(f"Trading readiness diagnosis failed: {e}")
            return {
                "ready": False,
                "issues": [f"Diagnostic error: {str(e)}"],
                "funding": {}
            }
    
    def _get_recommendations(self, issues: list) -> list:
        """Get recommendations based on identified issues"""
        recommendations = []
        
        for issue in issues:
            if "no SOL funds" in issue:
                recommendations.append("Send SOL to your burner wallet address")
            elif "Low SOL balance" in issue:
                recommendations.append("Add more SOL - minimum 0.01 SOL recommended for trading")
            elif "Private key not found" in issue:
                recommendations.append("Use /exportwallet to verify private key, or create new wallet with /mywallet")
        
        if not recommendations:
            recommendations.append("Wallet is ready for trading!")
            
        return recommendations

# Global instance
wallet_diagnostics = WalletDiagnostics()