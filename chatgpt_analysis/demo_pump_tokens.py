#!/usr/bin/env python3
"""
Demo pump.fun tokens that look realistic for testing
"""
import time
import random

def get_demo_pump_tokens(limit: int = 10):
    """Get realistic-looking pump.fun tokens with fresh timestamps"""
    current_time = int(time.time())
    
    demo_tokens = [
        {
            'mint': 'PumpA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0',
            'name': 'MoonPump',
            'symbol': 'MPUMP',
            'description': 'The ultimate moon mission pump token 🚀',
            'created_timestamp': current_time - random.randint(60, 1800),  # 1-30 mins ago
            'market_cap': random.randint(5000, 25000),
            'usd_market_cap': random.randint(5000, 25000),
            'creator': 'MoonDev123...',
            'bonding_curve': 'BC1...',
            'is_currently_live': True,
            'virtual_sol_reserves': 30 + random.randint(0, 20),
            'virtual_token_reserves': 1000000000,
            'total_supply': 1000000000,
            'nsfw': False,
            'show_name': True
        },
        {
            'mint': 'RocketB2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T1',
            'name': 'DiamondPump',
            'symbol': 'DPUMP', 
            'description': 'Diamond hands only! 💎👐',
            'created_timestamp': current_time - random.randint(120, 900),
            'market_cap': random.randint(8000, 35000),
            'usd_market_cap': random.randint(8000, 35000),
            'creator': 'DiamondDev...',
            'bonding_curve': 'BC2...',
            'is_currently_live': True,
            'virtual_sol_reserves': 30 + random.randint(0, 25),
            'virtual_token_reserves': 1000000000,
            'total_supply': 1000000000,
            'nsfw': False,
            'show_name': True
        },
        {
            'mint': 'LaserC3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T2',
            'name': 'LaserPump',
            'symbol': 'LPUMP',
            'description': 'Laser eyes activated! 👀⚡',
            'created_timestamp': current_time - random.randint(180, 600),
            'market_cap': random.randint(12000, 40000),
            'usd_market_cap': random.randint(12000, 40000),
            'creator': 'LaserDev...',
            'bonding_curve': 'BC3...',
            'is_currently_live': True,
            'virtual_sol_reserves': 30 + random.randint(5, 30),
            'virtual_token_reserves': 1000000000,
            'total_supply': 1000000000,
            'nsfw': False,
            'show_name': True
        },
        {
            'mint': 'RocketD4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T3',
            'name': 'RocketPump',
            'symbol': 'ROCKET',
            'description': 'To the moon and beyond! 🚀🌙',
            'created_timestamp': current_time - random.randint(300, 1200),
            'market_cap': random.randint(15000, 50000),
            'usd_market_cap': random.randint(15000, 50000),
            'creator': 'RocketDev...',
            'bonding_curve': 'BC4...',
            'is_currently_live': True,
            'virtual_sol_reserves': 30 + random.randint(10, 35),
            'virtual_token_reserves': 1000000000,
            'total_supply': 1000000000,
            'nsfw': False,
            'show_name': True
        },
        {
            'mint': 'ApeE5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T4',
            'name': 'ApePump',
            'symbol': 'APE',
            'description': 'Ape together strong! 🦍💪',
            'created_timestamp': current_time - random.randint(240, 800),
            'market_cap': random.randint(18000, 60000),
            'usd_market_cap': random.randint(18000, 60000),
            'creator': 'ApeDev...',
            'bonding_curve': 'BC5...',
            'is_currently_live': True,
            'virtual_sol_reserves': 30 + random.randint(8, 40),
            'virtual_token_reserves': 1000000000,
            'total_supply': 1000000000,
            'nsfw': False,
            'show_name': True
        },
        {
            'mint': 'DogF6G7H8I9J0K1L2M3N4O5P6Q7R8S9T5',
            'name': 'DogPump',
            'symbol': 'DOGP',
            'description': 'Good boy deserves pumps! 🐕',
            'created_timestamp': current_time - random.randint(150, 700),
            'market_cap': random.randint(8000, 28000),
            'usd_market_cap': random.randint(8000, 28000),
            'creator': 'DogDev...',
            'bonding_curve': 'BC6...',
            'is_currently_live': True,
            'virtual_sol_reserves': 30 + random.randint(5, 25),
            'virtual_token_reserves': 1000000000,
            'total_supply': 1000000000,
            'nsfw': False,
            'show_name': True
        }
    ]
    
    return demo_tokens[:limit]

if __name__ == "__main__":
    tokens = get_demo_pump_tokens(5)
    for token in tokens:
        age_mins = (time.time() - token['created_timestamp']) / 60
        print(f"{token['name']} ({token['symbol']}) - ${token['market_cap']:,} - {age_mins:.1f}m old")