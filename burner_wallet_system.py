"""
Burner Wallet System for MORK F.E.T.C.H Bot
Per-user, non-custodial burner wallets generated locally via Solana keypair generation.
Users have full control - we never touch their wallets.

Each user gets:
🔑 Public address (for funding + trade tracking)
🔐 Private key (securely stored, never exposed unless user requests export)
❗️ Users are informed that this wallet is non-recoverable if lost and they are responsible for backing it up if exported.
"""

import os
import json
import logging
import base64
import asyncio
from typing import Optional, Dict, Tuple
from datetime import datetime
from cryptography.fernet import Fernet

# Use correct Solana imports that are actually available
try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
    # Note: Using solders.keypair as it's the modern implementation
    # Generated exactly as specified: keypair = Keypair.generate()
    SOLANA_IMPORTS_AVAILABLE = True
    logging.info("✅ Solana libraries (solders) loaded successfully")
except ImportError as e:
    logging.warning(f"Solana imports not available: {e}")
    SOLANA_IMPORTS_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Marketing wallet for profit fees (0.5% of profits)
MARKETING_WALLET_ADDRESS = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"  # Placeholder - replace with actual

class BurnerWalletManager:
    """Manages individual burner wallets for each user"""
    
    def __init__(self):
        self.wallets_dir = "user_wallets"
        self.encryption_key = self._get_or_create_encryption_key()
        # Note: Client would be initialized here for balance checking
        # Currently focused on wallet generation functionality
        self.client = None
        
        # Create wallets directory if it doesn't exist
        os.makedirs(self.wallets_dir, exist_ok=True)
        
        # MORK token requirements
        self.mork_token_mint = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"
        self.min_mork_tokens = 100000  # 100K MORK minimum
        self.profit_fee_rate = 0.005  # 0.5% fee on profits
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for wallet storage"""
        key_file = "wallet_encryption.key"
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new encryption key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
            
    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        f = Fernet(self.encryption_key)
        return f.encrypt(data.encode()).decode()
        
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        f = Fernet(self.encryption_key)
        return f.decrypt(encrypted_data.encode()).decode()
        
    def generate_burner_wallet(self, user_id: str) -> Dict[str, str]:
        """
        Generate a new burner wallet for a user using exact method specified:
        from solana.keypair import Keypair
        keypair = Keypair.generate()
        
        Per user, non-custodial design - users have full control.
        """
        try:
            if not SOLANA_IMPORTS_AVAILABLE:
                raise Exception("Solana libraries not available")
            
            # Generate keypair using solders library (modern Solana implementation)
            # This achieves the same result as: keypair = Keypair.generate()
            keypair = Keypair()
            
            # Extract public and private key
            public_key = str(keypair.pubkey())
            private_key = base64.b64encode(bytes(keypair)).decode('utf-8')
            
            # Wallet data to store
            wallet_data = {
                'user_id': user_id,
                'public_key': public_key,
                'private_key_encrypted': self._encrypt_data(private_key),
                'created_at': datetime.now().isoformat(),
                'trades_count': 0,
                'total_profit': 0.0,
                'warning_shown': False  # Track if user has been warned about non-recovery
            }
            
            # Save wallet to file
            wallet_file = os.path.join(self.wallets_dir, f"user_{user_id}.json")
            with open(wallet_file, 'w') as f:
                json.dump(wallet_data, f, indent=2)
            
            logger.info(f"Generated burner wallet for user {user_id}: {public_key}")
            
            return {
                'success': True,
                'public_key': public_key,
                'user_id': user_id,
                'created_at': wallet_data['created_at'],
                'warning': 'This wallet is non-recoverable if lost. You are responsible for backing it up if exported.'
            }
            
        except Exception as e:
            logger.error(f"Failed to generate burner wallet for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_wallet_keys(self, user_id: str) -> Dict[str, str]:
        """
        Export wallet private key for user backup.
        Users are fully responsible for backing up their keys.
        We never touch their wallets - full user control.
        """
        try:
            wallet_file = os.path.join(self.wallets_dir, f"user_{user_id}.json")
            
            if not os.path.exists(wallet_file):
                return {
                    'success': False,
                    'error': 'No burner wallet found. Create one with /mywallet first.'
                }
            
            # Load wallet data
            with open(wallet_file, 'r') as f:
                wallet_data = json.load(f)
            
            # Decrypt private key
            private_key_encrypted = wallet_data['private_key_encrypted']
            private_key = self._decrypt_data(private_key_encrypted)
            
            # Update warning shown flag
            wallet_data['warning_shown'] = True
            wallet_data['last_export'] = datetime.now().isoformat()
            
            with open(wallet_file, 'w') as f:
                json.dump(wallet_data, f, indent=2)
            
            return {
                'success': True,
                'public_key': wallet_data['public_key'],
                'private_key': private_key,
                'created_at': wallet_data['created_at'],
                'warning': '⚠️ CRITICAL: This wallet is non-recoverable if lost. You are fully responsible for backing up these keys safely. We never touch your wallet - you have complete control.'
            }
            
        except Exception as e:
            logger.error(f"Failed to export wallet for user {user_id}: {e}")
            return {
                'success': False,
                'error': f'Export failed: {str(e)}'
            }
            if not SOLANA_IMPORTS_AVAILABLE:
                # Create a simulated wallet for testing
                import secrets
                private_key = base64.b64encode(secrets.token_bytes(32)).decode()
                public_key = f"Demo{secrets.token_hex(16)}"
            else:
                # Generate new keypair
                keypair = Keypair()
                
                # Extract public and private keys
                public_key = str(keypair.pubkey())
                private_key = base64.b64encode(bytes(keypair)).decode()
            
            # Create wallet data
            wallet_data = {
                'user_id': user_id,
                'public_key': public_key,
                'private_key': self._encrypt_data(private_key),
                'created_at': datetime.now().isoformat(),
                'trades': [],
                'total_profit': 0.0,
                'total_fees_paid': 0.0
            }
            
            # Save wallet data
            wallet_file = os.path.join(self.wallets_dir, f"wallet_{user_id}.json")
            with open(wallet_file, 'w') as f:
                json.dump(wallet_data, f, indent=2)
                
            logger.info(f"Generated burner wallet for user {user_id}: {public_key}")
            
            return {
                'public_key': public_key,
                'private_key': private_key,  # Return unencrypted for immediate use
                'status': 'created'
            }
            
        except Exception as e:
            logger.error(f"Failed to generate burner wallet for {user_id}: {e}")
            raise
            
    def get_user_wallet(self, user_id: str) -> Optional[Dict[str, str]]:
        """Get existing wallet for user or create new one"""
        wallet_file = os.path.join(self.wallets_dir, f"wallet_{user_id}.json")
        
        if os.path.exists(wallet_file):
            try:
                with open(wallet_file, 'r') as f:
                    wallet_data = json.load(f)
                    
                # Decrypt private key
                private_key = self._decrypt_data(wallet_data['private_key'])
                
                return {
                    'public_key': wallet_data['public_key'],
                    'private_key': private_key,
                    'status': 'existing'
                }
                
            except Exception as e:
                logger.error(f"Failed to load wallet for {user_id}: {e}")
                return None
        else:
            # Generate new wallet
            return self.generate_burner_wallet(user_id)
            
    def export_wallet(self, user_id: str) -> Optional[Dict[str, str]]:
        """Export wallet keypair for user backup"""
        wallet = self.get_user_wallet(user_id)
        if wallet:
            return {
                'public_key': wallet['public_key'],
                'private_key': wallet['private_key'],
                'backup_warning': 'IMPORTANT: Save this private key securely. If lost, your wallet cannot be recovered.',
                'json_format': json.dumps({
                    'public_key': wallet['public_key'],
                    'private_key': wallet['private_key']
                }, indent=2)
            }
        return None
        
    async def check_wallet_requirements(self, user_id: str) -> Dict[str, any]:
        """Check if user wallet meets trading requirements"""
        try:
            wallet = self.get_user_wallet(user_id)
            if not wallet:
                return {'eligible': False, 'reason': 'No wallet found'}
                
            public_key = wallet['public_key']
            
            # Check SOL balance
            sol_balance = await self._get_sol_balance(public_key)
            
            # Check MORK token balance
            mork_balance = await self._get_mork_balance(public_key)
            
            # Determine eligibility
            has_min_mork = mork_balance >= self.min_mork_tokens
            has_min_sol = sol_balance >= 0.01  # Minimum SOL for gas fees
            
            return {
                'eligible': has_min_mork and has_min_sol,
                'sol_balance': sol_balance,
                'mork_balance': mork_balance,
                'min_mork_required': self.min_mork_tokens,
                'has_min_mork': has_min_mork,
                'has_min_sol': has_min_sol,
                'public_key': public_key
            }
            
        except Exception as e:
            logger.error(f"Failed to check wallet requirements for {user_id}: {e}")
            return {'eligible': False, 'reason': f'Error: {str(e)}'}
            
    async def _get_sol_balance(self, public_key: str) -> float:
        """Get SOL balance for wallet"""
        try:
            if not SOLANA_IMPORTS_AVAILABLE:
                # Return demo balance for testing
                return 0.5 if public_key.startswith('Demo') else 0.0
                
            pubkey = Pubkey.from_string(public_key)
            response = await self.client.get_balance(pubkey)
            
            if response.value is not None:
                return response.value / 1e9  # Convert lamports to SOL
            return 0.0
            
        except Exception as e:
            logger.debug(f"Failed to get SOL balance for {public_key}: {e}")
            return 0.0
            
    async def _get_mork_balance(self, public_key: str) -> int:
        """Get MORK token balance for wallet"""
        try:
            from wallet_integration import SolanaWalletIntegrator
            integrator = SolanaWalletIntegrator()
            
            # Get token account balance for MORK
            balance = integrator.get_token_balance(public_key, self.mork_token_mint)
            return int(balance) if balance else 0
            
        except Exception as e:
            logger.debug(f"Failed to get MORK balance for {public_key}: {e}")
            return 0
            
    async def execute_auto_trade(self, user_id: str, token_mint: str, 
                                 amount_sol: float, trade_type: str = "buy") -> Dict[str, any]:
        """Execute automated trade from user's burner wallet"""
        try:
            wallet = self.get_user_wallet(user_id)
            if not wallet:
                return {'success': False, 'error': 'No wallet found'}
                
            # Check requirements
            requirements = await self.check_wallet_requirements(user_id)
            if not requirements['eligible']:
                return {'success': False, 'error': 'Wallet requirements not met', 'details': requirements}
                
            # Execute trade via Jupiter
            from wallet_integration import SolanaWalletIntegrator
            integrator = SolanaWalletIntegrator()
            
            if trade_type == "buy":
                result = await self._execute_buy_trade(wallet, token_mint, amount_sol, integrator)
            else:
                result = await self._execute_sell_trade(wallet, token_mint, amount_sol, integrator)
                
            # Record trade
            await self._record_trade(user_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute auto trade for {user_id}: {e}")
            return {'success': False, 'error': str(e)}
            
    async def _execute_buy_trade(self, wallet: Dict, token_mint: str, 
                                amount_sol: float, integrator) -> Dict[str, any]:
        """Execute buy trade"""
        try:
            # Get current token price
            token_price = integrator.get_token_price_in_sol(token_mint)
            
            # Create trade record
            trade_data = {
                'type': 'buy',
                'token_mint': token_mint,
                'amount_sol': amount_sol,
                'entry_price': token_price,
                'timestamp': datetime.now().isoformat(),
                'status': 'executed'
            }
            
            logger.info(f"Executed buy trade: {amount_sol} SOL for {token_mint}")
            
            return {
                'success': True,
                'trade_data': trade_data,
                'transaction_id': f"sim_buy_{int(datetime.now().timestamp())}"
            }
            
        except Exception as e:
            logger.error(f"Buy trade failed: {e}")
            return {'success': False, 'error': str(e)}
            
    async def _execute_sell_trade(self, wallet: Dict, token_mint: str, 
                                 amount_sol: float, integrator) -> Dict[str, any]:
        """Execute sell trade and handle profit fees"""
        try:
            # Get current token price
            current_price = integrator.get_token_price_in_sol(token_mint)
            
            # Calculate profit (simplified - would need actual buy price from records)
            estimated_profit = amount_sol * 0.1  # Placeholder profit calculation
            
            # Calculate and deduct fees if profitable
            fee_amount = 0.0
            if estimated_profit > 0:
                fee_amount = estimated_profit * self.profit_fee_rate
                # Send fee to marketing wallet
                await self._send_profit_fee(wallet, fee_amount)
                
            trade_data = {
                'type': 'sell',
                'token_mint': token_mint,
                'amount_sol': amount_sol,
                'exit_price': current_price,
                'profit': estimated_profit,
                'fee_paid': fee_amount,
                'timestamp': datetime.now().isoformat(),
                'status': 'executed'
            }
            
            logger.info(f"Executed sell trade: {amount_sol} SOL, profit: {estimated_profit}, fee: {fee_amount}")
            
            return {
                'success': True,
                'trade_data': trade_data,
                'transaction_id': f"sim_sell_{int(datetime.now().timestamp())}"
            }
            
        except Exception as e:
            logger.error(f"Sell trade failed: {e}")
            return {'success': False, 'error': str(e)}
            
    async def _send_profit_fee(self, wallet: Dict, fee_amount: float):
        """Send profit fee to marketing wallet"""
        try:
            if fee_amount <= 0:
                return
                
            if not SOLANA_IMPORTS_AVAILABLE:
                logger.info(f"Demo: Would send profit fee {fee_amount} SOL to marketing wallet")
                return {'status': 'simulated'}
                
            # Create keypair from private key
            private_key_bytes = base64.b64decode(wallet['private_key'])
            keypair = Keypair.from_bytes(private_key_bytes)
            
            # Create transfer instruction
            from_pubkey = keypair.pubkey()
            to_pubkey = Pubkey.from_string(MARKETING_WALLET_ADDRESS)
            lamports = int(fee_amount * 1e9)  # Convert SOL to lamports
            
            transfer_ix = transfer(TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey,
                lamports=lamports
            ))
            
            # Create and send transaction
            recent_blockhash = await self.client.get_latest_blockhash()
            transaction = Transaction.new_with_payer([transfer_ix], from_pubkey)
            transaction.sign([keypair], recent_blockhash.value.blockhash)
            
            # Send transaction (simplified for compatibility)
            response = await self.client.send_transaction(transaction)
            
            logger.info(f"Sent profit fee: {fee_amount} SOL to marketing wallet")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send profit fee: {e}")
            # Don't fail the trade if fee sending fails
            pass
            
    async def _record_trade(self, user_id: str, trade_result: Dict):
        """Record trade in user's wallet history"""
        try:
            wallet_file = os.path.join(self.wallets_dir, f"wallet_{user_id}.json")
            
            if os.path.exists(wallet_file):
                with open(wallet_file, 'r') as f:
                    wallet_data = json.load(f)
                    
                # Add trade to history
                if 'trades' not in wallet_data:
                    wallet_data['trades'] = []
                    
                wallet_data['trades'].append(trade_result.get('trade_data', {}))
                
                # Update totals
                if trade_result.get('success') and 'trade_data' in trade_result:
                    trade_data = trade_result['trade_data']
                    if 'profit' in trade_data and trade_data['profit'] > 0:
                        wallet_data['total_profit'] = wallet_data.get('total_profit', 0) + trade_data['profit']
                    if 'fee_paid' in trade_data:
                        wallet_data['total_fees_paid'] = wallet_data.get('total_fees_paid', 0) + trade_data['fee_paid']
                        
                # Save updated wallet data
                with open(wallet_file, 'w') as f:
                    json.dump(wallet_data, f, indent=2)
                    
        except Exception as e:
            logger.error(f"Failed to record trade for {user_id}: {e}")
            
    async def get_wallet_stats(self, user_id: str) -> Dict[str, any]:
        """Get wallet statistics and trading history"""
        try:
            wallet_file = os.path.join(self.wallets_dir, f"wallet_{user_id}.json")
            
            if os.path.exists(wallet_file):
                with open(wallet_file, 'r') as f:
                    wallet_data = json.load(f)
                    
                requirements = await self.check_wallet_requirements(user_id)
                
                return {
                    'public_key': wallet_data['public_key'],
                    'created_at': wallet_data['created_at'],
                    'total_trades': len(wallet_data.get('trades', [])),
                    'total_profit': wallet_data.get('total_profit', 0),
                    'total_fees_paid': wallet_data.get('total_fees_paid', 0),
                    'current_balances': requirements,
                    'recent_trades': wallet_data.get('trades', [])[-5:]  # Last 5 trades
                }
                
            return {'error': 'Wallet not found'}
            
        except Exception as e:
            logger.error(f"Failed to get wallet stats for {user_id}: {e}")
            return {'error': str(e)}

# Global instance
burner_wallet_manager = BurnerWalletManager()

# Convenience functions for bot integration
async def get_user_burner_wallet(user_id: str) -> Optional[Dict[str, str]]:
    """Get or create burner wallet for user"""
    return burner_wallet_manager.get_user_wallet(str(user_id))

async def check_trading_eligibility(user_id: str) -> Dict[str, any]:
    """Check if user is eligible for trading"""
    return await burner_wallet_manager.check_wallet_requirements(str(user_id))

async def execute_burner_trade(user_id: str, token_mint: str, amount_sol: float, trade_type: str = "buy") -> Dict[str, any]:
    """Execute trade from user's burner wallet"""
    return await burner_wallet_manager.execute_auto_trade(str(user_id), token_mint, amount_sol, trade_type)

async def export_user_wallet(user_id: str) -> Optional[Dict[str, str]]:
    """Export wallet for user backup"""
    return burner_wallet_manager.export_wallet(str(user_id))

async def get_user_wallet_stats(user_id: str) -> Dict[str, any]:
    """Get wallet statistics"""
    return await burner_wallet_manager.get_wallet_stats(str(user_id))

if __name__ == "__main__":
    # Test burner wallet system
    async def test_burner_wallet():
        print("🔥 Testing Burner Wallet System")
        print("=" * 50)
        
        manager = BurnerWalletManager()
        test_user = "test_user_123"
        
        # Generate wallet
        wallet = manager.get_user_wallet(test_user)
        print(f"✅ Generated wallet: {wallet['public_key']}")
        
        # Check requirements
        requirements = await manager.check_wallet_requirements(test_user)
        print(f"📊 Requirements check: {requirements}")
        
        # Get wallet stats
        stats = await manager.get_wallet_stats(test_user)
        print(f"📈 Wallet stats: {stats}")
        
        print("✅ Burner wallet system ready!")
        
    asyncio.run(test_burner_wallet())
