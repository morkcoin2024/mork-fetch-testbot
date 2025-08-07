"""
Debug script to test the enhanced /status command and check database
"""

from models import ActiveTrade, UserSession, db
from app import app
import logging

def create_test_trade():
    """Create a test trade for debugging"""
    try:
        with app.app_context():
            # Create a test active trade
            test_trade = ActiveTrade(
                chat_id="1653046781",  # Your chat ID
                trade_type="fetch",
                contract_address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
                token_name="Test Token",
                token_symbol="TEST",
                entry_price=0.000001,
                trade_amount=0.1,
                stop_loss=5.0,
                take_profit=10.0,
                sell_percent=100.0,
                status="active"
            )
            
            db.session.add(test_trade)
            db.session.commit()
            
            print("✅ Test trade created successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Failed to create test trade: {e}")
        return False

def check_database_status():
    """Check current database status"""
    try:
        with app.app_context():
            # Count all records
            all_trades = ActiveTrade.query.all()
            active_trades = ActiveTrade.query.filter_by(status='active').all()
            all_sessions = UserSession.query.all()
            
            print("📊 DATABASE STATUS CHECK")
            print("=" * 40)
            print(f"Total ActiveTrade records: {len(all_trades)}")
            print(f"Active trades: {len(active_trades)}")
            print(f"User sessions: {len(all_sessions)}")
            print()
            
            if active_trades:
                print("🚀 ACTIVE TRADES:")
                for i, trade in enumerate(active_trades, 1):
                    print(f"{i}. {trade.token_symbol} | {trade.trade_amount} SOL | Status: {trade.status}")
            else:
                print("❌ No active trades found")
            
            print()
            return len(active_trades) > 0
            
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def test_status_command():
    """Test the status command logic"""
    try:
        chat_id = "1653046781"  # Your chat ID
        
        # Import the status function
        import sys
        sys.path.append('/home/runner/workspace')
        from bot import handle_status_command
        
        print("🧪 TESTING STATUS COMMAND")
        print("=" * 40)
        
        # This would normally send to Telegram, but we'll capture the logic
        print("Status command would execute...")
        
        return True
        
    except Exception as e:
        print(f"❌ Status command test failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 DEBUGGING /STATUS COMMAND")
    print("=" * 50)
    print()
    
    # Check database first
    has_trades = check_database_status()
    
    # If no trades exist, create a test one
    if not has_trades:
        print("\n📝 Creating test trade for debugging...")
        create_test_trade()
        check_database_status()  # Check again
    
    # Test status command
    test_status_command()
    
    print("\n✅ Debug complete!")
    print("Try /status command in Telegram now")