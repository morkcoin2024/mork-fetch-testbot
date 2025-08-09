"""
simple_app.py - Simplified Flask App for Testing
Tests core functionality without Telegram dependencies
"""
import os
import json
import logging
from flask import Flask, request, jsonify

# Core module imports
from jupiter_engine import safe_swap_via_jupiter
from discovery import get_working_token, is_bonded_and_routable
from wallet import create_wallet, import_wallet, get_wallet, get_private_key
from risk import comprehensive_safety_check, check_safe_mode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "test-secret"

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "online",
        "bot": "Mork F.E.T.C.H Bot (Simple Mode)",
        "description": "Production Core Testing"
    })

@app.route('/create_wallet/<chat_id>')
def test_create_wallet(chat_id):
    """Test wallet creation"""
    result = create_wallet(chat_id)
    return jsonify(result)

@app.route('/import_wallet/<chat_id>/<private_key>')
def test_import_wallet(chat_id, private_key):
    """Test wallet import"""
    result = import_wallet(chat_id, private_key)
    return jsonify(result)

@app.route('/wallet_status/<chat_id>')
def test_wallet_status(chat_id):
    """Test wallet status check"""
    wallet = get_wallet(chat_id)
    if wallet:
        from jupiter_engine import _get_sol_balance
        sol_balance = _get_sol_balance(wallet['pubkey'])
        return jsonify({
            "wallet_found": True,
            "pubkey": wallet['pubkey'],
            "sol_balance": sol_balance,
            "safe_mode": check_safe_mode()
        })
    else:
        return jsonify({"wallet_found": False})

@app.route('/discover_tokens')
def test_token_discovery():
    """Test token discovery"""
    token = get_working_token()
    if token:
        return jsonify({
            "success": True,
            "token": token
        })
    else:
        return jsonify({
            "success": False,
            "error": "No working tokens found"
        })

@app.route('/test_snipe/<chat_id>/<mint>/<sol_amount>')
def test_snipe(chat_id, mint, sol_amount):
    """Test snipe functionality without real trade"""
    try:
        sol_amount = float(sol_amount)
        
        # Check wallet
        wallet = get_wallet(chat_id)
        if not wallet:
            return jsonify({"error": "No wallet linked"})
            
        # Check if token is routable
        is_routable, reason = is_bonded_and_routable(mint)
        if not is_routable:
            return jsonify({"error": f"Token not routable: {reason}"})
            
        # Safety checks
        safety_ok, safety_msg = comprehensive_safety_check(wallet['pubkey'], mint, sol_amount)
        if not safety_ok:
            return jsonify({"error": f"Safety check failed: {safety_msg}"})
            
        return jsonify({
            "success": True,
            "message": f"Ready to trade {sol_amount} SOL for {mint[:8]}...",
            "routable": True,
            "route_reason": reason,
            "safety_passed": True
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/execute_trade/<chat_id>/<mint>/<sol_amount>')
def test_real_trade(chat_id, mint, sol_amount):
    """Execute REAL trade (use with caution!)"""
    try:
        sol_amount = float(sol_amount)
        
        # Get private key
        private_key = get_private_key(chat_id)
        if not private_key:
            return jsonify({"error": "Could not access private key"})
            
        # Execute real Jupiter swap
        result = safe_swap_via_jupiter(
            private_key_b58=private_key,
            output_mint_str=mint,
            amount_in_sol=sol_amount,
            slippage_bps=150,
            min_post_delta_raw=1
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.exception(f"Trade execution failed: {e}")
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)