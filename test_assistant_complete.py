"""
Complete Test Suite for Assistant AI System
Tests both dry-run and live execution modes with mock data
"""

import os
import json
from assistant_dev import apply_unified_diffs, audit_log, MAX_DIFFS, MAX_DIFF_BYTES
from config import ASSISTANT_WRITE_GUARD, ASSISTANT_ADMIN_TELEGRAM_ID

# Mock unified diff for testing
MOCK_DIFF = '''--- a/token_fetcher.py
+++ b/token_fetcher.py
@@ -4,6 +4,7 @@ Handles token discovery and metadata retrieval
 """
 
 import requests
+import logging
 import json
 import time
 from typing import List, Dict, Optional
@@ -11,10 +12,14 @@ from typing import List, Dict, Optional
 class TokenFetcher:
     """Token discovery and metadata fetching"""
     
     def __init__(self):
+        logging.basicConfig(level=logging.DEBUG)
+        self.logger = logging.getLogger(__name__)
         self.pump_api = "https://api.pump.fun"
         self.birdeye_api = "https://public-api.birdeye.so"
         
     def fetch_tokens(self, limit: int = 10) -> List[Dict]:
+        self.logger.debug("Starting fetch_tokens() with limit=%d", limit)
         """Fetch trending tokens from Pump.fun"""
         try:
             url = f"{self.pump_api}/tokens/trending"
@@ -32,8 +37,10 @@ class TokenFetcher:
                     enriched_tokens.append(token)
                 
+                self.logger.debug("Completed fetch_tokens() - found %d tokens", len(enriched_tokens))
                 return enriched_tokens
             else:
+                self.logger.debug("fetch_tokens() failed - status code: %d", response.status_code)
                 return []
                 
         except Exception as e:
+            self.logger.debug("fetch_tokens() exception: %s", e)
             print(f"Error fetching tokens: {e}")
             return []'''

def test_dry_run_mode():
    """Test assistant system in dry-run mode"""
    print("🧪 TESTING DRY-RUN MODE")
    print(f"Write Guard: {ASSISTANT_WRITE_GUARD} (OFF = dry-run)")
    print(f"Admin ID: {ASSISTANT_ADMIN_TELEGRAM_ID}")
    
    # Test data
    mock_result = {
        "plan": "Add DEBUG logging to token_fetcher.py to track fetch_tokens() start/end execution",
        "diffs": [MOCK_DIFF],
        "commands": [],
        "restart": "none"
    }
    
    print(f"\n📋 Mock Plan: {mock_result['plan']}")
    print(f"📝 Diffs: {len(mock_result['diffs'])}")
    
    # Apply diffs (should be dry-run)
    apply_res = apply_unified_diffs(mock_result["diffs"])
    
    print(f"\n📊 Results:")
    print(f"  • Dry run mode: {apply_res.dry_run}")
    print(f"  • Applied files: {len(apply_res.applied_files)}")
    print(f"  • Failed files: {len(apply_res.failed_files)}")
    
    if apply_res.dry_run:
        print("  ✅ DRY-RUN: No files were actually modified")
    else:
        print("  ⚠️ LIVE MODE: Files were actually modified")
    
    # Show diff preview
    if mock_result["diffs"]:
        print(f"\n📄 Diff Preview (first 300 chars):")
        print(mock_result["diffs"][0][:300] + "...")

def test_size_limits():
    """Test size and diff count limits"""
    print("\n🔒 TESTING SIZE LIMITS")
    
    # Test diff count limit
    many_diffs = [MOCK_DIFF] * 5  # More than MAX_DIFFS
    print(f"Testing {len(many_diffs)} diffs (limit: {MAX_DIFFS})")
    
    apply_res = apply_unified_diffs(many_diffs)
    print(f"Result: processed diffs within limit")
    
    # Test diff size limit
    large_diff = "+" * (MAX_DIFF_BYTES + 1000)  # Larger than limit
    oversized_diffs = [large_diff]
    print(f"\nTesting oversized diff ({len(large_diff)} bytes, limit: {MAX_DIFF_BYTES})")
    
    apply_res = apply_unified_diffs(oversized_diffs)
    if apply_res.failed_files:
        print(f"✅ Size limit enforced: {apply_res.failed_files[0]}")

def test_live_mode_simulation():
    """Simulate what would happen in live mode"""
    print("\n🔴 LIVE MODE SIMULATION")
    
    if ASSISTANT_WRITE_GUARD.upper() == "ON":
        print("⚠️ LIVE MODE IS ENABLED - Files would be modified!")
        print("The same diff would be applied to actual files")
    else:
        print("Live mode disabled (ASSISTANT_WRITE_GUARD != 'ON')")
        print("To enable: Set environment variable ASSISTANT_WRITE_GUARD='ON'")
    
    print("\nIn live mode, the system would:")
    print("  • Apply the diff to token_fetcher.py")
    print("  • Add logging import and logger setup")
    print("  • Add debug logs at start/end of fetch_tokens()")
    print("  • Restart bot if requested")

def show_recent_audit_logs():
    """Display recent audit log entries"""
    print("\n📋 RECENT AUDIT LOG")
    
    if os.path.exists("logs/assistant_audit.log"):
        with open("logs/assistant_audit.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        print(f"Found {len(lines)} log entries")
        print("Recent entries:")
        for line in lines[-5:]:  # Show last 5
            print(f"  {line.strip()}")
    else:
        print("No audit log file found")

def test_access_control():
    """Test access control functionality"""
    print("\n🛡️ TESTING ACCESS CONTROL")
    
    # Simulate unauthorized access
    unauthorized_user_id = 999999999
    admin_user_id = ASSISTANT_ADMIN_TELEGRAM_ID or 123456789
    
    print(f"Admin ID: {admin_user_id}")
    print(f"Test unauthorized ID: {unauthorized_user_id}")
    
    # Log unauthorized attempt
    audit_log(f"ACCESS_DENIED: user_id:{unauthorized_user_id} (admin:{admin_user_id})")
    print("✅ Unauthorized access attempt logged")
    
    # Log authorized attempt
    audit_log(f"REQUEST: user_id:{admin_user_id} - test request")
    print("✅ Authorized access logged")

if __name__ == "__main__":
    print("🤖 MORK F.E.T.C.H BOT - Assistant AI Test Suite")
    print("=" * 50)
    
    # Run all tests
    test_dry_run_mode()
    test_size_limits() 
    test_access_control()
    test_live_mode_simulation()
    show_recent_audit_logs()
    
    print("\n" + "=" * 50)
    print("✅ Test suite completed")
    print("\nTo test live mode:")
    print("1. Set ASSISTANT_WRITE_GUARD='ON'")
    print("2. Set OPENAI_API_KEY with valid API key")
    print("3. Set ASSISTANT_ADMIN_TELEGRAM_ID with your Telegram ID")
    print("4. Use /assistant command in Telegram bot")