from telegram_safety import send_telegram_safe

# Import these from your app/config
from app import BOT_TOKEN, ADMIN_CHAT_ID  # ensure these exist

def send_alert(text: str):
    """Send an alert to the admin chat (Markdown-safe)."""
    ok, _, _ = send_telegram_safe(BOT_TOKEN, ADMIN_CHAT_ID, text)
    return ok