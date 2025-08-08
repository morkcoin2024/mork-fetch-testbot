#!/usr/bin/env python3
"""
Start monitoring system - FREEZE DEBUG
"""

import asyncio
import sys
sys.path.append('.')

async def test_freeze_issue():
    """Test the exact freeze issue"""
    print("TESTING FREEZE ISSUE AT PHASE 1")
    print("=" * 40)
    
    from automated_pump_trader import AutomatedPumpTrader
    from burner_wallet_system import BurnerWalletManager
    from app import app
    
    trader = AutomatedPumpTrader()
    manager = BurnerWalletManager()
    
    with app.app_context():
        # Create test wallet
        wallet = manager.get_user_wallet("freeze_test")
        
        print(f"Created test wallet: {wallet['public_key'][:10]}...")
        print("Starting automated trading (this is where it might freeze)...")
        
        try:
            # This is where it's freezing
            result = await asyncio.wait_for(
                trader.execute_automated_trading("freeze_test", wallet, 0.1),
                timeout=30.0  # 30 second maximum
            )
            
            print(f"✅ Trading completed without freezing!")
            print(f"Result: {result.get('success', False)}")
            
        except asyncio.TimeoutError:
            print(f"❌ FREEZE CONFIRMED - System timed out at 30 seconds")
            print("This confirms the freeze issue is still present")
            
        except Exception as e:
            print(f"❌ Error occurred: {e}")

def main():
    """Run freeze test"""
    asyncio.run(test_freeze_issue())

if __name__ == "__main__":
    main()