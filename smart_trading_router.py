"""
Smart Trading Router - Determines optimal trading platform based on token characteristics
Implements user rule: Pump tokens → Pump.fun (unless bonded) → Jupiter for bonded tokens
"""
import logging
import requests
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class SmartTradingRouter:
    """Routes trades to optimal platform based on token analysis"""
    
    def __init__(self):
        self.pump_fun_program_id = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        
    def analyze_token_platform(self, token_mint: str, token_symbol: str = "") -> Dict:
        """
        Analyze token to determine optimal trading platform
        Rules:
        1. If symbol ends with "pump" → Check if bonded
        2. If bonded → Use Jupiter
        3. If not bonded → Use Pump.fun
        4. All other tokens → Jupiter by default
        """
        try:
            logger.info(f"Analyzing trading platform for {token_symbol} ({token_mint[:8]}...)")
            
            # Check if token name/symbol suggests Pump.fun origin
            is_pump_token = token_symbol.lower().endswith("pump") if token_symbol else False
            
            if is_pump_token:
                logger.info(f"Token {token_symbol} ends with 'pump' - checking bonding status")
                
                # Check if token has graduated from bonding curve
                bonding_status = self._check_bonding_curve_status(token_mint)
                
                if bonding_status.get("is_bonded", False):
                    platform = "jupiter"
                    reason = f"Pump token {token_symbol} has bonded - using Jupiter DEX"
                    logger.info(f"✅ {reason}")
                else:
                    platform = "pump_fun"  
                    reason = f"Pump token {token_symbol} still on bonding curve - using Pump.fun"
                    logger.info(f"✅ {reason}")
                    
            else:
                # For VIP FETCH discovered tokens, assume they're from pump.fun
                platform = "pump_fun"
                reason = f"Token {token_symbol or 'UNKNOWN'} from VIP FETCH - using Pump.fun bonding curve"
                logger.info(f"✅ {reason}")
            
            return {
                "success": True,
                "platform": platform,
                "reason": reason,
                "is_pump_token": is_pump_token,
                "bonding_status": bonding_status if is_pump_token else None
            }
            
        except Exception as e:
            logger.error(f"Platform analysis failed: {e}")
            # Fallback to Jupiter for safety
            return {
                "success": False,
                "platform": "jupiter",
                "reason": f"Analysis failed, defaulting to Jupiter: {str(e)}",
                "is_pump_token": False,
                "error": str(e)
            }
    
    async def execute_smart_trade(self, private_key: str, token_mint: str, token_symbol: str, 
                                sol_amount: float, trade_type: str) -> Dict:
        """Execute a smart trade using optimal platform routing"""
        try:
            logger.info(f"Executing {trade_type} trade for {token_symbol} ({sol_amount} SOL)")
            
            # Analyze best platform for this token
            platform_analysis = self.analyze_token_platform(token_mint, token_symbol)
            
            if not platform_analysis.get("success"):
                logger.error(f"Platform analysis failed: {platform_analysis.get('error')}")
                return {
                    'success': False,
                    'error': f"Platform routing failed: {platform_analysis.get('error')}"
                }
            
            optimal_platform = platform_analysis.get("platform")
            logger.info(f"Routing {trade_type} trade to {optimal_platform}: {platform_analysis.get('reason')}")
            
            # Route to appropriate trading platform
            if optimal_platform == "pump_fun":
                return await self._execute_pump_fun_trade(private_key, token_mint, token_symbol, sol_amount, trade_type)
            elif optimal_platform == "jupiter":
                return await self._execute_jupiter_trade(private_key, token_mint, token_symbol, sol_amount, trade_type)
            else:
                return {
                    'success': False,
                    'error': f"Unknown platform: {optimal_platform}"
                }
                
        except Exception as e:
            logger.error(f"Smart trade execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_pump_fun_trade(self, private_key: str, token_mint: str, token_symbol: str, 
                                    sol_amount: float, trade_type: str) -> Dict:
        """Execute trade on Pump.fun bonding curve"""
        try:
            logger.info(f"Executing {trade_type} on Pump.fun for {token_symbol}")
            
            # Import and use pump.fun trading system
            from pump_fun_trading import execute_pump_fun_trade
            
            result = await execute_pump_fun_trade(
                private_key=private_key,
                token_contract=token_mint,
                sol_amount=sol_amount,
                action=trade_type
            )
            
            if result.get('success'):
                logger.info(f"✅ Pump.fun {trade_type} successful: {result.get('transaction_hash', 'No hash')}")
                return {
                    'success': True,
                    'transaction_hash': result.get('transaction_hash'),
                    'sol_spent': result.get('sol_spent', sol_amount),
                    'tokens_received': result.get('tokens_received', 0),
                    'platform': 'pump_fun'
                }
            else:
                logger.error(f"❌ Pump.fun {trade_type} failed: {result.get('error')}")
                return {
                    'success': False,
                    'error': f"Pump.fun trade failed: {result.get('error')}"
                }
                
        except Exception as e:
            logger.error(f"Pump.fun trade execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_jupiter_trade(self, private_key: str, token_mint: str, token_symbol: str, 
                                   sol_amount: float, trade_type: str) -> Dict:
        """Execute trade on Jupiter DEX"""
        try:
            logger.info(f"Executing {trade_type} on Jupiter for {token_symbol}")
            
            # Import Jupiter integration
            from wallet_integration import create_jupiter_swap_transaction
            
            if trade_type == "buy":
                # SOL → Token
                result = create_jupiter_swap_transaction(
                    private_key=private_key,
                    input_mint="So11111111111111111111111111111111111111112",  # SOL
                    output_mint=token_mint,
                    amount=int(sol_amount * 1_000_000_000)  # Convert SOL to lamports
                )
            else:  # sell
                # Token → SOL
                result = create_jupiter_swap_transaction(
                    private_key=private_key,
                    input_mint=token_mint,
                    output_mint="So11111111111111111111111111111111111111112",  # SOL
                    amount=0  # Need to calculate token balance
                )
            
            if result.get('success'):
                logger.info(f"✅ Jupiter {trade_type} successful: {result.get('transaction_hash', 'No hash')}")
                return {
                    'success': True,
                    'transaction_hash': result.get('transaction_hash'),
                    'sol_spent': result.get('sol_spent', sol_amount),
                    'tokens_received': result.get('tokens_received', 0),
                    'platform': 'jupiter'
                }
            else:
                logger.error(f"❌ Jupiter {trade_type} failed: {result.get('error')}")
                return {
                    'success': False,
                    'error': f"Jupiter trade failed: {result.get('error')}"
                }
                
        except Exception as e:
            logger.error(f"Jupiter trade execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_bonding_curve_status(self, token_mint: str) -> Dict:
        """
        Check if a pump token has graduated from bonding curve to DEX
        Returns bonding curve status and liquidity information
        """
        try:
            # Method 1: Check Pump.fun API for bonding curve status
            pump_api_url = f"https://frontend-api.pump.fun/coins/{token_mint}"
            
            try:
                response = requests.get(pump_api_url, timeout=10)
                if response.status_code == 200:
                    pump_data = response.json()
                    
                    # Check if token is still on bonding curve or has graduated
                    market_cap = pump_data.get('market_cap', 0)
                    is_complete = pump_data.get('complete', False)
                    
                    # Pump.fun tokens "complete" when they reach ~$69K market cap and graduate to Raydium
                    is_bonded = is_complete or market_cap >= 69000
                    
                    logger.info(f"Pump.fun status: Market cap ${market_cap:,}, Complete: {is_complete}")
                    
                    return {
                        "success": True,
                        "is_bonded": is_bonded,
                        "market_cap": market_cap,
                        "is_complete": is_complete,
                        "source": "pump_fun_api"
                    }
                    
            except Exception as api_error:
                logger.warning(f"Pump.fun API check failed: {api_error}")
            
            # Method 2: Check Jupiter for DEX liquidity (indicates bonding completion)
            try:
                jupiter_price_url = f"https://price.jup.ag/v4/price?ids={token_mint}"
                response = requests.get(jupiter_price_url, timeout=10)
                
                if response.status_code == 200:
                    price_data = response.json()
                    
                    if token_mint in price_data.get('data', {}):
                        # Token exists on Jupiter = likely bonded and on DEX
                        logger.info(f"Token found on Jupiter - likely bonded")
                        return {
                            "success": True,
                            "is_bonded": True,
                            "source": "jupiter_pricing",
                            "jupiter_data": price_data['data'][token_mint]
                        }
                
            except Exception as jupiter_error:
                logger.warning(f"Jupiter price check failed: {jupiter_error}")
            
            # Method 3: Default assumption for pump tokens
            # If we can't determine status, assume still on bonding curve (safer)
            logger.info(f"Could not determine bonding status - assuming still on Pump.fun bonding curve")
            return {
                "success": True,
                "is_bonded": False,
                "source": "default_assumption",
                "note": "Status unknown, defaulting to Pump.fun"
            }
            
        except Exception as e:
            logger.error(f"Bonding status check failed: {e}")
            return {
                "success": False,
                "is_bonded": False,  # Default to safer Pump.fun
                "error": str(e)
            }
    


# Global smart router instance
smart_trading_router = SmartTradingRouter()