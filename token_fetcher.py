# token_fetcher.py
# Mock token data provider for testing the scanner system
import random
import time
from typing import List, Dict, Optional

def recent(n: int) -> List[Dict]:
    """Return n recent tokens with randomized data for testing"""
    out = []
    current_time = int(time.time())
    
    for i in range(n):
        # Add some randomization to make testing more realistic
        age_seconds = random.randint(30, 3600)  # 30 seconds to 1 hour old
        price = random.uniform(0.0001, 0.01)
        holders = random.randint(5, 500)
        fdv = random.randint(50000, 1000000)
        
        out.append({
            "mint": f"FAKE{i:04d}M1NT{random.randint(1000,9999)}xxxxxxxxxxxxxxxxx",
            "symbol": f"TKN{i}",
            "name": f"Test Token {i}",
            "price": round(price, 6),
            "usd_price": round(price, 6),
            "fdv": fdv,
            "market_cap": fdv,
            "lp": random.randint(5000, 50000),
            "age": age_seconds,
            "age_seconds": age_seconds,
            "created_at": current_time - age_seconds,
            "holders": holders,
            "holder_count": holders,
            "buy_tax": 0, 
            "sell_tax": 0,
            "renounced": random.choice([True, False]),
            "mint_revoked": random.choice([True, False]),
            "liquidity_locked": random.choice([True, False]),
            "volume_24h": random.randint(1000, 100000),
            "price_change_24h": random.uniform(-50, 200),  # -50% to +200%
            "source": "mock_data",
            "verified": random.choice([True, False]),
            "rugpull_risk": random.choice(["low", "medium", "high"]),
            "socials": {
                "twitter": f"https://twitter.com/token{i}" if random.choice([True, False]) else None,
                "telegram": f"https://t.me/token{i}" if random.choice([True, False]) else None,
                "website": f"https://token{i}.com" if random.choice([True, False]) else None
            }
        })
    return out

def lookup(q: str) -> Optional[Dict]:
    """Look up a specific token by mint address or symbol"""
    if not q:
        return None
        
    # Simulate realistic lookup data
    price = random.uniform(0.0001, 0.01)
    holders = random.randint(10, 1000)
    current_time = int(time.time())
    age = random.randint(300, 86400)  # 5 minutes to 1 day
    
    return {
        "mint": q if len(q) > 20 else f"{q}_FAKEM1NT{random.randint(1000,9999)}xxxxxxxxxxxx",
        "symbol": q if len(q) <= 10 else "LOOKUP",
        "name": f"Lookup Token {q[:6]}",
        "price": round(price, 6),
        "usd_price": round(price, 6),
        "fdv": random.randint(100000, 2000000),
        "market_cap": random.randint(100000, 2000000),
        "lp": random.randint(10000, 100000),
        "age": age,
        "age_seconds": age,
        "created_at": current_time - age,
        "holders": holders,
        "holder_count": holders,
        "buy_tax": 0, 
        "sell_tax": 0,
        "renounced": True,
        "mint_revoked": True,
        "liquidity_locked": True,
        "volume_24h": random.randint(5000, 200000),
        "price_change_24h": random.uniform(-30, 150),
        "source": "mock_lookup",
        "verified": True,
        "rugpull_risk": "low"
    }

def get_trending(limit: int = 20) -> List[Dict]:
    """Get trending tokens (wrapper around recent for compatibility)"""
    return recent(limit)

def get_new_tokens(limit: int = 20) -> List[Dict]:
    """Get newest tokens (wrapper around recent for compatibility)"""
    tokens = recent(limit)
    # Sort by age (newest first)
    return sorted(tokens, key=lambda x: x.get('age', 0))

# Compatibility functions for existing integrations
def multi_source_fetch(limit: int = 20) -> List[Dict]:
    """Multi-source token fetch simulation"""
    return recent(limit)

def pumpfun_recent(limit: int = 20) -> List[Dict]:
    """Pump.fun specific token fetch simulation"""
    tokens = recent(limit)
    # Add pump.fun specific fields
    for token in tokens:
        token['platform'] = 'pumpfun'
        token['bonding_curve'] = random.choice([True, False])
        token['graduation_progress'] = random.uniform(0, 100)
    return tokens