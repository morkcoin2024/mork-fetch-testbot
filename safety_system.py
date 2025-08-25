"""
Safety System for Mork F.E.T.C.H Bot
Implements SAFE_MODE, spend caps, emergency stops, and MORK holder gates
"""

import json
import logging
import os
import time

from config import (
    DAILY_SPEND_LIMIT,
    MAX_TRADE_SOL,
    MIN_MORK_FOR_FETCH,
    MIN_MORK_FOR_SNIPE,
    MORK_MINT,
)

logger = logging.getLogger(__name__)


class SafetySystem:
    """Comprehensive safety and gating system"""

    def __init__(self):
        self.config_file = "safety_config.json"
        self.emergency_stop = False
        self.safe_mode = True  # Start in safe mode
        self.mork_mint = MORK_MINT
        self.min_mork_for_snipe = MIN_MORK_FOR_SNIPE
        self.min_mork_for_fetch = MIN_MORK_FOR_FETCH
        self.max_trade_sol = MAX_TRADE_SOL
        self.daily_spend_limit = DAILY_SPEND_LIMIT
        self._load_config()

    def _load_config(self):
        """Load safety configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file) as f:
                    config = json.load(f)
                self.safe_mode = config.get("safe_mode", True)
                self.emergency_stop = config.get("emergency_stop", False)
                self.max_trade_sol = config.get("max_trade_sol", MAX_TRADE_SOL)
                self.daily_spend_limit = config.get("daily_spend_limit", DAILY_SPEND_LIMIT)
            except Exception as e:
                logger.error(f"Error loading safety config: {e}")

    def _save_config(self):
        """Save safety configuration"""
        try:
            config = {
                "safe_mode": self.safe_mode,
                "emergency_stop": self.emergency_stop,
                "max_trade_sol": self.max_trade_sol,
                "daily_spend_limit": self.daily_spend_limit,
                "updated": int(time.time()),
            }
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving safety config: {e}")

    def check_emergency_stop(self) -> tuple[bool, str]:
        """Check if emergency stop is active"""
        if self.emergency_stop:
            return False, "🚨 EMERGENCY STOP ACTIVE - All trading disabled"
        return True, "Emergency stop: OK"

    def set_emergency_stop(self, active: bool, admin_chat_id: str = None) -> str:
        """Set emergency stop state (admin only)"""
        # TODO: Add proper admin verification
        self.emergency_stop = active
        self._save_config()

        status = "ACTIVATED" if active else "DEACTIVATED"
        logger.warning(f"Emergency stop {status} by {admin_chat_id}")
        return f"🚨 Emergency stop {status}"

    def check_safe_mode_limits(self, amount_sol: float) -> tuple[bool, str]:
        """Check safe mode trading limits"""
        if not self.safe_mode:
            return True, "Safe mode: OFF"

        if amount_sol > self.max_trade_sol:
            return False, f"Safe mode limit: max {self.max_trade_sol} SOL per trade"

        return True, f"Safe mode: OK (limit {self.max_trade_sol} SOL)"

    def check_mork_holdings(
        self, wallet_address: str, required_sol_worth: float
    ) -> tuple[bool, str]:
        """Check if user holds enough MORK tokens for gated features"""
        try:
            from solders.pubkey import Pubkey
            from spl.token.instructions import get_associated_token_address

            from jupiter_engine import jupiter_engine

            # Get user's MORK token balance
            wallet_pubkey = Pubkey.from_string(wallet_address)
            mork_pubkey = Pubkey.from_string(self.mork_mint)
            mork_ata = get_associated_token_address(wallet_pubkey, mork_pubkey)
            mork_balance = jupiter_engine.get_token_balance(str(mork_ata))

            if mork_balance == 0:
                return False, f"❌ No MORK tokens found. Need ≥{required_sol_worth} SOL worth"

            # Get MORK price in SOL via Jupiter quote
            is_routable, route_msg = jupiter_engine.check_token_routable(self.mork_mint, 0.001)
            if is_routable and "tokens expected" in route_msg:
                try:
                    # Extract tokens per 0.001 SOL
                    tokens_per_milli_sol = int(
                        route_msg.split("tokens expected")[0].split(" - ")[-1].replace(",", "")
                    )
                    tokens_per_sol = tokens_per_milli_sol / 0.001
                    required_mork_tokens = int(required_sol_worth * tokens_per_sol)

                    if mork_balance >= required_mork_tokens:
                        sol_worth = mork_balance / tokens_per_sol
                        return (
                            True,
                            f"✅ MORK verified: {sol_worth:.3f} SOL worth (need {required_sol_worth})",
                        )
                    else:
                        sol_worth = mork_balance / tokens_per_sol
                        return (
                            False,
                            f"❌ Insufficient MORK: {sol_worth:.3f} SOL worth (need {required_sol_worth})",
                        )
                except:
                    return False, "❌ MORK price verification failed"
            else:
                return False, "❌ MORK price check unavailable"

        except Exception as e:
            logger.error(f"MORK holdings check failed: {e}")
            return False, f"❌ MORK verification error: {e}"

    def check_daily_limits(self, chat_id: str, amount_sol: float) -> tuple[bool, str]:
        """Check daily spending limits per user"""
        try:
            # Load daily spending data
            daily_file = f"daily_limits_{time.strftime('%Y%m%d')}.json"
            daily_spending = {}

            if os.path.exists(daily_file):
                with open(daily_file) as f:
                    daily_spending = json.load(f)

            user_id = str(chat_id)
            current_spending = daily_spending.get(user_id, 0.0)

            if current_spending + amount_sol > self.daily_spend_limit:
                return (
                    False,
                    f"Daily limit exceeded: {current_spending:.3f} + {amount_sol:.3f} > {self.daily_spend_limit}",
                )

            return True, f"Daily limit OK: {current_spending:.3f}/{self.daily_spend_limit} SOL"

        except Exception as e:
            logger.error(f"Daily limits check failed: {e}")
            return True, "Daily limits check failed (allowing)"

    def record_trade(self, chat_id: str, amount_sol: float):
        """Record trade for daily limit tracking"""
        try:
            daily_file = f"daily_limits_{time.strftime('%Y%m%d')}.json"
            daily_spending = {}

            if os.path.exists(daily_file):
                with open(daily_file) as f:
                    daily_spending = json.load(f)

            user_id = str(chat_id)
            daily_spending[user_id] = daily_spending.get(user_id, 0.0) + amount_sol

            with open(daily_file, "w") as f:
                json.dump(daily_spending, f)

        except Exception as e:
            logger.error(f"Failed to record trade: {e}")

    def comprehensive_safety_check(
        self,
        chat_id: str,
        wallet_address: str,
        token_mint: str,
        amount_sol: float,
        feature_type: str = "snipe",
    ) -> tuple[bool, str]:
        """Run all safety checks before trade execution"""

        checks = []

        # Emergency stop check
        ok, msg = self.check_emergency_stop()
        checks.append((ok, msg))
        if not ok:
            return False, msg

        # Safe mode limits
        ok, msg = self.check_safe_mode_limits(amount_sol)
        checks.append((ok, msg))
        if not ok:
            return False, msg

        # MORK holdings gate
        required_mork = (
            self.min_mork_for_fetch if feature_type == "fetch" else self.min_mork_for_snipe
        )
        ok, msg = self.check_mork_holdings(wallet_address, required_mork)
        checks.append((ok, msg))
        if not ok:
            return False, msg

        # Daily spending limits
        ok, msg = self.check_daily_limits(chat_id, amount_sol)
        checks.append((ok, msg))
        if not ok:
            return False, msg

        # All checks passed
        passed_msgs = [msg for ok, msg in checks if ok]
        return True, " | ".join(passed_msgs)


# Global instance
safety = SafetySystem()
