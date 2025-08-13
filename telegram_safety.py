# telegram_safety.py
import re
import time
import logging
import requests

# Telegram MarkdownV2 reserved chars that must be escaped
_MD2_RESERVED = r"_*[]()~`>#+-=|{}.! "

def escape_markdown_v2(text: str) -> str:
    # Escape every reserved character with a backslash
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)

# quick heuristic: if text has obvious md tokens, we *may* try MD
_MD_TOKENS = re.compile(r"(\*.+\*|_.+_|`.+`|\[.+?\]\(.+?\)|^#{1,6}\s)")

def looks_like_markdown(text: str) -> bool:
    return bool(_MD_TOKENS.search(text))

# Lightweight balance checks (not perfect, but cheap & safe)
def balanced_md(text: str) -> bool:
    # pairs: **, __, ``, (), [], ()
    def count_pair(tok):
        return text.count(tok) % 2 == 0
    # single char pairs
    simple_ok = (
        count_pair("**") and
        count_pair("__") and
        count_pair("``")    # if you use ``…`` anywhere
    )
    # parens/brackets
    stack = []
    for ch in text:
        if ch in "([": stack.append(ch)
        elif ch == ")" and (not stack or stack.pop() != "("): return False
        elif ch == "]" and (not stack or stack.pop() != "["): return False
    brackets_ok = (len(stack) == 0)
    return simple_ok and brackets_ok

def send_telegram_safe(token: str, chat_id: int, text: str, retry_plain_on_fail: bool = True):
    """
    Unified, safe sender:
    1) If text *looks* like Markdown and is balanced, try MarkdownV2 (escaped)
    2) If that fails (can't parse entities), retry as plain text
    Always returns (ok: bool, status: str, resp_json: dict|None)
    """
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    def _post(payload):
        try:
            r = requests.post(url, json=payload, timeout=8)
            ok = r.ok and r.json().get("ok", False)
            return ok, r.json()
        except Exception as e:
            logging.exception("telegram_send_exception")
            return False, {"error": str(e)}

    # Try MarkdownV2 when appropriate
    tried_md = False
    if looks_like_markdown(text) and balanced_md(text):
        tried_md = True
        md_text = escape_markdown_v2(text)
        ok, js = _post({"chat_id": chat_id, "text": md_text, "parse_mode": "MarkdownV2", "disable_web_page_preview": True})
        if ok:
            return True, "sent_md2", js
        # If parse error, fall through
        err_desc = (js or {}).get("description", "")
        logging.warning("telegram_md2_failed", extra={"desc": err_desc})
        # Optional: small wait to avoid rapid double-send
        time.sleep(0.05)

    # Fallback to plain text
    if (not tried_md) or retry_plain_on_fail:
        ok, js = _post({"chat_id": chat_id, "text": text, "disable_web_page_preview": True})
        if ok:
            return True, "sent_plain", js
        return False, "failed_all", js

    return False, "skipped_plain", None