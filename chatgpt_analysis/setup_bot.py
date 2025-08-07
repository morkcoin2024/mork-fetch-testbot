#!/usr/bin/env python3
"""
Setup script to configure the Mork F.E.T.C.H Bot webhook
Run this script after setting the BOT_TOKEN environment variable
"""
import os
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_webhook():
    """Set up the Telegram webhook for the bot"""
    bot_token = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
    
    # Get the Replit domain
    replit_domain = os.environ.get("REPL_SLUG", "mork-sniper-bot")
    replit_user = os.environ.get("REPL_OWNER", "")
    
    # Construct webhook URL
    if replit_user:
        webhook_url = f"https://{replit_domain}.{replit_user}.repl.co/webhook"
    else:
        # Fallback to manual entry
        webhook_url = input("Enter your Replit app URL (e.g., https://your-app.replit.app/webhook): ")
        if not webhook_url.endswith('/webhook'):
            webhook_url += '/webhook'
    
    logger.info(f"Setting webhook to: {webhook_url}")
    
    # Set webhook
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    response = requests.post(api_url, json={'url': webhook_url})
    
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            logger.info("✅ Webhook set successfully!")
            logger.info(f"Description: {result.get('description', 'No description')}")
            
            # Test the bot info
            info_url = f"https://api.telegram.org/bot{bot_token}/getMe"
            info_response = requests.get(info_url)
            if info_response.status_code == 200:
                bot_info = info_response.json()
                if bot_info.get('ok'):
                    bot_data = bot_info['result']
                    logger.info(f"Bot Username: @{bot_data.get('username')}")
                    logger.info(f"Bot Name: {bot_data.get('first_name')}")
                    logger.info("🚀 Bot is ready to receive messages!")
                else:
                    logger.error("Failed to get bot info")
            return True
        else:
            logger.error(f"Failed to set webhook: {result}")
            return False
    else:
        logger.error(f"HTTP error {response.status_code}: {response.text}")
        return False

def check_webhook():
    """Check current webhook status"""
    bot_token = "8133024100:AAGQpJYAKK352Dkx93feKfbC0pM_bTVU824"
    
    api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    response = requests.get(api_url)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            webhook_info = result['result']
            logger.info("📡 Current webhook status:")
            logger.info(f"URL: {webhook_info.get('url', 'Not set')}")
            logger.info(f"Has custom certificate: {webhook_info.get('has_custom_certificate', False)}")
            logger.info(f"Pending update count: {webhook_info.get('pending_update_count', 0)}")
            if webhook_info.get('last_error_date'):
                logger.warning(f"Last error: {webhook_info.get('last_error_message', 'Unknown error')}")
        else:
            logger.error(f"Failed to get webhook info: {result}")
    else:
        logger.error(f"HTTP error {response.status_code}: {response.text}")

if __name__ == "__main__":
    print("🤖 Mork F.E.T.C.H Bot Setup")
    print("=" * 50)
    
    print("\n1. Checking current webhook status...")
    check_webhook()
    
    print("\n2. Setting up new webhook...")
    success = setup_webhook()
    
    if success:
        print("\n✅ Setup complete! Your bot is now ready.")
        print("Users can start chatting with @MorkSniperBot on Telegram!")
        print("\nAvailable commands:")
        print("• /start - Welcome message and instructions")
        print("• /snipe - Start a simulation snipe")
        print("• /status - Check current session")
        print("• /help - Show help information")
    else:
        print("\n❌ Setup failed. Please check the logs above.")