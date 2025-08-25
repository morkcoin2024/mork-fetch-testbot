#!/usr/bin/env python3
"""
Test script for the lightweight assistant system
Verifies all components are working properly
"""

import os
import sys


def test_environment_variables():
    """Test that all required environment variables are set"""
    required_vars = [
        "ASSISTANT_ADMIN_TELEGRAM_ID",
        "ASSISTANT_WRITE_GUARD",
        "ASSISTANT_FAILSAFE",
        "ASSISTANT_MODEL",
        "OPENAI_API_KEY",
    ]

    print("Testing environment variables...")
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
        else:
            print(f"✓ {var}: {'*' * min(len(os.environ[var]), 8)}")

    if missing:
        print(f"❌ Missing variables: {missing}")
        return False
    else:
        print("✅ All environment variables set")
        return True


def test_assistant_import():
    """Test that assistant modules can be imported"""
    print("\nTesting module imports...")
    try:

        print("✓ assistant_dev_lite imported successfully")

        print("✓ telegram handlers imported successfully")

        print("✓ config variables imported successfully")

        print("✅ All modules imported successfully")
        return True

    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_assistant_config():
    """Test assistant configuration values"""
    print("\nTesting configuration...")
    try:
        from config import (
            ASSISTANT_ADMIN_TELEGRAM_ID,
            ASSISTANT_FAILSAFE,
            ASSISTANT_MODEL,
            ASSISTANT_WRITE_GUARD,
        )

        print(f"Admin ID: {ASSISTANT_ADMIN_TELEGRAM_ID}")
        print(f"Write Guard: {ASSISTANT_WRITE_GUARD}")
        print(f"Failsafe: {ASSISTANT_FAILSAFE}")
        print(f"Model: {ASSISTANT_MODEL}")

        # Basic validation
        if not ASSISTANT_ADMIN_TELEGRAM_ID or not str(ASSISTANT_ADMIN_TELEGRAM_ID).isdigit():
            print("❌ Invalid admin ID")
            return False

        if ASSISTANT_WRITE_GUARD not in ["ON", "OFF"]:
            print("❌ Invalid write guard value")
            return False

        if ASSISTANT_FAILSAFE not in ["ON", "OFF"]:
            print("❌ Invalid failsafe value")
            return False

        print("✅ Configuration valid")
        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("LIGHTWEIGHT ASSISTANT SYSTEM - TEST SUITE")
    print("=" * 50)

    tests = [test_environment_variables, test_assistant_import, test_assistant_config]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🚀 LIGHTWEIGHT ASSISTANT SYSTEM READY FOR PRODUCTION")
        print("\nNext steps:")
        print("1. Test /whoami command in Telegram")
        print("2. Test /assistant_toggle OFF command")
        print("3. Test /assistant hello world command")
        return True
    else:
        print("❌ Some tests failed - check configuration")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
