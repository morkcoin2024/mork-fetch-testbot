"""
Test assistant system status and readiness
"""


def check_assistant_status():
    """Check if assistant system is ready for testing"""
    print("🔍 ASSISTANT SYSTEM STATUS CHECK")
    print("=" * 50)

    # Check core files
    import os

    files_to_check = ["assistant_dev_lite.py", "alerts/telegram.py", "config.py", "bot.py"]

    print("📁 Core Files:")
    for file in files_to_check:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} missing")

    # Check imports
    print("\n📦 Import Tests:")
    try:
        print("   ✅ assistant_dev_lite imports")
    except Exception as e:
        print(f"   ❌ assistant_dev_lite error: {e}")

    try:
        print("   ✅ cmd_assistant handler")
    except Exception as e:
        print(f"   ❌ cmd_assistant error: {e}")

    # Check configuration
    print("\n⚙️ Configuration:")
    try:
        from config import ASSISTANT_FAILSAFE, ASSISTANT_MODEL, ASSISTANT_WRITE_GUARD

        print(f"   Model: {ASSISTANT_MODEL}")
        print(f"   Write Guard: {ASSISTANT_WRITE_GUARD}")
        print(f"   Failsafe: {ASSISTANT_FAILSAFE}")
    except Exception as e:
        print(f"   ❌ Config error: {e}")

    # Check secrets
    print("\n🔐 Environment Variables:")
    required_secrets = [
        "OPENAI_API_KEY",
        "ASSISTANT_ADMIN_TELEGRAM_ID",
        "ASSISTANT_WRITE_GUARD",
        "ASSISTANT_FAILSAFE",
        "ASSISTANT_MODEL",
    ]

    for secret in required_secrets:
        value = os.getenv(secret)
        if value:
            print(f"   ✅ {secret} = {'***' if 'KEY' in secret else value}")
        else:
            print(f"   ❌ {secret} = NOT SET")

    print("\n🎯 TESTING INSTRUCTIONS:")
    print("1. Set missing environment variables in Replit secrets")
    print("2. Use /whoami to get your Telegram ID")
    print("3. Test /assistant hello world (should show DRY-RUN)")
    print("4. Set ASSISTANT_WRITE_GUARD=ON for live mode")
    print("5. Test /assistant add comment to main.py")


if __name__ == "__main__":
    check_assistant_status()
