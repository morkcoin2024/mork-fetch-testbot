import os
import logging
from flask import Flask, request, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "mork-sniper-bot-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///mork_bot.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    from models import UserSession, TradeSimulation  # Import models here
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram webhook updates - FIXED"""
    try:
        update = request.get_json()
        logging.info(f"📨 Webhook received update: {update.get('update_id', 'unknown') if update else 'None'}")
        
        if update:
            with app.app_context():
                # EMERGENCY: Use safe bot during SOL draining crisis  
                from emergency_override_bot import handle_emergency_webhook
                result = handle_emergency_webhook(update)
                logging.info(f"✅ Simplified bot processed update successfully")
        return 'OK', 200
    except Exception as e:
        logging.error(f"❌ Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return 'OK', 200  # Return 200 to prevent retry loops

@app.route('/health')
def health():
    return {'status': 'healthy', 'service': 'Mork F.E.T.C.H Bot'}, 200
