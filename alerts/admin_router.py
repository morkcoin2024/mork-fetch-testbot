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
    msg = getattr(update, "message", None) or getattr(update, "edited_message", None)
    if not msg or not msg.text:
        return
    text = msg.text.strip()

    if not text.startswith("/a_"):
        return  # not an admin alias; let others handle

    if not _is_admin(update):
        await msg.reply_text("Not authorized.")
        raise ApplicationHandlerStop  # stop unknown handler from also replying

    # Parse and dispatch
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1].split() if len(parts) == 2 else []
    context.args = args  # so the downstream cmds get args

    try:
        if cmd == "/a_ping":
            await cmd_ping(update, context)
        elif cmd == "/a_whoami":
            await cmd_whoami(update, context)
        elif cmd == "/a_status":
            await cmd_status(update, context)
        elif cmd == "/a_logs_tail":
            await cmd_logs_tail(update, context)
        elif cmd == "/a_logs_stream":
            await cmd_logs_stream(update, context)
        elif cmd == "/a_logs_watch":
            await cmd_logs_watch(update, context)
        elif cmd == "/a_mode":
            await cmd_mode(update, context)
        else:
            await msg.reply_text("Unknown admin alias.")
        # STOP propagation so legacy unknown handler won't fire
        raise ApplicationHandlerStop
    except ApplicationHandlerStop:
        raise
    except Exception as e:
        logging.exception("admin_router error")
        await msg.reply_text(f"admin router error: {e}")
        raise ApplicationHandlerStop