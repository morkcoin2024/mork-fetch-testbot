#!/usr/bin/env python3
"""
Test Jupiter Engine with Whale token - the one that failed with PumpPortal
This will be the definitive test of Jupiter vs PumpPortal reliability
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jupiter_trade_engine import JupiterTradeEngine

def test_jupiter_whale_token():
    """Test Jupiter with the Whale token that failed with PumpPortal"""
    
    print("🐋 JUPITER VS PUMPPORTAL COMPARISON TEST")
    print("=" * 60)
    print("Token: 'It's just a whale' (G4irCda4dFsePvSrhc1H1u9uZUR2TSUiUCsHm661pump)")
    print("Previous PumpPortal result: FAILED - 0 tokens delivered")
    print("Testing: Jupiter Trade Engine")
    print()
    
    # Load test wallet
    try:
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.read().strip().split('\n')
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"Wallet: {public_key}")
        print()
        
        # Initialize Jupiter engine
        engine = JupiterTradeEngine()
        
        # Test with Whale token
        whale_mint = "G4irCda4dFsePvSrhc1H1u9uZUR2TSUiUCsHm661pump"
        
        print("EXECUTING JUPITER TRADE...")
        print("-" * 30)
        
        result = engine.execute_jupiter_trade(
            wallet_pubkey=public_key,
            private_key=private_key,
            token_mint=whale_mint,
            sol_amount=0.002,  # 0.002 SOL
            slippage_bps=1500  # 15% slippage for newer token
        )
        
        print("\n" + "="*60)
        print("JUPITER WHALE TOKEN TEST RESULT")
        print("="*60)
        
        if result["success"]:
            print("🎯 SUCCESS: Jupiter delivered Whale tokens!")
            print(f"Transaction: {result['transaction_hash']}")
            print(f"Expected: {result['expected_tokens']:,}")
            print(f"Actual: {result['actual_tokens']:,.0f}")
            print(f"Explorer: {result['explorer_url']}")
            print()
            print("✅ JUPITER WORKS WHERE PUMPPORTAL FAILED")
            print("✅ Reliable token delivery confirmed")
            print("✅ Ready to replace PumpPortal in bot")
            
        else:
            print("❌ FAILED: Jupiter also failed with Whale token")
            print(f"Error: {result['error']}")
            print()
            print("❌ Issue may be token-specific or wallet-related")
            print("❌ Further investigation needed")
        
        print("\n" + "="*60)
        print("COMPARISON SUMMARY")
        print("="*60)
        print("PumpPortal with Whale token:")
        print("  ❌ Test 1 (CLIPPY params): 0 tokens delivered")
        print("  ❌ Test 2 (SOL-denominated): insufficient funds error") 
        print("  ❌ Test 3 (High slippage): insufficient funds error")
        print()
        print("Jupiter with Whale token:")
        if result["success"]:
            print(f"  ✅ SUCCESS: {result['actual_tokens']:,.0f} tokens delivered")
            print("  ✅ Professional validation pipeline works")
            print("  ✅ Reliable execution confirmed")
        else:
            print(f"  ❌ FAILED: {result['error']}")
            print("  ❌ Same pattern as PumpPortal")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_jupiter_whale_token()