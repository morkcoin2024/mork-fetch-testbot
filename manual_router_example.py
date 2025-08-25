# Manual Router Pattern for Admin Alias Commands
# Alternative implementation for environments with command registration conflicts

from alerts.telegram import (
    _is_admin,
    cmd_logs_stream,
    cmd_logs_tail,
    cmd_logs_watch,
    cmd_mode,
    cmd_ping,
    cmd_status,
    cmd_whoami,
)


async def manual_admin_router(update, context):
    """
    Manual router for admin alias commands.
    Use this pattern if automatic CommandHandler registration has conflicts.
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    # Admin alias command routing
    if text.startswith("/a_status"):
        await cmd_status(update, context)
    elif text.startswith("/a_logs_tail"):
        await cmd_logs_tail(update, context)
    elif text.startswith("/a_logs_stream"):
        await cmd_logs_stream(update, context)
    elif text.startswith("/a_logs_watch"):
        await cmd_logs_watch(update, context)
    elif text.startswith("/a_mode"):
        await cmd_mode(update, context)
    elif text.startswith("/a_ping"):
        await cmd_ping(update, context)
    elif text.startswith("/a_whoami"):
        await cmd_whoami(update, context)

    # Standard command routing (if needed)
    elif text.startswith("/status") and _is_admin(update):
        await cmd_status(update, context)
    elif text.startswith("/logs_tail") and _is_admin(update):
        await cmd_logs_tail(update, context)
    elif text.startswith("/logs_stream") and _is_admin(update):
        await cmd_logs_stream(update, context)
    elif text.startswith("/logs_watch") and _is_admin(update):
        await cmd_logs_watch(update, context)
    elif text.startswith("/mode") and _is_admin(update):
        await cmd_mode(update, context)
    elif text.startswith("/ping"):
        await cmd_ping(update, context)
    elif text.startswith("/whoami"):
        await cmd_whoami(update, context)


# Usage in main.py for manual routing:
# app.add_handler(MessageHandler(filters.TEXT, manual_admin_router), group=0)

# Command mapping for dynamic routing
ADMIN_COMMAND_MAP = {
    "/a_status": cmd_status,
    "/a_logs_tail": cmd_logs_tail,
    "/a_logs_stream": cmd_logs_stream,
    "/a_logs_watch": cmd_logs_watch,
    "/a_mode": cmd_mode,
    "/a_ping": cmd_ping,
    "/a_whoami": cmd_whoami,
    "/status": cmd_status,
    "/logs_tail": cmd_logs_tail,
    "/logs_stream": cmd_logs_stream,
    "/logs_watch": cmd_logs_watch,
    "/mode": cmd_mode,
    "/ping": cmd_ping,
    "/whoami": cmd_whoami,
}


async def dynamic_admin_router(update, context):
    """
    Dynamic router using command mapping.
    More maintainable for large command sets.
    """
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    command = text.split()[0]  # Get first word (command)

    if command in ADMIN_COMMAND_MAP:
        # Admin authorization check for non-alias commands
        if not command.startswith("/a_") and not _is_admin(update):
            await update.message.reply_text("Not authorized.")
            return

        # Execute the command
        handler = ADMIN_COMMAND_MAP[command]
        await handler(update, context)
