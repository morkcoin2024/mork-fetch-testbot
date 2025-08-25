# telegram_safety.py
import logging
import re
import time

import requests

# Reserved characters for Telegram MarkdownV2 that need escaping
# (space is NOT required to be escaped; keep it out to preserve text)
_MD2_RESERVED = r"_*[]()~`>#+-=|{}.!?"


def escape_markdown_v2(text: str) -> str:
    # Escape every reserved character with a backslash
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!?])", r"\\\1", text)


# Heuristic: does the text *look* like it intends Markdown?
_MD_TOKENS = re.compile(r"(\*[^*\n]+\*|_[^_\n]+_|`[^`\n]+`|```[\s\S]+?```|^#{1,6}\s|\~\~[^~\n]+~~)")


def looks_like_markdown(text: str) -> bool:
    return bool(_MD_TOKENS.search(text))


def balanced_md(text: str) -> bool:
    """Cheap balance check for common Markdown pairs."""
    # even counts for paired tokens
    if text.count("**") % 2 != 0:
        return False
    if text.count("__") % 2 != 0:
        return False
    if text.count("``") % 2 != 0:
        return False
    if text.count("`") % 2 != 0:
        return False  # single backticks
    if text.count("~~") % 2 != 0:
        return False

    # bracket/paren stack
    stack = []
    pairs = {")": "(", "]": "["}
    for ch in text:
        if ch in "([":
            stack.append(ch)
        elif ch in ")]":
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack


def send_telegram_safe(token: str, chat_id: int, text: str, disable_preview: bool = True):
    """
    Unified safe sender:
      1) If text *looks* like Markdown and balances, try MarkdownV2 (escaped)
      2) If that fails, retry plain text
    Returns: (ok: bool, status: str, resp_json: dict|None)
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    def _post(payload):
        try:
            r = requests.post(url, json=payload, timeout=10)
            ok = r.ok and r.json().get("ok", False)
            return ok, r.json()
        except Exception as e:
            logging.exception("telegram_send_exception")
            return False, {"ok": False, "exception": str(e)}

    _ = False
    if looks_like_markdown(text) and balanced_md(text):
        _ = True
        md_text = escape_markdown_v2(text)
        ok, js = _post(
            {
                "chat_id": chat_id,
                "text": md_text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": disable_preview,
            }
        )
        if ok:
            return True, "sent_md2", js
        # log and fall through to plain
        desc = (js or {}).get("description", "")
        logging.warning("telegram_md2_failed: %s", desc)
        time.sleep(0.03)

    ok, js = _post({"chat_id": chat_id, "text": text, "disable_web_page_preview": disable_preview})
    return (True, "sent_plain", js) if ok else (False, "failed_all", js)
