"""
Complete Text Handler Router Implementation
Manual routing pattern for admin alias commands in text handlers
"""

from alerts.telegram import (
    cmd_logs_stream,
    cmd_logs_tail,
    cmd_logs_watch,
    cmd_mode,
    cmd_ping,
    cmd_status,
    cmd_whoami,
)
from config import ASSISTANT_ADMIN_TELEGRAM_ID


def _is_admin(u):
    """Local admin check function for text handler routing"""
    return getattr(u, "id", None) == ASSISTANT_ADMIN_TELEGRAM_ID


async def handle_text_commands(update, context):
    """
    Complete text handler with admin alias routing
    Use this pattern inside your existing text command handler
    """
    text = (update.message.text or "").strip()

    # --- Admin aliases that won't collide with legacy commands ---
    if text.startswith("/a_ping"):
        await cmd_ping(update, context)
        return

    elif text.startswith("/a_whoami"):
        if not _is_admin(update.effective_user):
            await update.message.reply_text("Not authorized.")
            return
        await cmd_whoami(update, context)
        return

    elif text.startswith("/a_status"):
        if not _is_admin(update.effective_user):
            await update.message.reply_text("Not authorized.")
            return
        await cmd_status(update, context)
        return

    elif text.startswith("/a_logs_tail"):
        if not _is_admin(update.effective_user):
            await update.message.reply_text("Not authorized.")
            return
        # Support optional number after command
        parts = text.split()
        context.args = parts[1:] if len(parts) > 1 else []
        await cmd_logs_tail(update, context)
        return

    elif text.startswith("/a_logs_stream"):
        if not _is_admin(update.effective_user):
            await update.message.reply_text("Not authorized.")
            return
        parts = text.split()
        context.args = parts[1:] if len(parts) > 1 else []
        await cmd_logs_stream(update, context)
        return

    elif text.startswith("/a_logs_watch"):
        if not _is_admin(update.effective_user):
            await update.message.reply_text("Not authorized.")
            return
        parts = text.split(maxsplit=1)
        context.args = parts[1].split() if len(parts) == 2 else []
        await cmd_logs_watch(update, context)
        return

    elif text.startswith("/a_mode"):
        if not _is_admin(update.effective_user):
            await update.message.reply_text("Not authorized.")
            return
        parts = text.split()
        context.args = parts[1:] if len(parts) > 1 else []
        await cmd_mode(update, context)
        return

    # Standard command routing (if needed as fallback)
    elif text.startswith("/ping"):
        await cmd_ping(update, context)
        return

    elif text.startswith("/whoami"):
        await cmd_whoami(update, context)
        return

    elif text.startswith("/status") and _is_admin(update.effective_user):
        await cmd_status(update, context)
        return

    elif text.startswith("/logs_tail") and _is_admin(update.effective_user):
        parts = text.split()
        context.args = parts[1:] if len(parts) > 1 else []
        await cmd_logs_tail(update, context)
        return

    elif text.startswith("/logs_stream") and _is_admin(update.effective_user):
        parts = text.split()
        context.args = parts[1:] if len(parts) > 1 else []
        await cmd_logs_stream(update, context)
        return

    elif text.startswith("/logs_watch") and _is_admin(update.effective_user):
        parts = text.split(maxsplit=1)
        context.args = parts[1].split() if len(parts) == 2 else []
        await cmd_logs_watch(update, context)
        return

    elif text.startswith("/mode") and _is_admin(update.effective_user):
        parts = text.split()
        context.args = parts[1:] if len(parts) > 1 else []
        await cmd_mode(update, context)
        return

    # Handle /help and other legacy commands here
    elif text.startswith("/help"):
        help_text = """
🤖 Mork F.E.T.C.H Bot Commands

**Basic Commands:**
/ping - Test bot responsiveness
/whoami - Show your Telegram info

**Admin Commands (aliases available):**
/status, /a_status - System status
/logs_tail [n], /a_logs_tail [n] - Last n log lines
/logs_stream on|off, /a_logs_stream on|off - Stream logs
/logs_watch <regex>, /a_logs_watch <regex> - Watch for pattern
/mode polling|webhook, /a_mode polling|webhook - Switch mode

*Admin aliases (a_*) avoid conflicts with legacy commands*
        """
        await update.message.reply_text(help_text)
        return

    # Unknown command fallback
    else:
        if text.startswith("/"):
            await update.message.reply_text("Unknown command. Type /help for available commands.")
        return


# Integration example for existing bots:
"""
# In your existing message handler:
async def on_message(update, context):
    # Handle admin alias commands first
    await handle_text_commands(update, context)

    # Your existing message handling logic continues here...
    # (Only reached if no command was handled above)
"""


# Alternative compact implementation for tight integration:
async def handle_admin_aliases_only(update, context):
    """
    Compact version for bots that only need admin alias support
    """
    text = (update.message.text or "").strip()

    if not text.startswith("/a_"):
        return False  # Not an admin alias

    if not _is_admin(update.effective_user):
        await update.message.reply_text("Not authorized.")
        return True

    # Parse command and arguments
    parts = text.split()
    cmd = parts[0][3:]  # Remove "/a_" prefix
    context.args = parts[1:] if len(parts) > 1 else []

    # Route to appropriate handler
    handlers = {
        "ping": cmd_ping,
        "whoami": cmd_whoami,
        "status": cmd_status,
        "logs_tail": cmd_logs_tail,
        "logs_stream": cmd_logs_stream,
        "logs_watch": cmd_logs_watch,
        "mode": cmd_mode,
    }

    if cmd in handlers:
        # Special handling for logs_watch arguments
        if cmd == "logs_watch" and len(parts) > 1:
            context.args = [" ".join(parts[1:])]

        await handlers[cmd](update, context)
        return True

    return False  # Unknown admin alias
