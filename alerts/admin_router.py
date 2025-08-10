# alerts/admin_router.py  (PTB v20+)
import logging, re
try:
    from telegram.ext import ApplicationHandlerStop
except ImportError:
    # Fallback for environments without full PTB support
    class ApplicationHandlerStop(Exception):
        pass

from config import ASSISTANT_ADMIN_TELEGRAM_ID
from alerts.telegram import (
    cmd_status, cmd_logs_tail, cmd_logs_stream, cmd_logs_watch, cmd_mode,
    cmd_ping, cmd_whoami,
)

def _is_admin(update) -> bool:
    return getattr(update.effective_user, "id", None) == ASSISTANT_ADMIN_TELEGRAM_ID

# IMPORTANT: async for PTB v20
async def admin_router(update, context):
    """
    High-priority interceptor for admin aliases (/a_*).
    Runs before all other handlers; if matched and executed,
    it stops further processing so legacy 'unknown' won't fire.
    """
    logging.info(f"[ADMIN_ROUTER] Processing update: {type(update).__name__}")
    
    msg = getattr(update, "message", None) or getattr(update, "edited_message", None)
    if not msg or not msg.text:
        logging.info(f"[ADMIN_ROUTER] No message or text found, skipping")
        return
    
    text = msg.text.strip()
    user_id = getattr(update.effective_user, "id", None) if update.effective_user else None
    username = getattr(update.effective_user, "username", "unknown") if update.effective_user else "unknown"
    
    logging.info(f"[ADMIN_ROUTER] Message from {username} ({user_id}): '{text}'")

    if not text.startswith("/a_"):
        logging.info(f"[ADMIN_ROUTER] Not an admin alias command, passing through")
        return  # not an admin alias; let others handle

    logging.info(f"[ADMIN_ROUTER] Admin alias command detected: {text}")
    
    if not _is_admin(update):
        logging.warning(f"[ADMIN_ROUTER] Unauthorized access attempt from {username} ({user_id})")
        await msg.reply_text("Not authorized.")
        raise ApplicationHandlerStop  # stop unknown handler from also replying
    
    logging.info(f"[ADMIN_ROUTER] Admin authorized: {username} ({user_id})")

    # Parse and dispatch
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1].split() if len(parts) == 2 else []
    context.args = args  # so the downstream cmds get args

    try:
        logging.info(f"[ADMIN_ROUTER] Executing command: {cmd} with args: {args}")
        
        if cmd == "/a_ping":
            logging.info(f"[ADMIN_ROUTER] Calling cmd_ping")
            await cmd_ping(update, context)
        elif cmd == "/a_whoami":
            logging.info(f"[ADMIN_ROUTER] Calling cmd_whoami")
            await cmd_whoami(update, context)
        elif cmd == "/a_status":
            logging.info(f"[ADMIN_ROUTER] Calling cmd_status")
            await cmd_status(update, context)
        elif cmd == "/a_logs_tail":
            logging.info(f"[ADMIN_ROUTER] Calling cmd_logs_tail")
            await cmd_logs_tail(update, context)
        elif cmd == "/a_logs_stream":
            logging.info(f"[ADMIN_ROUTER] Calling cmd_logs_stream")
            await cmd_logs_stream(update, context)
        elif cmd == "/a_logs_watch":
            logging.info(f"[ADMIN_ROUTER] Calling cmd_logs_watch")
            await cmd_logs_watch(update, context)
        elif cmd == "/a_mode":
            logging.info(f"[ADMIN_ROUTER] Calling cmd_mode")
            await cmd_mode(update, context)
        else:
            logging.warning(f"[ADMIN_ROUTER] Unknown admin alias: {cmd}")
            await msg.reply_text("Unknown admin alias.")
            
        logging.info(f"[ADMIN_ROUTER] Command {cmd} completed successfully")
        # STOP propagation so legacy unknown handler won't fire
        raise ApplicationHandlerStop
        
    except ApplicationHandlerStop:
        logging.info(f"[ADMIN_ROUTER] Handler stop raised for {cmd}")
        raise
    except Exception as e:
        logging.exception(f"[ADMIN_ROUTER] Error executing {cmd}")
        await msg.reply_text(f"admin router error: {e}")
        raise ApplicationHandlerStop