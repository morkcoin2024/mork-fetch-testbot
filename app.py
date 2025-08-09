"""
app.py - Flask Application
Webhook endpoint for Telegram bot
"""
import os
import logging
from flask import Flask, request, jsonify
from bot import bot_application, process_update

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "online",
        "bot": "Mork F.E.T.C.H Bot",
        "description": "Degens' Best Friend"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    try:
        update_data = request.get_json()
        
        if not update_data:
            logger.warning("Received empty webhook data")
            return jsonify({"error": "No data"}), 400
        
        logger.info(f"📨 Webhook received update: {update_data.get('update_id', 'unknown')}")
        
        # Process update with bot
        success = process_update(update_data)
        
        if success:
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": "Processing failed"}), 500
            
    except Exception as e:
        logger.exception(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/status')
def status():
    """Bot status endpoint"""
    return jsonify({
        "bot_status": "running",
        "safe_mode": os.getenv("SAFE_MODE", "0") == "1",
        "emergency_stop": os.path.exists("EMERGENCY_STOP")
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)