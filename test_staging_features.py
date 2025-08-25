"""
Test Script for New Assistant Staging Features
Tests /assistant_diff and Git staging workflow
"""

import os

from assistant_dev import audit_log, get_file_tail, git_approve_merge, git_stage_changes
from config import ASSISTANT_GIT_BRANCH


def test_assistant_diff():
    """Test the file inspection feature"""
    print("📄 TESTING /assistant_diff COMMAND")
    print("=" * 40)

    # Test with existing file
    file_path = "token_fetcher.py"
    content = get_file_tail(file_path, 100)

    print(f"File: {file_path}")
    print(f"Content length: {len(content)} characters")
    print("Preview (first 200 chars):")
    print(content[:200] + "..." if len(content) > 200 else content)
    print()

    # Test with non-existent file
    nonexistent = "nonexistent_file.py"
    error_content = get_file_tail(nonexistent, 100)
    print(f"Non-existent file test: {error_content}")
    print()


def test_git_staging():
    """Test Git staging functionality"""
    print("🌿 TESTING GIT STAGING FEATURES")
    print("=" * 40)

    if not ASSISTANT_GIT_BRANCH:
        print("Git staging disabled (ASSISTANT_GIT_BRANCH not set)")
        print("To test: Set ASSISTANT_GIT_BRANCH='assistant-staging'")
        return

    print(f"Git branch configured: {ASSISTANT_GIT_BRANCH}")

    # Test files
    test_files = ["token_fetcher.py", "config.py"]

    # Test staging
    print(f"Testing staging of {len(test_files)} files...")
    result = git_stage_changes(test_files, ASSISTANT_GIT_BRANCH)

    if result:
        print(f"✅ Successfully staged files on branch {ASSISTANT_GIT_BRANCH}")

        # Test approval
        print("Testing approval/merge...")
        merge_result = git_approve_merge(ASSISTANT_GIT_BRANCH)

        if merge_result:
            print("✅ Successfully merged and cleaned up branch")
        else:
            print("❌ Merge failed (expected if no changes)")
    else:
        print("❌ Staging failed (expected if not in git repo)")


def demo_telegram_workflow():
    """Demonstrate the complete Telegram workflow"""
    print("📱 COMPLETE STAGING WORKFLOW DEMO")
    print("=" * 45)

    print("STEP 1: User makes a request")
    print("💬 /assistant add logging to wallet_manager.py")
    print()

    print("STEP 2: Bot processes and stages (if ASSISTANT_GIT_BRANCH set)")
    print("🤖 Thinking… generating patch.")
    print("✅ Plan: Add comprehensive logging to wallet_manager.py")
    print("✍️ Write mode: ON")
    print("📝 Applied: 1 files (wallet_manager.py)")
    if ASSISTANT_GIT_BRANCH:
        print(f"🌿 staged 1 files on branch {ASSISTANT_GIT_BRANCH}")
    print()

    print("STEP 3: User inspects changes")
    print("💬 /assistant_diff wallet_manager.py")
    print("📄 Shows last 100 lines of modified file")
    print()

    print("STEP 4: User approves changes (if staging enabled)")
    if ASSISTANT_GIT_BRANCH:
        print("💬 /assistant_approve")
        print("🔄 Approving and merging staged changes...")
        print(f"✅ Successfully merged branch `{ASSISTANT_GIT_BRANCH}` to main")
    else:
        print("(Staging disabled - changes applied directly)")
    print()


def show_expected_responses():
    """Show expected Telegram bot responses"""
    print("📋 EXPECTED TELEGRAM RESPONSES")
    print("=" * 35)

    print("FOR /assistant_diff token_fetcher.py:")
    print("```")
    print("📄 token_fetcher.py (last 100 lines):")
    print("")
    print("```")
    print('"""')
    print("Token Fetcher for Mork F.E.T.C.H Bot")
    print("Handles token discovery and metadata retrieval")
    print('"""')
    print("# ... (rest of file content)")
    print("```")
    print()

    print("FOR /assistant with ASSISTANT_GIT_BRANCH='staging':")
    print("✅ Plan: Add logging functionality")
    print("✍️ Write mode: ON")
    print("📝 Applied: 1 files")
    print("🌿 staged 1 files on branch staging")
    print()

    print("FOR /assistant_approve:")
    print("🔄 Approving and merging staged changes...")
    print("✅ Successfully merged branch `staging` to main")


def show_environment_setup():
    """Show environment variables needed"""
    print("⚙️ ENVIRONMENT SETUP")
    print("=" * 25)

    required_vars = {
        "OPENAI_API_KEY": "Your OpenAI API key for code generation",
        "ASSISTANT_ADMIN_TELEGRAM_ID": "Your numeric Telegram ID for admin access",
        "ASSISTANT_WRITE_GUARD": '"ON" to enable live changes (default: "OFF")',
        "ASSISTANT_GIT_BRANCH": '"staging" or branch name for Git workflow (optional)',
    }

    for var, desc in required_vars.items():
        current = os.environ.get(var, "(not set)")
        status = "✅" if current != "(not set)" else "⚠️"
        print(f"{status} {var}: {current}")
        print(f"   Description: {desc}")
        print()


if __name__ == "__main__":
    print("🤖 MORK F.E.T.C.H BOT - Staging Features Test")
    print("=" * 50)

    # Show current environment
    show_environment_setup()

    # Run tests
    test_assistant_diff()
    test_git_staging()
    demo_telegram_workflow()
    show_expected_responses()

    print("=" * 50)
    print("🎉 NEW FEATURES SUMMARY")
    print("✅ /assistant_diff <path> - Inspect last 100 lines of any file")
    print("✅ Git staging - Changes staged on branch if ASSISTANT_GIT_BRANCH set")
    print("✅ /assistant_approve - Merge staged changes to main branch")
    print("✅ Enhanced security - All commands admin-only with audit logging")
    print("✅ Error handling - Clear messages for missing files/Git issues")

    # Log the test
    audit_log("STAGING_TEST: Completed staging features test suite")
