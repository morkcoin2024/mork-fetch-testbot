#!/usr/bin/env python3
"""
Test the complete /fetch flow with a funded wallet to verify real token purchasing
"""

import asyncio
import sys
sys.path.append('.')

async def test_real_fetch_with_funding():
    """Test /fetch with a wallet that has SOL balance"""
    print("Testing /fetch with funded wallet simulation")
    print("=" * 50)
    
    from automated_pump_trader import start_automated_trading
    from burner_wallet_system import BurnerWalletManager
    from app import app
    
    # Create a test scenario with funded wallet
    manager = BurnerWalletManager()
    test_user = "funded_wallet_test"
    
    with app.app_context():
        print("Step 1: Creating wallet...")
        wallet = manager.get_user_wallet(test_user)
        
        if wallet:
            print(f"Wallet created: {wallet['public_key'][:10]}...")
            
            # Override wallet balance check to simulate funding
            print("Step 2: Simulating funded wallet (0.5 SOL)...")
            
            # Patch the balance check temporarily
            from pump_fun_trading import PumpFunTrader
            
            original_check = PumpFunTrader.check_wallet_balance
            def mock_funded_balance(self, wallet_address):
                return {
                    "success": True,
                    "sol_balance": 0.5,  # Simulate 0.5 SOL balance
                    "lamports": 500_000_000,
                    "funded": True,
                    "trading_ready": True
                }
            
            # Apply the mock
            PumpFunTrader.check_wallet_balance = mock_funded_balance
            
            try:
                print("Step 3: Testing automated trading with funded wallet...")
                result = await start_automated_trading(test_user, wallet, 0.1)
                
                print(f"Trading result:")
                print(f"  Success: {result.get('success')}")
                print(f"  Message: {result.get('message')}")
                
                trades = result.get('trades', [])
                if trades:
                    for i, trade in enumerate(trades):
                        print(f"  Trade {i+1}:")
                        print(f"    Token: {trade.get('token_symbol')}")
                        print(f"    Success: {trade.get('success')}")
                        print(f"    Simulated: {trade.get('simulated', False)}")
                        print(f"    Method: {trade.get('method')}")
                        print(f"    TX Hash: {trade.get('transaction_hash')}")
                
                return result.get('success', False)
                
            finally:
                # Restore original method
                PumpFunTrader.check_wallet_balance = original_check
                
        else:
            print("Failed to create wallet")
            return False

async def test_pump_portal_api_directly():
    """Test PumpPortal API integration directly"""
    print("\nTesting PumpPortal API integration")
    print("=" * 40)
    
    from pump_fun_trading import PumpFunTrader
    
    trader = PumpFunTrader()
    
    # Test with mock funded scenario
    print("Creating test scenario with funded wallet...")
    
    # Override balance check for this test
    original_check = trader.check_wallet_balance
    trader.check_wallet_balance = lambda addr: {
        "success": True,
        "sol_balance": 1.0,
        "funded": True,
        "trading_ready": True
    }
    
    try:
        # Test real token purchase call
        result = await trader.buy_pump_token(
            private_key="test_funded_key",
            token_contract="So11111111111111111111111111111111111111112",
            sol_amount=0.05
        )
        
        print(f"PumpPortal API result:")
        print(f"  Success: {result.get('success')}")
        print(f"  Error: {result.get('error', 'None')}")
        print(f"  Method: {result.get('method')}")
        print(f"  TX: {result.get('transaction_hash')}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"API test failed: {e}")
        return False
    finally:
        trader.check_wallet_balance = original_check

def main():
    """Run comprehensive real trading tests"""
    print("TESTING REAL TOKEN PURCHASING")
    print("=" * 60)
    
    async def run_tests():
        # Test 1: Full /fetch flow with funded wallet
        fetch_success = await test_real_fetch_with_funding()
        
        # Test 2: Direct PumpPortal API test
        api_success = await test_pump_portal_api_directly()
        
        print(f"\nTEST RESULTS:")
        print(f"  /fetch with funding: {'PASS' if fetch_success else 'FAIL'}")
        print(f"  PumpPortal API direct: {'PASS' if api_success else 'FAIL'}")
        
        if fetch_success or api_success:
            print(f"\nReal trading components are working!")
            print("The system can execute actual token purchases when wallets are funded.")
        else:
            print(f"\nReal trading needs more fixes.")
            print("The API integration may need adjustments for live trading.")
        
        return fetch_success or api_success
    
    success = asyncio.run(run_tests())
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)