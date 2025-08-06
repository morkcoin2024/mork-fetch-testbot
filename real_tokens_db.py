"""
Real Solana Token Database
Contains verified token contracts that exist on Jupiter DEX
"""

# Real verified Solana tokens with working Jupiter integration
REAL_SOLANA_TOKENS = [
    # Major tokens
    {
        'name': 'Wrapped SOL',
        'symbol': 'SOL',
        'mint': 'So11111111111111111111111111111111111111112',
        'market_cap_range': (50000000, 100000000),
        'is_verified': True
    },
    {
        'name': 'USD Coin',
        'symbol': 'USDC',
        'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
        'market_cap_range': (10000000, 50000000),
        'is_verified': True
    },
    # Popular meme tokens that exist on Jupiter
    {
        'name': 'dogwifhat',
        'symbol': 'WIF',
        'mint': 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm',
        'market_cap_range': (1000000, 5000000),
        'is_verified': True
    },
    {
        'name': 'Bonk',
        'symbol': 'BONK',
        'mint': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
        'market_cap_range': (500000, 2000000),
        'is_verified': True
    },
    {
        'name': 'Jupiter',
        'symbol': 'JUP',
        'mint': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
        'market_cap_range': (1000000, 3000000),
        'is_verified': True
    },
    {
        'name': 'Solana Name Service',
        'symbol': 'FIDA',
        'mint': 'EchesyfXePKdLtoiZSL8pBe8Myagyy8ZRqsACNCFGnvp',
        'market_cap_range': (100000, 500000),
        'is_verified': True
    },
    {
        'name': 'Raydium',
        'symbol': 'RAY',
        'mint': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
        'market_cap_range': (500000, 1500000),
        'is_verified': True
    },
    {
        'name': 'Serum',
        'symbol': 'SRM',
        'mint': 'SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt',
        'market_cap_range': (200000, 800000),
        'is_verified': True
    },
]

# MORK token (our ecosystem token)
MORK_TOKEN = {
    'name': 'Mork Token',
    'symbol': 'MORK',
    'mint': 'ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH',
    'market_cap_range': (2000000, 3000000),
    'is_verified': True,
    'description': 'The official $MORK token - powering the F.E.T.C.H ecosystem'
}

def get_real_token_selection(count: int = 5) -> list:
    """Get a selection of real tokens for discovery simulation"""
    import random
    import time
    
    # Always include MORK token (20% frequency - 1 in 5)
    selected_tokens = []
    
    # Select random real tokens
    available_tokens = REAL_SOLANA_TOKENS.copy()
    random.shuffle(available_tokens)
    
    for i in range(count):
        if (i + 1) % 5 == 0:  # Every 5th token is MORK
            token = MORK_TOKEN.copy()
        else:
            if available_tokens:
                token = available_tokens.pop().copy()
            else:
                # Refill if we run out
                available_tokens = REAL_SOLANA_TOKENS.copy()
                random.shuffle(available_tokens)
                token = available_tokens.pop().copy()
        
        # Add realistic "fresh launch" characteristics
        market_cap_min, market_cap_max = token.get('market_cap_range', (500, 500000))
        
        # Scale down for "fresh launch" simulation
        fresh_min = max(500, market_cap_min // 1000)
        fresh_max = min(500000, market_cap_max // 100)
        
        token.update({
            'usd_market_cap': random.randint(fresh_min, fresh_max),
            'holder_count': random.randint(50, 300),
            'volume_24h': random.randint(5000, 25000),
            'price': random.uniform(0.000001, 0.05),
            'liquidity_usd': random.randint(1000, 10000),
            'risk_level': random.choice(['LOW', 'MEDIUM', 'HIGH']),
            'is_renounced': random.choice([True, False]),
            'is_burnt': random.choice([True, False]),
            'created_timestamp': int(time.time()) - random.randint(30, 1800),
            'age_minutes': random.randint(1, 30)
        })
        
        # Add description if not present
        if 'description' not in token:
            descriptions = [
                f"🚀 {token['name']} - trending on Jupiter DEX",
                f"💎 Popular {token['symbol']} token with growing community",
                f"⚡ {token['name']} - verified token on Solana blockchain",
                f"🔥 High-volume {token['symbol']} trading on DEX platforms"
            ]
            token['description'] = random.choice(descriptions)
        
        selected_tokens.append(token)
    
    return selected_tokens