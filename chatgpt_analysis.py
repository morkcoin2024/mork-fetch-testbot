#!/usr/bin/env python3
"""
ChatGPT Analysis Request - Complete Problem Description
For consultation on Solana pump.fun trading bot implementation
"""

CHATGPT_ANALYSIS_REQUEST = """
# Solana Pump.fun Trading Bot - Implementation Challenge

## PROJECT OVERVIEW
We're building "Mork F.E.T.C.H Bot" - a Telegram cryptocurrency trading bot that automatically discovers and trades newly launched tokens on pump.fun (Solana blockchain). The bot should execute real trades with actual token delivery to user wallets.

## CORE REQUIREMENTS
1. **Automated token discovery** from pump.fun new launches
2. **Real-time trading execution** with actual token acquisition  
3. **Telegram bot interface** for user interaction
4. **Wallet integration** with private key management
5. **Token verification** - must confirm tokens actually arrive in wallet

## CURRENT ARCHITECTURE
- **Python Flask** web application with Telegram webhook
- **PumpPortal API** for transaction generation 
- **Solana RPC** for blockchain interaction
- **SQLAlchemy** for user session management
- **Wallet system** with JSON-stored private keys

## CRITICAL PROBLEM: TOKEN DELIVERY FAILURE

### What Works:
- ✅ Transactions broadcast successfully to Solana blockchain
- ✅ Valid transaction hashes returned  
- ✅ SOL balance decreases (gas fees paid)
- ✅ Blockchain confirms transactions as successful
- ✅ ONE SUCCESS: 7,500 CLIPPY tokens were actually delivered

### What Fails:
- ❌ **Zero tokens delivered** for all other attempts (ESPURR, Whale)
- ❌ **Inconsistent behavior** - same method works for CLIPPY, fails for others
- ❌ **False success indicators** - transactions appear successful but deliver nothing
- ❌ **Wallet balance errors** - "insufficient funds for rent/fee" on some tokens

### Specific Test Results:
```
CLIPPY Token (7eMJmn1bYWSQEwxAX7CyngBzGNGu1cT582asKxxRpump):
✅ SUCCESS - 7,500 tokens delivered and verified in wallet

ESPURR Token: 
❌ FAILED - Transaction succeeded, 0 tokens delivered

Whale Token (G4irCda4dFsePvSrhc1H1u9uZUR2TSUiUCsHm661pump):
❌ FAILED - All 3 parameter variations failed
   - Test 1: Transaction succeeded, 0 tokens delivered
   - Test 2: "insufficient funds for rent" 
   - Test 3: "insufficient funds for fee"
```

## CURRENT IMPLEMENTATION APPROACH

### PumpPortal Lightning Transaction API:
```python
response = requests.post(
    url="https://pumpportal.fun/api/trade-local", 
    data={
        "publicKey": wallet_address,
        "action": "buy",
        "mint": token_mint,
        "amount": tokens_to_buy,
        "denominatedInSol": "false",  # or "true"
        "slippage": 10,               # tried 10-25%
        "priorityFee": 0.005,         # tried 0.005-0.02
        "pool": "auto"                # tried "auto", "pump"
    }
)

# Sign returned transaction
keypair = Keypair.from_base58_string(private_key)  # with fallback
tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [keypair])

# Broadcast to Solana
send_response = requests.post(
    url="https://api.mainnet-beta.solana.com/",
    headers={"Content-Type": "application/json"},
    data=SendVersionedTransaction(tx, config).to_json()
)
```

## KEY QUESTIONS FOR ANALYSIS:

1. **Why does PumpPortal work for CLIPPY but fail for other tokens?**
   - Token age difference? (CLIPPY older, established)
   - Liquidity differences?
   - Different pool requirements?

2. **Are there alternative trading methods for pump.fun tokens?**
   - Direct DEX interaction (Raydium, Jupiter)
   - Different transaction construction approaches
   - Native Solana program calls

3. **Could wallet balance/rent issues be the root cause?**
   - Minimum SOL requirements for token accounts
   - Associated token account creation costs
   - Priority fee calculations

4. **Is PumpPortal fundamentally unreliable for systematic trading?**
   - Should we abandon this approach entirely?
   - Are there better APIs or methods?

5. **Jupiter DEX alternative approach:**
   - Can we trade pump.fun tokens through Jupiter?
   - Would this be more reliable for token delivery?
   - How to identify newly bonded tokens on Jupiter?

## TECHNICAL CONSTRAINTS:
- **Solana mainnet** deployment required
- **Real SOL and tokens** - no testnet
- **Private key management** - user controls wallet
- **Real-time execution** - automated trading within minutes of token launch
- **Token verification essential** - must confirm actual delivery

## WHAT WE NEED:
A reliable, consistent method to:
1. Identify newly launched pump.fun tokens
2. Execute trades that actually deliver tokens to wallet
3. Work across different tokens, not just specific ones
4. Handle wallet balance and fee requirements properly

## ALTERNATIVE APPROACHES TO CONSIDER:
1. **Jupiter DEX integration** for broader token support
2. **Direct Raydium pool interaction** for pump.fun tokens
3. **Native Solana program calls** bypassing third-party APIs
4. **Hybrid approach** - different methods for different token types

Please analyze this implementation challenge and suggest reliable solutions for consistent token acquisition on Solana/pump.fun.
"""


def save_analysis_request():
    """Save the ChatGPT analysis request to file"""
    with open("chatgpt_analysis.md", "w") as f:
        f.write(CHATGPT_ANALYSIS_REQUEST)

    print("📝 CHATGPT ANALYSIS REQUEST SAVED")
    print("=" * 60)
    print("File: chatgpt_analysis.md")
    print("Ready to paste into ChatGPT for consultation")
    print()
    print("The analysis covers:")
    print("✓ Complete problem description")
    print("✓ Current implementation details")
    print("✓ Specific failure patterns")
    print("✓ Test results with transaction hashes")
    print("✓ Technical constraints")
    print("✓ Alternative approaches to explore")


if __name__ == "__main__":
    save_analysis_request()
