# telegram_media.py
import logging
import requests

log = logging.getLogger(__name__)

def send_photo_safe(token: str, chat_id: int | str, image_path: str, caption: str | None = None):
    """
    Send a photo to Telegram chat with safe error handling.
    
    Args:
        token: Telegram bot token
        chat_id: Chat ID to send photo to
        image_path: Path to image file
        caption: Optional caption text
        
    Returns:
        Tuple: (success: bool, status: str, response: dict)
    """
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
        
    try:
        with open(image_path, "rb") as f:
            files = {"photo": f}
            r = requests.post(url, data=data, files=files, timeout=15)
            
        response_data = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        ok = r.ok and response_data.get("ok", False)
        
        if ok:
            log.info(f"[TELEGRAM] Photo sent successfully to chat {chat_id}")
            return (True, "sent_photo", response_data)
        else:
            log.warning(f"[TELEGRAM] Photo send failed to chat {chat_id}: {response_data}")
            return (False, "photo_failed", response_data)
            
    except FileNotFoundError:
        error_msg = f"Image file not found: {image_path}"
        log.error(f"[TELEGRAM] {error_msg}")
        return (False, "file_not_found", {"error": error_msg})
        
    except Exception as e:
        log.exception(f"[TELEGRAM] Photo send exception for chat {chat_id}")
        return (False, "photo_exception", {"exception": str(e)})

def send_document_safe(token: str, chat_id: int | str, document_path: str, caption: str | None = None):
    """
    Send a document to Telegram chat with safe error handling.
    
    Args:
        token: Telegram bot token
        chat_id: Chat ID to send document to
        document_path: Path to document file
        caption: Optional caption text
        
    Returns:
        Tuple: (success: bool, status: str, response: dict)
    """
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
        
    try:
        with open(document_path, "rb") as f:
            files = {"document": f}
            r = requests.post(url, data=data, files=files, timeout=30)
            
        response_data = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        ok = r.ok and response_data.get("ok", False)
        
        if ok:
            log.info(f"[TELEGRAM] Document sent successfully to chat {chat_id}")
            return (True, "sent_document", response_data)
        else:
            log.warning(f"[TELEGRAM] Document send failed to chat {chat_id}: {response_data}")
            return (False, "document_failed", response_data)
            
    except FileNotFoundError:
        error_msg = f"Document file not found: {document_path}"
        log.error(f"[TELEGRAM] {error_msg}")
        return (False, "file_not_found", {"error": error_msg})
        
    except Exception as e:
        log.exception(f"[TELEGRAM] Document send exception for chat {chat_id}")
        return (False, "document_exception", {"exception": str(e)})