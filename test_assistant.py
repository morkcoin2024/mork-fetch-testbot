"""
Test script for Assistant AI system
Tests both dry-run and live execution modes
"""

import os

from assistant_dev import apply_unified_diffs, assistant_codegen
from config import ASSISTANT_ADMIN_TELEGRAM_ID, ASSISTANT_WRITE_GUARD


def test_assistant_dry_run():
    """Test assistant in dry-run mode"""
    print("=== DRY-RUN TEST ===")
    print(f"ASSISTANT_WRITE_GUARD: {ASSISTANT_WRITE_GUARD}")

    # Mock request
    test_request = "add a DEBUG logger to token_fetcher.py that logs start/end of fetch_tokens()"
    test_user_id = ASSISTANT_ADMIN_TELEGRAM_ID or 123456789

    print(f"Request: {test_request}")
    print(f"User ID: {test_user_id}")

    # Generate response
    result = assistant_codegen(test_request, test_user_id)
    plan = result.get("plan", "(no plan)")
    diffs = result.get("diffs", [])
    commands = result.get("commands", [])
    restart = result.get("restart", "none")

    print(f"\n✅ Plan:\n{plan}")
    print(f"\n📝 Generated {len(diffs)} diffs")
    print(f"🔧 Commands: {len(commands)}")
    print(f"♻️ Restart: {restart}")

    if diffs:
        print("\n--- Diff Preview (first 500 chars) ---")
        print(diffs[0][:500] + "..." if len(diffs[0]) > 500 else diffs[0])

    # Apply diffs
    apply_res = apply_unified_diffs(diffs)
    print("\n🔄 Application Results:")
    print(f"  - Applied: {len(apply_res.applied_files)} files")
    print(f"  - Failed: {len(apply_res.failed_files)} files")
    print(f"  - Dry run: {apply_res.dry_run}")

    if apply_res.failed_files:
        print(f"  - Failed files: {apply_res.failed_files}")


def test_assistant_live():
    """Test assistant in live mode (if enabled)"""
    print("\n=== LIVE MODE TEST ===")

    # Check if live mode is enabled
    if ASSISTANT_WRITE_GUARD.upper() != "ON":
        print("Live mode not enabled (ASSISTANT_WRITE_GUARD != 'ON')")
        print("To test live mode, set environment variable ASSISTANT_WRITE_GUARD='ON'")
        return

    print("⚠️ LIVE MODE ENABLED - Files will be modified!")
    print("This would execute the same request but with actual file changes")

    # Same test as dry-run but would actually modify files
    test_request = "add a DEBUG logger to token_fetcher.py that logs start/end of fetch_tokens()"
    test_user_id = ASSISTANT_ADMIN_TELEGRAM_ID or 123456789

    result = assistant_codegen(test_request, test_user_id)
    apply_res = apply_unified_diffs(result.get("diffs", []))

    print(f"Applied {len(apply_res.applied_files)} files in LIVE mode")


def show_audit_log():
    """Show recent audit log entries"""
    print("\n=== AUDIT LOG ===")

    if os.path.exists("logs/assistant_audit.log"):
        with open("logs/assistant_audit.log") as f:
            lines = f.readlines()
            print("Recent entries:")
            for line in lines[-10:]:  # Show last 10 entries
                print(f"  {line.strip()}")
    else:
        print("No audit log found")


if __name__ == "__main__":
    print("🤖 Testing Assistant AI System")
    print(f"Admin ID configured: {ASSISTANT_ADMIN_TELEGRAM_ID}")
    print(f"Write Guard: {ASSISTANT_WRITE_GUARD}")

    # Run tests
    test_assistant_dry_run()
    test_assistant_live()
    show_audit_log()
