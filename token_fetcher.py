# token_fetcher.py
# Replace the stubs with real data calls later (Pump.fun, DexScreener, Helius)
import random


def recent(n: int):
    """Return n fake tokens for now (so commands are testable today)"""
    out = []
    for i in range(n):
        # Add some randomness to make testing more realistic
        age_variance = random.randint(30, 3600)  # 30 seconds to 1 hour
        price_base = 0.001 * (i + 1)
        price = round(price_base * random.uniform(0.5, 2.0), 6)
        holders_base = 10 + i
        holders = holders_base + random.randint(0, 500)

        out.append(
            {
                "mint": f"FAKE{i:04d}M1NTxxxxxxxxxxxxxxxxxxxxxx",
                "symbol": f"TKN{i}",
                "price": price,
                "usd_price": price,  # Add for compatibility
                "fdv": 100000 * (i + 1),
                "lp": 5000 * (i + 1),
                "age": age_variance,
                "age_seconds": age_variance,  # Add for compatibility
                "holders": holders,
                "holder_count": holders,  # Add for compatibility
                "buy_tax": 0,
                "sell_tax": 0,
                "renounced": False,
                "mint_revoked": False,
                "liquidity_locked": True,
            }
        )
    return out


def lookup(q: str):
    """If q looks like a mint, return a single dict; else simulate symbol"""
    return {
        "mint": q if len(q) > 20 else f"{q}_FAKEM1NTxxxxxxxxxxxxxxxxxxxxx",
        "symbol": q if len(q) <= 10 else "TKN",
        "price": 0.0042,
        "usd_price": 0.0042,  # Add for compatibility
        "fdv": 420000,
        "lp": 20000,
        "age": 1234,
        "age_seconds": 1234,  # Add for compatibility
        "holders": 321,
        "holder_count": 321,  # Add for compatibility
        "buy_tax": 0,
        "sell_tax": 0,
        "renounced": True,
        "mint_revoked": True,
        "liquidity_locked": True,
    }
