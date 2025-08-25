from config import ADMIN_CHAT_ID

# Import these from your app/config
from config import TELEGRAM_BOT_TOKEN as BOT_TOKEN  # ensure these exist
from telegram_safety import send_telegram_safe


def send_alert(text: str):
    """Send an alert to the admin chat (Markdown-safe)."""
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return False
    ok, _, _ = send_telegram_safe(BOT_TOKEN, ADMIN_CHAT_ID, text)
    return ok
