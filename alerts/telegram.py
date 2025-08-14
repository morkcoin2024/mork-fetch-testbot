import os

def send_alert(text: str):
    """Send alert to admin using telegram_safety module"""
    try:
        from telegram_safety import send_telegram_safe
        
        # Get tokens from environment
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        admin_chat_id = os.environ.get('ASSISTANT_ADMIN_TELEGRAM_ID')
        
        if not bot_token or not admin_chat_id:
            print(f"[ALERT] Missing tokens - bot_token: {bool(bot_token)}, admin_chat_id: {bool(admin_chat_id)}")
            return False
            
        # Send alert to admin (convert chat_id to int)
        ok, _, _ = send_telegram_safe(bot_token, int(admin_chat_id), text)
        return ok
    except Exception as e:
        print(f"[ALERT] Error sending alert: {e}")
        return False