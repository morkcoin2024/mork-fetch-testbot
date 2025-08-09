#!/usr/bin/env python3
"""
Simple Mork F.E.T.C.H Bot Interface
Command-line interface for testing core functionality
"""

import sys
import logging
from jupiter_engine import jupiter_engine
from discovery import discovery
from wallet_manager import wallet_manager
from safety_system import safety

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleMorkBot:
    """Command-line interface for Mork F.E.T.C.H Bot"""
    
    def __init__(self):
        self.current_user = "cli_user"
        print("🐕 Mork F.E.T.C.H Bot - Command Line Interface")
        print("=" * 50)
    
    def show_help(self):
        """Display available commands"""
        help_text = """
📖 Available Commands:

💼 Wallet Management:
  wallet create          - Create new wallet
  wallet import <key>    - Import existing wallet  
  wallet info           - Show wallet information
  balance               - Check SOL and MORK balances

🎯 Trading:
  snipe <mint> <amount>  - Manual token sniping
  fetch                 - Auto-discover and trade
  validate <mint>       - Check if token is tradeable

🛡️ System:
  status                - System status and safety info
  emergency stop        - Activate emergency stop
  emergency start       - Deactivate emergency stop
  safe on/off          - Toggle safe mode

📚 Help:
  help                  - Show this help
  exit/quit            - Exit bot
"""
        print(help_text)
    
    def handle_wallet_command(self, args):
        """Handle wallet management commands"""
        if len(args) < 1:
            print("❌ Usage: wallet <create|import|info>")
            return
        
        action = args[0].lower()
        
        if action == "create":
            result = wallet_manager.create_wallet(self.current_user, "default")
            if result["success"]:
                print(f"✅ Wallet Created: {result['pubkey']}")
            else:
                print(f"❌ Failed: {result['error']}")
                
        elif action == "import":
            if len(args) < 2:
                print("❌ Usage: wallet import <private_key>")
                return
            
            private_key = args[1]
            result = wallet_manager.import_wallet(self.current_user, private_key, "default")
            if result["success"]:
                print(f"✅ Wallet Imported: {result['pubkey']}")
            else:
                print(f"❌ Failed: {result['error']}")
                
        elif action == "info":
            wallet_info = wallet_manager.get_wallet_info(self.current_user)
            if wallet_info:
                print("💼 Your Wallets:")
                for name, data in wallet_info.items():
                    status = "🔗 Imported" if data.get("imported") else "🆕 Generated"
                    print(f"  • {name}: {data['pubkey']} {status}")
            else:
                print("❌ No wallets found")
        else:
            print("❌ Unknown wallet command")
    
    def handle_balance_command(self):
        """Check wallet balances"""
        if not wallet_manager.has_wallet(self.current_user):
            print("❌ No wallet found. Use 'wallet create' first.")
            return
        
        wallet_info = wallet_manager.get_wallet_info(self.current_user)
        wallet_address = wallet_info["default"]["pubkey"]
        
        print(f"💰 Checking balance for: {wallet_address}")
        
        # Get SOL balance
        sol_balance = jupiter_engine.get_sol_balance(wallet_address)
        print(f"SOL Balance: {sol_balance:.6f} SOL")
        
        # Check MORK holdings
        mork_ok, mork_msg = safety.check_mork_holdings(wallet_address, 1.0)
        print(f"MORK Holdings: {mork_msg}")
        
        trading_status = "✅ Eligible for trading" if mork_ok else "❌ Need more MORK"
        print(f"Trading Status: {trading_status}")
    
    def handle_snipe_command(self, args):
        """Handle manual sniping"""
        if len(args) < 2:
            print("❌ Usage: snipe <token_mint> <sol_amount>")
            return
        
        if not wallet_manager.has_wallet(self.current_user):
            print("❌ No wallet found. Use 'wallet create' first.")
            return
        
        token_mint = args[0]
        try:
            amount_sol = float(args[1])
        except ValueError:
            print("❌ Invalid SOL amount")
            return
        
        wallet_info = wallet_manager.get_wallet_info(self.current_user)
        wallet_address = wallet_info["default"]["pubkey"]
        
        print(f"🎯 Preparing snipe: {amount_sol} SOL → {token_mint[:8]}...")
        
        # Safety checks
        safe_ok, safe_msg = safety.comprehensive_safety_check(
            self.current_user, wallet_address, token_mint, amount_sol, "snipe"
        )
        
        if not safe_ok:
            print(f"❌ Safety check failed: {safe_msg}")
            return
        
        print("✅ Safety checks passed")
        
        # Get confirmation
        confirm = input("Execute trade? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Trade cancelled")
            return
        
        # Execute trade
        private_key = wallet_manager.get_private_key(self.current_user, "default")
        if not private_key:
            print("❌ Could not access wallet private key")
            return
        
        print("🔥 Executing trade...")
        result = jupiter_engine.safe_swap(private_key, token_mint, amount_sol)
        
        if result["success"]:
            safety.record_trade(self.current_user, amount_sol)
            print(f"🎉 Trade successful!")
            print(f"Transaction: {result['signature']}")
            print(f"Tokens received: {result['delta_raw']:,}")
        else:
            print(f"❌ Trade failed: {result['error']}")
    
    def handle_fetch_command(self):
        """Handle automated token discovery"""
        if not wallet_manager.has_wallet(self.current_user):
            print("❌ No wallet found. Use 'wallet create' first.")
            return
        
        wallet_info = wallet_manager.get_wallet_info(self.current_user)
        wallet_address = wallet_info["default"]["pubkey"]
        
        # Check MORK holdings
        mork_ok, mork_msg = safety.check_mork_holdings(wallet_address, 1.0)
        if not mork_ok:
            print(f"❌ Fetch feature locked: {mork_msg}")
            return
        
        print("🤖 F.E.T.C.H mode activated - scanning for tokens...")
        
        # Find tradeable token
        token = discovery.find_tradeable_token()
        
        if not token:
            print("❌ No suitable tokens found")
            return
        
        print(f"🎯 Found: {token['symbol']} (${token['market_cap']:,.0f} market cap)")
        
        amount_sol = 0.02  # Default fetch amount
        
        # Get confirmation
        confirm = input(f"Trade {amount_sol} SOL for {token['symbol']}? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Trade cancelled")
            return
        
        # Execute trade
        private_key = wallet_manager.get_private_key(self.current_user, "default")
        result = jupiter_engine.safe_swap(private_key, token["mint"], amount_sol)
        
        if result["success"]:
            safety.record_trade(self.current_user, amount_sol)
            print(f"🎉 F.E.T.C.H trade successful!")
            print(f"Token: {token['symbol']}")
            print(f"Transaction: {result['signature']}")
            print(f"Tokens received: {result['delta_raw']:,}")
        else:
            print(f"❌ F.E.T.C.H failed: {result['error']}")
    
    def handle_validate_command(self, args):
        """Validate if a token is tradeable"""
        if len(args) < 1:
            print("❌ Usage: validate <token_mint>")
            return
        
        token_mint = args[0]
        print(f"🔍 Validating token: {token_mint[:8]}...")
        
        is_valid, msg, data = discovery.validate_token_for_trading(token_mint)
        
        if is_valid:
            print(f"✅ Token is tradeable: {msg}")
            if data.get('expected_tokens_per_sol'):
                print(f"Expected tokens per SOL: ~{data['expected_tokens_per_sol']:,.0f}")
        else:
            print(f"❌ Token not tradeable: {msg}")
    
    def handle_status_command(self):
        """Show system status"""
        print("📊 Mork F.E.T.C.H System Status")
        print("-" * 30)
        
        # Emergency stop
        emergency_ok, emergency_msg = safety.check_emergency_stop()
        print(f"Emergency Stop: {'✅ Normal' if emergency_ok else '🚨 ACTIVE'}")
        
        # Safe mode
        safe_mode_ok, safe_msg = safety.check_safe_mode_limits(0.01)
        print(f"Safe Mode: {'🟡 Active' if safety.safe_mode else '🟢 Disabled'}")
        
        # Limits
        print(f"Max Trade: {safety.max_trade_sol} SOL")
        print(f"Daily Limit: {safety.daily_spend_limit} SOL")
        print(f"MORK Requirement: {safety.min_mork_for_snipe} SOL worth")
    
    def handle_emergency_command(self, args):
        """Handle emergency stop commands"""
        if len(args) < 1:
            emergency_ok, _ = safety.check_emergency_stop()
            status = "ACTIVE" if not emergency_ok else "INACTIVE"
            print(f"🚨 Emergency Stop: {status}")
            return
        
        action = args[0].lower()
        if action in ["stop", "activate"]:
            result = safety.set_emergency_stop(True, self.current_user)
            print(f"🚨 {result}")
        elif action in ["start", "deactivate"]:
            result = safety.set_emergency_stop(False, self.current_user)
            print(f"✅ {result}")
        else:
            print("❌ Use: emergency stop|start")
    
    def handle_safe_command(self, args):
        """Toggle safe mode"""
        if len(args) < 1:
            status = "ON" if safety.safe_mode else "OFF"
            print(f"Safe Mode: {status}")
            return
        
        action = args[0].lower()
        if action == "on":
            safety.safe_mode = True
            safety._save_config()
            print("✅ Safe mode activated")
        elif action == "off":
            safety.safe_mode = False
            safety._save_config()
            print("⚠️ Safe mode disabled")
        else:
            print("❌ Use: safe on|off")
    
    def run(self):
        """Main command loop"""
        self.show_help()
        
        while True:
            try:
                command_line = input("\n🐕 fetch> ").strip()
                
                if not command_line:
                    continue
                
                parts = command_line.split()
                command = parts[0].lower()
                args = parts[1:]
                
                if command in ['exit', 'quit']:
                    print("👋 Goodbye!")
                    break
                elif command == 'help':
                    self.show_help()
                elif command == 'wallet':
                    self.handle_wallet_command(args)
                elif command == 'balance':
                    self.handle_balance_command()
                elif command == 'snipe':
                    self.handle_snipe_command(args)
                elif command == 'fetch':
                    self.handle_fetch_command()
                elif command == 'validate':
                    self.handle_validate_command(args)
                elif command == 'status':
                    self.handle_status_command()
                elif command == 'emergency':
                    self.handle_emergency_command(args)
                elif command == 'safe':
                    self.handle_safe_command(args)
                else:
                    print(f"❌ Unknown command: {command}")
                    print("💡 Type 'help' for available commands")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    bot = SimpleMorkBot()
    bot.run()