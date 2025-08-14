# telegram_media.py
import logging, requests

def send_photo_safe(token: str, chat_id: int, image_path: str, caption: str | None = None):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    try:
        with open(image_path, "rb") as f:
            files = {"photo": f}
            r = requests.post(url, data=data, files=files, timeout=15)
        ok = r.ok and r.json().get("ok", False)
        return (True, "sent_photo", r.json()) if ok else (False, "photo_failed", r.json())
    except Exception as e:
        logging.exception("telegram_photo_exception")
        return False, "photo_exception", {"exception": str(e)}