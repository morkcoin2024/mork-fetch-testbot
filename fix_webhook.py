#!/usr/bin/env python3
"""
Fix webhook setup for Mork F.E.T.C.H Bot
"""
import os
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_webhook():
    """Fix the webhook setup with correct URL"""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found")
        return False
    
    # Get the correct Replit domain
    replit_domain = os.environ.get('REPLIT_DOMAINS')
    
    if not replit_domain:
        logger.error("REPLIT_DOMAINS not found")
        logger.info("Available env vars:")
        for key in os.environ:
            if 'REPL' in key or 'DOMAIN' in key:
                logger.info(f"  {key}: {os.environ[key]}")
        return False
    
    # Construct webhook URL
    webhook_url = f"https://{replit_domain}/webhook"
    logger.info(f"Setting webhook to: {webhook_url}")
    
    # Clear any existing webhook first
    clear_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    clear_response = requests.post(clear_url, json={'drop_pending_updates': True})
    logger.info(f"Cleared old webhook: {clear_response.status_code}")
    
    # Set new webhook
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    response = requests.post(api_url, json={'url': webhook_url})
    
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            logger.info("✅ Webhook set successfully!")
            logger.info(f"Description: {result.get('description', 'No description')}")
            
            # Verify webhook
            info_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
            info_response = requests.get(info_url)
            if info_response.status_code == 200:
                webhook_info = info_response.json().get('result', {})
                logger.info(f"Webhook URL: {webhook_info.get('url')}")
                logger.info(f"Pending updates: {webhook_info.get('pending_update_count', 0)}")
                
            logger.info("🚀 Bot should now respond to messages!")
            return True
        else:
            logger.error(f"Failed to set webhook: {result}")
            return False
    else:
        logger.error(f"HTTP error {response.status_code}: {response.text}")
        return False

def test_webhook():
    """Test webhook connectivity"""
    replit_domain = os.environ.get('REPLIT_DOMAINS')
    if replit_domain:
        test_url = f"https://{replit_domain}/health"
        try:
            response = requests.get(test_url, timeout=10)
            logger.info(f"Health check: {response.status_code} - {response.text}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    return False

if __name__ == "__main__":
    logger.info("🔧 Fixing Mork F.E.T.C.H Bot webhook...")
    
    # Test connectivity first
    if test_webhook():
        logger.info("✅ App is accessible")
        if fix_webhook():
            logger.info("🎉 Webhook fixed successfully!")
        else:
            logger.error("❌ Failed to fix webhook")
    else:
        logger.error("❌ App is not accessible")