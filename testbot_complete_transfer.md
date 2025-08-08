# Complete MorkSniperTestBot File Transfer Guide

## Step 1: Get Your Test Bot Token First

Message @BotFather on Telegram:
- `/newbot`
- Name: "Mork F.E.T.C.H Test Bot"
- Username: "MorkSniperTestBot"
- Save the token (looks like: 1234567890:ABCdef...)

## Step 2: Copy These Files to Your New Test Bot Project

### File 1: main.py
```python
from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

### File 2: app.py (Replace existing)
```python
import os
import logging
from flask import Flask, request, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from models import db

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "test-bot-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///test_bot.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    from models import UserSession, TradeSimulation, ActiveTrade  # Import models here
    db.create_all()

@app.route('/')
def index():
    return "🤖 MorkSniperTestBot is running! This is the test environment."

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram webhook updates"""
    try:
        update = request.get_json()
        logging.info(f"Received webhook update: {update}")
        if update:
            with app.app_context():
                import bot
                result = bot.handle_update(update)
                logging.info(f"Bot handled update successfully")
        return 'OK', 200
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return 'OK', 200  # Return 200 to prevent retry loops

@app.route('/health')
def health():
    return {'status': 'healthy', 'service': 'Mork F.E.T.C.H Test Bot'}, 200
```

### File 3: pyproject.toml (Replace existing)
```toml
[project]
name = "mork-sniper-test-bot"
version = "1.0.0"
description = "Test version of Mork F.E.T.C.H Bot"
requires-python = ">=3.11"
dependencies = [
    "aiohttp>=3.12.15",
    "anthropic>=0.61.0",
    "asyncio>=4.0.0",
    "base58>=2.1.1",
    "beautifulsoup4>=4.13.4",
    "cryptography>=45.0.6",
    "email-validator>=2.2.0",
    "flask>=3.1.1",
    "flask-sqlalchemy>=3.1.1",
    "gunicorn>=23.0.0",
    "httpx>=0.28.1",
    "numpy>=2.3.2",
    "openai>=1.99.1",
    "pandas>=2.3.1",
    "psycopg2-binary>=2.9.10",
    "python-dotenv>=1.1.1",
    "requests>=2.32.4",
    "scikit-learn>=1.7.1",
    "selenium>=4.34.2",
    "solana>=0.36.7",
    "solders>=0.26.0",
    "sqlalchemy>=2.0.42",
    "trafilatura>=2.0.0",
    "websocket-client>=1.8.0",
    "websockets>=15.0.1",
    "werkzeug>=3.1.3",
]
```

## Step 3: Configure Secrets

In your test bot project, go to Secrets (lock icon) and add:

1. **TELEGRAM_BOT_TOKEN** = Your new test bot token from @BotFather
2. **DATABASE_URL** = Copy from production bot
3. **OPENAI_API_KEY** = Copy from production bot

## Step 4: Ready for Additional Files

Once you have these 3 files created and secrets configured, I'll send you the remaining core files:
- models.py (database models)
- bot.py (main bot logic - cleaned for test environment)
- wallet_integration.py
- pump_fun_trading.py
- And other essential modules

This creates a complete, isolated test environment that won't interfere with your production @MorkSniperBot.