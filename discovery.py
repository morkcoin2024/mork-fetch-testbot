"""
discovery.py - Token Discovery and Validation
Finds new Pump.fun tokens and validates they are bonded/routable
"""
import logging
import requests
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

PUMPFUN_API = "https://frontend-api.pump.fun/coins"
JUPITER_QUOTE_API = "https://quote-api.jup.ag/v6/quote"
SOL_MINT = "So11111111111111111111111111111111111111112"

def get_pumpfun_new(limit: int = 20) -> List[Dict]:
    """
    Get latest tokens from Pump.fun
    Returns list of token dicts with mint, symbol, name, market_cap, etc.
    """
    try:
        params = {
            "sort": "created_timestamp",
            "order": "DESC", 
            "limit": limit
        }
        
        response = requests.get(PUMPFUN_API, params=params, timeout=15)
        if response.status_code != 200:
            logger.warning(f"Pump.fun API error: {response.status_code}")
            return []
            
        tokens = response.json()
        if not isinstance(tokens, list):
            return []
            
        # Clean and standardize token data
        cleaned_tokens = []
        for token in tokens:
            if not token.get('mint'):
                continue
                
            cleaned_token = {
                'mint': token['mint'],
                'symbol': token.get('symbol', 'UNKNOWN'),
                'name': token.get('name', 'Unknown Token'),
                'market_cap': float(token.get('usd_market_cap', 0)),
                'created_timestamp': token.get('created_timestamp', 0),
                'description': token.get('description', ''),
                'image_uri': token.get('image_uri', ''),
                'website': token.get('website', ''),
                'twitter': token.get('twitter', ''),
                'telegram': token.get('telegram', '')
            }
            cleaned_tokens.append(cleaned_token)
            
        logger.info(f"Found {len(cleaned_tokens)} tokens from Pump.fun")
        return cleaned_tokens
        
    except Exception as e:
        logger.error(f"Pump.fun discovery failed: {e}")
        return []

def is_bonded_and_routable(mint: str, test_amount_sol: float = 0.01) -> tuple[bool, str]:
    """
    Check if token is bonded and has Jupiter routing
    Returns (is_routable, reason)
    """
    try:
        # Test with small SOL amount to see if Jupiter can route
        amount_lamports = int(test_amount_sol * 1_000_000_000)
        
        params = {
            "inputMint": SOL_MINT,
            "outputMint": mint,
            "amount": str(amount_lamports),
            "slippageBps": "300",  # Allow high slippage for test
            "onlyDirectRoutes": "false"
        }
        
        response = requests.get(JUPITER_QUOTE_API, params=params, timeout=15)
        
        if response.status_code != 200:
            return False, f"Jupiter API error: {response.status_code}"
            
        quote_data = response.json()
        
        # Check if we got a valid route
        if not quote_data:
            return False, "No quote data returned"
            
        if "error" in quote_data:
            return False, f"Quote error: {quote_data['error']}"
            
        # Valid quote should have outAmount and routes
        if "outAmount" not in quote_data or not quote_data["outAmount"]:
            return False, "No output amount in quote"
            
        if "routePlan" not in quote_data or not quote_data["routePlan"]:
            return False, "No route plan available"
            
        out_amount = int(quote_data["outAmount"])
        if out_amount <= 0:
            return False, "Zero output tokens"
            
        # If we get here, token is routable
        logger.info(f"Token {mint[:8]}... is routable: {out_amount:,} tokens for {test_amount_sol} SOL")
        return True, f"Routable - {out_amount:,} tokens expected"
        
    except Exception as e:
        logger.error(f"Routability check failed for {mint}: {e}")
        return False, f"Check failed: {e}"

def find_routable_tokens(max_tokens: int = 5) -> List[Dict]:
    """
    Find routable tokens from latest Pump.fun launches
    Returns up to max_tokens that pass bonding/routing checks
    """
    logger.info("Discovering routable tokens...")
    
    # Get latest tokens
    new_tokens = get_pumpfun_new(limit=50)  # Check more tokens to find good ones
    if not new_tokens:
        logger.warning("No tokens found from Pump.fun")
        return []
    
    routable_tokens = []
    
    for token in new_tokens:
        if len(routable_tokens) >= max_tokens:
            break
            
        mint = token['mint']
        logger.info(f"Checking {token['symbol']} ({mint[:8]}...)")
        
        is_routable, reason = is_bonded_and_routable(mint)
        
        if is_routable:
            token['routable'] = True
            token['route_reason'] = reason
            routable_tokens.append(token)
            logger.info(f"✅ {token['symbol']}: {reason}")
        else:
            logger.info(f"❌ {token['symbol']}: {reason}")
            
    logger.info(f"Found {len(routable_tokens)} routable tokens")
    return routable_tokens

# Fallback tokens that are known to be working (for testing)
FALLBACK_TOKENS = [
    {
        'mint': '7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump',
        'symbol': 'DEGEN',
        'name': 'DEGEN Alert',
        'market_cap': 8500,
        'routable': True,
        'route_reason': 'Known working token'
    }
]

def get_working_token() -> Optional[Dict]:
    """Get one guaranteed working token for testing"""
    # Try to find a routable token from recent launches
    routable = find_routable_tokens(max_tokens=1)
    if routable:
        return routable[0]
        
    # Fallback to known working token
    for token in FALLBACK_TOKENS:
        mint = token['mint']
        is_routable, reason = is_bonded_and_routable(mint)
        if is_routable:
            token['route_reason'] = reason
            return token
            
    return None