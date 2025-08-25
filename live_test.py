#!/usr/bin/env python3
"""
Live Test Script for Mork F.E.T.C.H Bot
Test actual wallet functionality with your existing wallet
"""

import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_with_real_wallet():
    """Test bot with actual wallet if available"""

    print("🔍 Checking for existing wallet...")

    try:
        from wallet_manager import wallet_manager

        # Check if we have the existing wallet
        existing_wallets = wallet_manager._load_wallets()

        if existing_wallets:
            print(f"✅ Found {len(existing_wallets)} user(s) with wallets")

            # Test with first user
            for user_id, user_wallets in existing_wallets.items():
                print(f"\n👤 Testing user: {user_id}")

                for wallet_name, wallet_data in user_wallets.items():
                    pubkey = wallet_data["pubkey"]
                    print(f"   💼 Wallet '{wallet_name}': {pubkey}")

                    # Test Jupiter balance check
                    from jupiter_engine import jupiter_engine

                    sol_balance = jupiter_engine.get_sol_balance(pubkey)
                    print(f"   💰 SOL Balance: {sol_balance:.6f}")

                    # Test MORK holdings
                    from safety_system import safety

                    mork_ok, mork_msg = safety.check_mork_holdings(pubkey, 1.0)
                    print(f"   🪙 MORK Check: {mork_msg}")

                    # Test comprehensive safety check
                    test_mint = "7eMJmn1b8tJnmhK4qZsZfMPUWuBhzQ5VXx1B1Cj6v1"  # Example token
                    safety_ok, safety_msg = safety.comprehensive_safety_check(
                        user_id, pubkey, test_mint, 0.01, "snipe"
                    )
                    print(f"   🛡️ Safety Check: {'✅ PASSED' if safety_ok else '❌ FAILED'}")
                    print(f"       {safety_msg}")

                    break  # Test only first wallet
                break  # Test only first user

        else:
            print("❌ No existing wallets found")
            print("💡 To test with your wallet, first import it using:")
            print("   /wallet import <your_private_key>")

    except Exception as e:
        print(f"❌ Wallet test failed: {e}")
        return False

    return True


def test_token_discovery():
    """Test live token discovery"""

    print("\n🤖 Testing Token Discovery...")

    try:
        from discovery import discovery

        print("🔍 Scanning for tradeable tokens (this may take a moment)...")

        # Try to find one tradeable token
        token = discovery.find_tradeable_token()

        if token:
            print("✅ Found tradeable token:")
            print(f"   Symbol: {token['symbol']}")
            print(f"   Mint: {token['mint']}")
            print(f"   Market Cap: ${token['market_cap']:,.0f}")
            print(f"   Age: {token.get('age_hours', 0):.1f} hours")
            print(f"   Expected tokens per SOL: ~{token.get('expected_tokens_per_sol', 0):,.0f}")
        else:
            print("⚠️ No suitable tokens found in current scan")
            print("   This is normal - suitable tokens depend on market conditions")

    except Exception as e:
        print(f"❌ Token discovery failed: {e}")
        return False

    return True


def main():
    """Run live tests with real data"""

    print("🐕 Mork F.E.T.C.H Bot - Live System Test")
    print("Testing with real wallet data and live APIs")
    print("=" * 60)

    tests = [
        ("Real Wallet Test", test_with_real_wallet),
        ("Live Token Discovery", test_token_discovery),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        print(f"\n{'=' * 20} {name} {'=' * 20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {name}: PASSED")
            else:
                print(f"❌ {name}: FAILED")
        except Exception as e:
            print(f"💥 {name}: CRASHED - {e}")

    print("\n" + "=" * 60)
    print(f"📊 Live Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 System ready for live trading!")
        print("\n💡 Next steps:")
        print("   1. Start the bot with your Telegram token")
        print("   2. Use /balance to verify your wallet")
        print("   3. Try /fetch to discover new tokens")
        print("   4. Use /snipe <mint> <amount> for manual trades")
    else:
        print("⚠️ Some issues detected - address before live trading")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
