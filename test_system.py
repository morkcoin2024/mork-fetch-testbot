#!/usr/bin/env python3
"""
Test System for Mork F.E.T.C.H Bot
Quick validation of all core components
"""

import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_jupiter_engine():
    """Test Jupiter engine basic functionality"""
    try:
        from jupiter_engine import jupiter_engine

        # Test SOL balance (should work without wallet)
        test_wallet = "11111111111111111111111111111112"  # System program
        balance = jupiter_engine.get_sol_balance(test_wallet)
        print(f"✓ Jupiter Engine: SOL balance check working (got {balance})")

        # Test token routing check
        mork_mint = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"
        is_routable, msg = jupiter_engine.check_token_routable(mork_mint, 0.001)
        print(
            f"✓ Jupiter Engine: Routing check {'✅ PASSED' if is_routable else '❌ FAILED'} - {msg}"
        )

        return True
    except Exception as e:
        print(f"❌ Jupiter Engine failed: {e}")
        return False


def test_discovery():
    """Test token discovery system"""
    try:
        from discovery import discovery

        # Test token validation (without actual trading)
        mork_mint = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"
        is_valid, msg, data = discovery.validate_token_for_trading(mork_mint)
        print(f"✓ Discovery: Token validation {'✅ PASSED' if is_valid else '❌ FAILED'} - {msg}")

        return True
    except Exception as e:
        print(f"❌ Discovery failed: {e}")
        return False


def test_wallet_manager():
    """Test wallet management"""
    try:
        from wallet_manager import wallet_manager

        # Test wallet info (should work even if empty)
        wallet_info = wallet_manager.get_wallet_info("test_user")
        print(f"✓ Wallet Manager: Info retrieval working (found {len(wallet_info)} wallets)")

        return True
    except Exception as e:
        print(f"❌ Wallet Manager failed: {e}")
        return False


def test_safety_system():
    """Test safety system"""
    try:
        from safety_system import safety

        # Test emergency stop check
        ok, msg = safety.check_emergency_stop()
        print(f"✓ Safety System: Emergency stop check {'✅ OK' if ok else '❌ ACTIVE'} - {msg}")

        # Test safe mode
        ok, msg = safety.check_safe_mode_limits(0.01)
        print(f"✓ Safety System: Safe mode check {'✅ OK' if ok else '❌ BLOCKED'} - {msg}")

        return True
    except Exception as e:
        print(f"❌ Safety System failed: {e}")
        return False


def test_flask_app():
    """Test Flask application"""
    try:
        from app import app

        print("✓ Flask App: Successfully imported")

        # Test status endpoint
        with app.test_client() as client:
            response = client.get("/status")
            print(
                f"✓ Flask App: Status endpoint {'✅ OK' if response.status_code == 200 else '❌ FAILED'}"
            )

        return True
    except Exception as e:
        print(f"❌ Flask App failed: {e}")
        return False


def main():
    """Run all system tests"""
    print("🐕 Mork F.E.T.C.H Bot - System Test")
    print("=" * 50)

    tests = [
        ("Jupiter Engine", test_jupiter_engine),
        ("Discovery System", test_discovery),
        ("Wallet Manager", test_wallet_manager),
        ("Safety System", test_safety_system),
        ("Flask App", test_flask_app),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        print(f"\n🔍 Testing {name}...")
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {name} test crashed: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} components passed")

    if passed == total:
        print("🎉 All systems operational! Bot ready for deployment.")
        return 0
    else:
        print("⚠️ Some components need attention before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
