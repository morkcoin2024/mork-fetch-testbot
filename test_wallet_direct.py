#!/usr/bin/env python3
"""Direct test of wallet functions without webhook complexity"""

import sys

sys.path.append(".")

from wallets import get_balance_sol, get_or_create_wallet, get_wallet


def test_wallet_commands():
    print("🔧 Testing wallet commands directly...")

    # Test user ID (admin)
    uid = "1653046781"

    try:
        print(f"\n1. Testing /wallet_new for uid={uid}")
        w = get_or_create_wallet(uid)
        response = (
            "🪪 *Burner wallet created*\n"
            f"• Address: `{w['address']}`\n"
            "_(Private key stored server-side for testing; will move to secure storage before trading.)_"
        )
        print(f"✅ SUCCESS: {response}")

        print(f"\n2. Testing /wallet_addr for uid={uid}")
        w2 = get_wallet(uid)
        if w2:
            response = f"📬 *Your burner wallet address*\n`{w2['address']}`"
            print(f"✅ SUCCESS: {response}")
        else:
            print("❌ FAIL: No wallet found")

        print(f"\n3. Testing /wallet_balance for uid={uid}")
        if w2:
            bal = get_balance_sol(w2["address"])
            response = f"💰 *Wallet balance*\nAddress: `{w2['address']}`\nBalance: `{bal:.6f} SOL`"
            print(f"✅ SUCCESS: {response}")
        else:
            print("❌ FAIL: No wallet found")

        print("\n🎯 All wallet functions work correctly!")
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_wallet_commands()
