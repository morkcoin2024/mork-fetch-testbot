# prices.py
import time
import requests
import logging

log = logging.getLogger(__name__)

_CACHE = {"sol": {"price": None, "ts": 0}}

def _fetch_sol_price_usd():
    """
    Fetch real SOL price from CoinGecko API.
    Returns float price in USD.
    """
    try:
        # CoinGecko free API - no auth required
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        price = float(data["solana"]["usd"])
        log.info(f"[PRICES] SOL price fetched: ${price:.2f}")
        return price
        
    except requests.exceptions.RequestException as e:
        log.warning(f"[PRICES] Network error fetching SOL price: {e}")
        raise
    except (KeyError, ValueError, TypeError) as e:
        log.warning(f"[PRICES] Parse error for SOL price: {e}")
        raise
    except Exception as e:
        log.error(f"[PRICES] Unexpected error fetching SOL price: {e}")
        raise

def get_sol_price_usd(cache_secs: int = 60):
    """
    Get SOL price in USD with intelligent caching and fallback.
    
    Args:
        cache_secs: Cache duration in seconds (default 60s)
        
    Returns:
        float: SOL price in USD, or cached/fallback value if fetch fails
    """
    now = time.time()
    c = _CACHE["sol"]
    
    # Return cached price if still valid
    if c["price"] is not None and now - c["ts"] < cache_secs:
        return c["price"]
    
    try:
        # Fetch fresh price
        price = float(_fetch_sol_price_usd())
        _CACHE["sol"] = {"price": price, "ts": now}
        return price
        
    except Exception as e:
        log.warning(f"[PRICES] Failed to fetch SOL price, using fallback: {e}")
        
        # Return last known price if available
        if c["price"] is not None:
            log.info(f"[PRICES] Using cached SOL price: ${c['price']:.2f}")
            return c["price"]
            
        # Final fallback - reasonable default price
        log.warning("[PRICES] Using default SOL price: $200.00")
        return 200.0