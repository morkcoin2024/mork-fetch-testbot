#!/usr/bin/env python3
"""
Test /fetch command end-to-end to verify real trading functionality
"""

import asyncio
import json
import sys
import os
sys.path.append('.')

def test_fetch_command():
    """Test the complete /fetch command flow"""
    print("🧪 TESTING /fetch COMMAND END-TO-END")
    print("=" * 50)
    
    # Import bot functions
    from bot import handle_fetch_command, get_or_create_session, update_session
    from models import UserSession, db
    from app import app
    
    # Create test user session
    test_chat_id = "test_fetch_user_123"
    
    with app.app_context():
        # Clean up any existing session
        existing_session = UserSession.query.filter_by(chat_id=test_chat_id).first()
        if existing_session:
            db.session.delete(existing_session)
            db.session.commit()
        
        # Create fresh session
        session = get_or_create_session(test_chat_id)
        
        print(f"✅ Created test session for user: {test_chat_id}")
        print(f"Initial state: {session.state}")
        
        # Test /fetch command
        print("\n🚀 EXECUTING /fetch COMMAND...")
        try:
            handle_fetch_command(test_chat_id)
            print("✅ /fetch command executed without crashes")
            
            # Check session state after command
            updated_session = get_or_create_session(test_chat_id)
            print(f"Final state: {updated_session.state}")
            
            return True
            
        except Exception as e:
            print(f"❌ /fetch command failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = test_fetch_command()
    print(f"\n🎯 TEST RESULT: {'PASS' if success else 'FAIL'}")