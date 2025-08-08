#!/usr/bin/env python3
"""
Alternative approach: Try Jupiter DEX API for token trading
Since PumpPortal may have specific requirements we're missing
"""
import requests
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def test_jupiter_trading():
    """Test Jupiter DEX for token trading as alternative to PumpPortal"""
    print("🪐 JUPITER DEX TRADING TEST")
    print(f"Time: {datetime.now()}")
    print("Alternative: Jupiter DEX instead of PumpPortal")
    print("Reason: PumpPortal 400 errors may need specific setup")
    print("=" * 60)
    
    try:
        # Read test wallet
        with open('test_wallet_info.txt', 'r') as f:
            lines = f.readlines()
            public_key = lines[0].split(': ')[1].strip()
            private_key = lines[1].split(': ')[1].strip()
        
        print(f"📍 Wallet: {public_key}")
        
        # Clippy token
        clippy_token = "7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump"
        sol_token = "So11111111111111111111111111111111111111112"  # Wrapped SOL
        
        # Step 1: Get Jupiter quote
        quote_url = "https://quote-api.jup.ag/v6/quote"
        quote_params = {
            "inputMint": sol_token,
            "outputMint": clippy_token,
            "amount": str(int(0.01 * 1_000_000_000)),  # 0.01 SOL in lamports
            "slippageBps": 1000  # 10% slippage
        }
        
        print(f"\n📤 Getting Jupiter quote...")
        quote_response = requests.get(quote_url, params=quote_params)
        
        if quote_response.status_code == 200:
            quote_data = quote_response.json()
            print("✅ Jupiter quote received")
            print(f"Input: {quote_data.get('inAmount', 'N/A')} lamports SOL")
            print(f"Output: {quote_data.get('outAmount', 'N/A')} tokens")
            print(f"Price impact: {quote_data.get('priceImpactPct', 'N/A')}%")
            
            # Step 2: Get swap transaction
            swap_url = "https://quote-api.jup.ag/v6/swap"
            swap_payload = {
                "userPublicKey": public_key,
                "quoteResponse": quote_data,
                "wrapAndUnwrapSol": True,
                "computeUnitPriceMicroLamports": 5000  # Priority fee
            }
            
            print(f"\n📤 Getting Jupiter swap transaction...")
            swap_response = requests.post(swap_url, json=swap_payload)
            
            if swap_response.status_code == 200:
                swap_data = swap_response.json()
                print("🎉 SUCCESS: Jupiter swap transaction received!")
                
                # Extract transaction
                swap_transaction = swap_data.get('swapTransaction')
                if swap_transaction:
                    print(f"✅ Transaction data: {len(swap_transaction)} characters")
                    print(f"🎯 Ready for signing and sending")
                    
                    return {
                        'success': True,
                        'method': 'jupiter',
                        'quote_received': True,
                        'transaction_received': True,
                        'transaction_data': swap_transaction,
                        'in_amount': quote_data.get('inAmount'),
                        'out_amount': quote_data.get('outAmount'),
                        'ready_for_execution': True
                    }
                else:
                    print("❌ No transaction in response")
                    return {'success': False, 'error': 'No transaction data'}
            else:
                error_text = swap_response.text
                print(f"❌ Swap error {swap_response.status_code}: {error_text}")
                return {
                    'success': False, 
                    'quote_success': True,
                    'swap_error': error_text,
                    'status_code': swap_response.status_code
                }
        else:
            error_text = quote_response.text
            print(f"❌ Quote error {quote_response.status_code}: {error_text}")
            return {
                'success': False,
                'quote_error': error_text,
                'status_code': quote_response.status_code
            }
            
    except Exception as e:
        print(f"💥 Exception: {e}")
        return {'success': False, 'error': str(e)}

async def main():
    result = await test_jupiter_trading()
    
    print("\n" + "=" * 60)
    print("🏁 JUPITER TRADING TEST SUMMARY:")
    
    for key, value in result.items():
        if key != 'transaction_data':  # Don't print long transaction data
            print(f"{key}: {value}")
    
    if result.get('ready_for_execution'):
        print("\n🎉 COMPLETE SUCCESS: Alternative trading method working")
        print("✅ Jupiter DEX integration functional")
        print("✅ Transaction ready for execution")
        print("🎯 Can proceed with transaction signing and sending")
        print("💡 Alternative to PumpPortal issues resolved")
    elif result.get('quote_success'):
        print("\n🟡 PARTIAL SUCCESS: Quote working but swap issues")
        print("✅ Jupiter API accessible")
        print("🔧 Need to debug swap parameters")
    else:
        print("\n🔴 JUPITER INTEGRATION ISSUES")
        print("Need to investigate Jupiter API parameters")
    
    return result

if __name__ == "__main__":
    asyncio.run(main())