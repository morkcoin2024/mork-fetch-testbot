"""
risk.py - Risk Management and Safety Checks
Token sanity checks, gas validation, and safety guardrails
"""
import os
import logging
import requests
from typing import Dict, Tuple
from jupiter_engine import _get_sol_balance

logger = logging.getLogger(__name__)

# Safety constants
MIN_SOL_HEADROOM = 0.01  # Minimum SOL to keep for rent/fees
MAX_SINGLE_TRADE_SOL = 1.0  # Maximum SOL per trade (safety cap)
BLOCKLIST_MINTS = set()  # Known bad tokens

def gas_headroom_ok(pubkey: str, required_sol: float) -> Tuple[bool, str]:
    """
    Check if wallet has enough SOL headroom for trade + rent/fees
    Returns (is_ok, reason)
    """
    try:
        current_balance = _get_sol_balance(pubkey)
        total_required = required_sol + MIN_SOL_HEADROOM
        
        if current_balance >= total_required:
            return True, f"Balance OK: {current_balance:.6f} SOL"
        else:
            return False, f"Insufficient SOL: {current_balance:.6f} < {total_required:.6f} (includes {MIN_SOL_HEADROOM} headroom)"
            
    except Exception as e:
        logger.error(f"Gas headroom check failed: {e}")
        return False, f"Balance check failed: {e}"

def basic_token_sanity(mint: str) -> Tuple[bool, str]:
    """
    Basic token safety checks
    Returns (is_safe, reason)
    """
    try:
        # Check blocklist
        if mint in BLOCKLIST_MINTS:
            return False, "Token is blocklisted"
            
        # Check mint format
        if len(mint) != 44:
            return False, "Invalid mint address format"
            
        # For now, basic checks pass
        # TODO: Add more sophisticated checks:
        # - Mint authority checks
        # - Freeze authority checks  
        # - Liquidity thresholds
        # - Creator reputation
        
        return True, "Basic checks passed"
        
    except Exception as e:
        logger.error(f"Token sanity check failed: {e}")
        return False, f"Safety check failed: {e}"

def validate_trade_amount(sol_amount: float, user_spend_cap: float = None) -> Tuple[bool, str]:
    """
    Validate trade amount against safety limits
    Returns (is_valid, reason)
    """
    try:
        # Check minimum amount
        if sol_amount <= 0:
            return False, "Amount must be positive"
            
        if sol_amount < 0.001:  # 0.001 SOL minimum
            return False, "Amount too small (min 0.001 SOL)"
            
        # Check maximum amount
        if sol_amount > MAX_SINGLE_TRADE_SOL:
            return False, f"Amount too large (max {MAX_SINGLE_TRADE_SOL} SOL)"
            
        # Check user's spend cap
        if user_spend_cap and sol_amount > user_spend_cap:
            return False, f"Exceeds spend cap: {sol_amount} > {user_spend_cap} SOL"
            
        return True, f"Amount OK: {sol_amount} SOL"
        
    except Exception as e:
        logger.error(f"Trade amount validation failed: {e}")
        return False, f"Validation failed: {e}"

def check_emergency_stop() -> Tuple[bool, str]:
    """
    Check if emergency stop is active
    Returns (is_stopped, reason)
    """
    try:
        # Check environment variable
        if os.getenv("EMERGENCY_STOP", "0") == "1":
            return True, "Global emergency stop is active"
            
        # Check file-based stop
        if os.path.exists("EMERGENCY_STOP"):
            return True, "Emergency stop file detected"
            
        return False, "No emergency stop"
        
    except Exception as e:
        logger.error(f"Emergency stop check failed: {e}")
        return False, "Emergency stop check failed"

def check_safe_mode() -> bool:
    """Check if safe mode is enabled"""
    return os.getenv("SAFE_MODE", "0") == "1"

def comprehensive_safety_check(
    pubkey: str,
    mint: str, 
    sol_amount: float,
    user_spend_cap: float = None
) -> Tuple[bool, str]:
    """
    Run all safety checks before executing trade
    Returns (is_safe, reason)
    """
    try:
        # Check safe mode
        if check_safe_mode():
            return False, "SAFE_MODE is enabled - no real trades"
            
        # Check emergency stop
        is_stopped, stop_reason = check_emergency_stop()
        if is_stopped:
            return False, f"Trading halted: {stop_reason}"
            
        # Check trade amount
        amount_ok, amount_reason = validate_trade_amount(sol_amount, user_spend_cap)
        if not amount_ok:
            return False, amount_reason
            
        # Check token safety
        token_ok, token_reason = basic_token_sanity(mint)
        if not token_ok:
            return False, token_reason
            
        # Check gas headroom
        gas_ok, gas_reason = gas_headroom_ok(pubkey, sol_amount)
        if not gas_ok:
            return False, gas_reason
            
        return True, "All safety checks passed"
        
    except Exception as e:
        logger.error(f"Comprehensive safety check failed: {e}")
        return False, f"Safety check failed: {e}"