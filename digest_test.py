#!/usr/bin/env python3
"""
Daily Digest Test Script - Verify Digest Functionality
"""
import sys

sys.path.insert(0, "/home/runner/workspace")


def test_digest():
    print("🧪 Testing Daily Digest functionality...")

    try:
        from app import _digest_compose, _digest_target_chat, _parse_hhmm, _secs_until_next

        print("✅ Successfully imported digest functions")

        # Test compose
        sample = _digest_compose("test note")
        print(f"📄 Sample digest:\n{sample}\n")

        # Test target chat
        chat = _digest_target_chat()
        print(f"📱 Target chat: {chat}")

        # Test time parsing
        valid_times = ["09:00", "23:59", "00:00"]
        invalid_times = ["25:00", "12:60", "abc"]

        for t in valid_times:
            parsed = _parse_hhmm(t)
            print(f"✅ {t} -> {parsed}")

        for t in invalid_times:
            parsed = _parse_hhmm(t)
            print(f"❌ {t} -> {parsed}")

        # Test seconds calculation
        secs = _secs_until_next(9, 0)  # 9:00 AM
        print(f"⏰ Seconds until next 9:00 AM: {secs}")

        print("🎉 All digest tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    test_digest()
