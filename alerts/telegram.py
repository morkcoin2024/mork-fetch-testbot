"""
Telegram Alert Handlers for Mork F.E.T.C.H Bot
Advanced async admin commands for system monitoring and control
"""

import logging
logging.basicConfig(level=logging.INFO)
logging.info(">>> LOADED alerts.telegram vDEBUG-1 <<<")

import os, re, time, asyncio, logging, pathlib
from typing import Dict, Optional, Tuple

try:
    from telegram import __version__ as PTB_VERSION
    from telegram.constants import ParseMode
except ImportError:
    PTB_VERSION = "Unknown"
    ParseMode = None

from config import ASSISTANT_ADMIN_TELEGRAM_ID

LOG_PATH = pathlib.Path("logs/app.log")
STREAM_TASKS: Dict[int, asyncio.Task] = {}
WATCH_TASKS: Dict[int, asyncio.Task] = {}


def _is_admin(update) -> bool:
    return getattr(update.effective_user, "id", None) == ASSISTANT_ADMIN_TELEGRAM_ID

def _tail_lines(path: pathlib.Path, n: int = 200) -> str:
    if not path.exists():
        return f"(no log file at {path})"
    # Efficient-ish tail without loading whole file
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        block = 4096
        data = b""
        while size > 0 and data.count(b"\n") <= n:
            read_size = block if size - block > 0 else size
            f.seek(size - read_size)
            data = f.read(read_size) + data
            size -= read_size
    text = data.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-n:])

def _current_mode_text() -> str:
    # Heuristic: if PUBLIC_WEBHOOK_URL is set AND a webhook is configured, you can adapt this.
    # For now we just report that we're in polling mode because main.py starts run_polling().
    return "polling"

def cmd_whoami(update, context):
    uid = update.effective_user.id if update.effective_user else "unknown"
    uname = update.effective_user.username if update.effective_user else "unknown"
    
    logging.info(f"[CMD_WHOAMI] Called by {uname} ({uid})")
    
    try:
        response = update.message.reply_text(f"Your Telegram ID: {uid}\nUsername: @{uname}")
        logging.info(f"[CMD_WHOAMI] Response sent successfully")
        return response
    except Exception as e:
        logging.exception(f"[CMD_WHOAMI] Failed to send response: {e}")
        raise

def cmd_ping(update, context):
    uid = update.effective_user.id if update.effective_user else "unknown"
    uname = update.effective_user.username if update.effective_user else "unknown"
    
    logging.info(f"[CMD_PING] Called by {uname} ({uid})")
    
    try:
        response = update.message.reply_text("pong")
        logging.info(f"[CMD_PING] Response sent successfully")
        return response
    except Exception as e:
        logging.exception(f"[CMD_PING] Failed to send response: {e}")
        raise

async def cmd_status(update, context):
    uid = update.effective_user.id if update.effective_user else "unknown"
    uname = update.effective_user.username if update.effective_user else "unknown"
    
    logging.info(f"[CMD_STATUS] Called by {uname} ({uid})")
    
    if not _is_admin(update):
        logging.warning(f"[CMD_STATUS] Unauthorized access attempt from {uname} ({uid})")
        return await update.message.reply_text("Not authorized.")
    # Build a handler table (groups → handlers)
    try:
        app = context.application
        lines = [f"PTB: {PTB_VERSION}", f"Mode: {_current_mode_text()}"]
        lines.append("Handlers:")
        for grp in sorted(app.handlers.keys()):
            descs = []
            for h in app.handlers[grp]:
                name = type(h).__name__
                cmds = getattr(h, "commands", set())
                if cmds:
                    descs.append(f"{name}({','.join(sorted(cmds))})")
                else:
                    descs.append(name)
            lines.append(f" g{grp}: " + ", ".join(descs))
        txt = "```\n" + "\n".join(lines) + "\n```"
        parse_mode = ParseMode.MARKDOWN if ParseMode else None
        
        logging.info(f"[CMD_STATUS] Sending status response to {uname} ({uid})")
        response = await update.message.reply_text(txt, parse_mode=parse_mode)
        logging.info(f"[CMD_STATUS] Response sent successfully")
        return response
        
    except Exception as e:
        logging.exception(f"[CMD_STATUS] Error: {e}")
        await update.message.reply_text(f"status error: {e}")

async def cmd_logs_tail(update, context):
    if not _is_admin(update):
        return await update.message.reply_text("Not authorized.")
    n = 200
    if context.args:
        try:
            n = max(10, min(1000, int(context.args[0])))
        except Exception:
            pass
    text = _tail_lines(LOG_PATH, n)
    # Keep under Telegram limits
    if len(text) > 3900:
        text = text[-3900:]
        text = "(tail)\n" + text
    parse_mode = ParseMode.MARKDOWN if ParseMode else None
    await update.message.reply_text(f"```\n{text}\n```", parse_mode=parse_mode)

async def _stream_task(chat_id: int, bot, period_sec: float = 5.0, duration_sec: float = 120.0):
    """Send last ~80 lines every few seconds; auto-stop after duration."""
    start = time.time()
    while time.time() - start < duration_sec:
        if chat_id not in STREAM_TASKS:
            break  # cancelled
        text = _tail_lines(LOG_PATH, 80)
        if len(text) > 3900:
            text = "(tail)\n" + text[-3900:]
        try:
            parse_mode = ParseMode.MARKDOWN if ParseMode else None
            await bot.send_message(chat_id, f"```\n{text}\n```", parse_mode=parse_mode)
        except Exception as e:
            logging.warning("logs_stream send failed: %s", e)
            break
        await asyncio.sleep(period_sec)
    STREAM_TASKS.pop(chat_id, None)

async def cmd_logs_stream(update, context):
    if not _is_admin(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /logs_stream on|off")
    mode = context.args[0].lower()
    chat_id = update.effective_chat.id
    if mode == "on":
        if chat_id in STREAM_TASKS and not STREAM_TASKS[chat_id].done():
            return await update.message.reply_text("Already streaming. Use /logs_stream off to stop.")
        task = asyncio.create_task(_stream_task(chat_id, context.bot))
        STREAM_TASKS[chat_id] = task
        return await update.message.reply_text("✅ Log streaming started for ~2 minutes (every 5s).")
    elif mode == "off":
        t = STREAM_TASKS.pop(chat_id, None)
        if t:
            t.cancel()
        return await update.message.reply_text("🛑 Log streaming stopped.")
    else:
        return await update.message.reply_text("Usage: /logs_stream on|off")

async def _watch_task(chat_id: int, bot, pattern: re.Pattern, timeout_sec: float = 300.0):
    """Poll the log for a regex match; stop on first match or timeout."""
    pos = 0
    start = time.time()
    try:
        while time.time() - start < timeout_sec:
            if chat_id not in WATCH_TASKS:
                break
            if not LOG_PATH.exists():
                await asyncio.sleep(2.0); continue
            # Read new bytes from file
            with LOG_PATH.open("rb") as f:
                f.seek(pos)
                chunk = f.read()
                pos = f.tell()
            if chunk:
                text = chunk.decode("utf-8", errors="replace")
                if pattern.search(text):
                    parse_mode = ParseMode.MARKDOWN if ParseMode else None
                    await bot.send_message(chat_id, f"🔔 logs_watch matched: `{pattern.pattern}`", parse_mode=parse_mode)
                    break
            await asyncio.sleep(2.0)
    finally:
        WATCH_TASKS.pop(chat_id, None)

async def cmd_logs_watch(update, context):
    if not _is_admin(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /logs_watch <regex>")
    expr = " ".join(context.args).strip()
    try:
        pat = re.compile(expr)
    except re.error as e:
        return await update.message.reply_text(f"Bad regex: {e}")
    chat_id = update.effective_chat.id
    if chat_id in WATCH_TASKS and not WATCH_TASKS[chat_id].done():
        WATCH_TASKS[chat_id].cancel()
    WATCH_TASKS[chat_id] = asyncio.create_task(_watch_task(chat_id, context.bot, pat))
    parse_mode = ParseMode.MARKDOWN if ParseMode else None
    await update.message.reply_text(f"👀 Watching logs for `{expr}` (up to 5m)…", parse_mode=parse_mode)

async def cmd_mode(update, context):
    if not _is_admin(update):
        return await update.message.reply_text("Not authorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /mode polling|webhook")
    choice = context.args[0].lower()
    if choice == "polling":
        try:
            from telegram import Bot
            token = os.environ["TELEGRAM_BOT_TOKEN"]
            Bot(token).delete_webhook(drop_pending_updates=True)
            parse_mode = ParseMode.MARKDOWN if ParseMode else None
            return await update.message.reply_text("✅ Switched to polling (webhook deleted). *Restart not required.*", parse_mode=parse_mode)
        except Exception as e:
            return await update.message.reply_text(f"Error switching to polling: {e}")
    elif choice == "webhook":
        pub = os.environ.get("PUBLIC_WEBHOOK_URL")
        if not pub:
            return await update.message.reply_text("Set PUBLIC_WEBHOOK_URL first.")
        try:
            import requests
            token = os.environ["TELEGRAM_BOT_TOKEN"]
            r = requests.get(f"https://api.telegram.org/bot{token}/setWebhook", params={"url": pub})
            return await update.message.reply_text(f"Webhook set status {r.status_code}: {r.text[:500]}")
        except Exception as e:
            return await update.message.reply_text(f"Error setting webhook: {e}")
    else:
        return await update.message.reply_text("Usage: /mode polling|webhook")

def unknown(update, context):
    update.message.reply_text("Unknown command. Type /help for available commands.")


# NEW: handler map introspection so we can see priority at runtime
def cmd_debug_handlers(update, context):
    try:
        app = context.application
        lines = ["Handlers by group:"]
        for group, handlers in sorted(app.handlers.items(), key=lambda kv: kv[0]):
            descs = []
            for h in handlers:
                name = type(h).__name__
                if name == "CommandHandler":
                    cmds = getattr(h, "commands", set())
                    descs.append(f"{name}({','.join(sorted(cmds))})")
                else:
                    descs.append(name)
            lines.append(f"g{group}: " + ", ".join(descs))
        txt = "\n".join(lines)
        update.message.reply_text(f"```\n{txt}\n```", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"debug error: {e}")



def cmd_assistant(update, context):
    """Lightweight assistant command handler"""
    from config import ASSISTANT_ADMIN_TELEGRAM_ID, ASSISTANT_WRITE_GUARD, ASSISTANT_FAILSAFE
    from assistant_dev_lite import assistant_codegen, apply_unified_diffs, maybe_run_commands, safe_restart_if_needed, audit_log
    
    uid = update.effective_user.id
    if uid != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Not authorized.")
        return
        
    if ASSISTANT_FAILSAFE == "ON":
        update.message.reply_text("🚫 Assistant patching DISABLED (failsafe ON).")
        return

    req = update.message.text.partition(" ")[2].strip()
    if not req:
        update.message.reply_text("Usage: /assistant <change request>")
        return

    update.message.reply_text("🤔 Thinking… generating patch.")
    
    try:
        result = assistant_codegen(req)
        plan = result.get("plan", "(no plan)")
        diffs = result.get("diffs", [])
        commands = result.get("commands", [])
        restart = result.get("restart", "none")

        apply_res = apply_unified_diffs(diffs)
        cmd_out = maybe_run_commands(commands)

        summary = [
            f"✅ Plan:\n{plan}",
            f"✍️ Mode: {'WRITE' if ASSISTANT_WRITE_GUARD=='ON' else 'DRY-RUN'}",
            f"📝 Applied: {len(apply_res.applied_files)} | Failed: {len(apply_res.failed_files)}",
            ("❌ " + ", ".join(apply_res.failed_files)) if apply_res.failed_files else "✅ No failures",
            f"🔧 Commands: {'ran' if ASSISTANT_WRITE_GUARD=='ON' else 'skipped (dry-run)'}",
            f"♻️ Restart: {restart}",
        ]
        
        response = "\n\n".join(summary)[:4000]
        update.message.reply_text(response)
        
        if diffs:
            diff_preview = f"📋 Diff preview:\n```\n{diffs[0][:3500]}\n```"
            update.message.reply_text(diff_preview, parse_mode='Markdown')
        
        safe_restart_if_needed(restart)
        audit_log(f"ASSISTANT: user_id:{uid} request:'{req[:100]}' applied:{len(apply_res.applied_files)}")
        
    except Exception as e:
        update.message.reply_text(f"❌ Assistant error: {str(e)}")
        audit_log(f"ASSISTANT_ERROR: user_id:{uid} error:'{str(e)}'")



def cmd_assistant_model(update, context):
    """Get/set current assistant model"""
    from config import ASSISTANT_ADMIN_TELEGRAM_ID
    from assistant_dev_lite import get_current_model, set_current_model
    
    uid = update.effective_user.id
    if uid != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("Not authorized.")
        return

    args = update.message.text.split(maxsplit=1)
    if len(args) == 1:
        # show current
        update.message.reply_text(f"🤖 Current assistant model: `{get_current_model()}`\nUse `/assistant_model <name>` to change.", parse_mode="Markdown")
        return

    new_name = args[1].strip()
    # Optional basic sanity check
    if not new_name:
        update.message.reply_text("Usage: /assistant_model <model-name>")
        return

    set_current_model(new_name)
    update.message.reply_text(f"✅ Assistant model set to: `{new_name}`\n(Will auto-fallback to `gpt-4o` on errors.)", parse_mode="Markdown")


def cmd_assistant_toggle(update, context):
    """Toggle assistant failsafe ON/OFF"""
    from config import ASSISTANT_ADMIN_TELEGRAM_ID
    from assistant_dev_lite import audit_log
    
    uid = update.effective_user.id
    if uid != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Not authorized.")
        return
    
    args = update.message.text.split()
    if len(args) != 2:
        update.message.reply_text("Usage: /assistant_toggle ON|OFF")
        return
    
    mode = args[1].upper()
    if mode not in ["ON", "OFF"]:
        update.message.reply_text("Mode must be ON or OFF")
        return
    
    # Update environment variable (this affects runtime behavior)
    import os
    os.environ["ASSISTANT_FAILSAFE"] = mode
    
    status_msg = "🚫 DISABLED" if mode == "ON" else "✅ ENABLED"
    update.message.reply_text(f"🔧 Assistant failsafe: {status_msg}")
    
    audit_log(f"FAILSAFE_TOGGLE: user_id:{uid} set to {mode}")

def cmd_whoami(update, context):
    """Simple command to get user's Telegram ID and username"""
    uid = update.effective_user.id if update.effective_user else "unknown"
    uname = update.effective_user.username if update.effective_user else "unknown"
    update.message.reply_text(f"Your Telegram ID: {uid}\nUsername: @{uname}")

def log_update(update, context):
    """Log ANY update so we know the bot is receiving messages at all"""
    try:
        import logging
        logging.info("UPDATE: %s", update.to_dict())
    except Exception:
        pass

def cmd_rules_show(update, context):
    """Show current rules configuration"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Not authorized.")
        return
    
    try:
        from rules_loader import Rules
        rules = Rules()
        
        current_profile = rules.meta.get("default_profile", "conservative")
        profile_data = rules.profile()
        
        summary = f"""📋 **Rules Configuration**

**Version:** {rules.meta.get('version', 'unknown')}
**Active Profile:** {current_profile}

**Output Limits:**
• Top N: {rules.output.get('top_n', 10)}
• Min Score: {rules.output.get('min_score', 70)}

**Key Filters ({current_profile}):**
• Min Liquidity: ${profile_data.get('filters', {}).get('min_liquidity_usd', 0):,}
• Min Holders: {profile_data.get('filters', {}).get('min_holders', 0)}
• Max Dev Holdings: {profile_data.get('filters', {}).get('max_dev_holdings_pct', 0)}%
• Age Range: {profile_data.get('filters', {}).get('min_age_minutes', 0)}-{profile_data.get('filters', {}).get('max_age_minutes', 1440)} min

**Available Profiles:** {', '.join(rules.profiles.keys())}

Use /rules_profile <name> to switch profiles."""
        
        update.message.reply_text(summary, parse_mode='Markdown')
        
        from assistant_dev import audit_log
        audit_log(f"RULES_SHOW: user_id:{user_id}")
        
    except Exception as e:
        update.message.reply_text(f"❌ Error loading rules: {str(e)}")

def cmd_rules_profile(update, context):
    """Switch rules profile"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Not authorized.")
        return
    
    args = update.message.text.split(maxsplit=1)
    if len(args) != 2:
        update.message.reply_text("Usage: /rules_profile <conservative|degen>")
        return
    
    profile_name = args[1].strip().lower()
    
    try:
        from rules_loader import Rules
        rules = Rules()
        
        if profile_name in rules.profiles:
            rules.set_profile(profile_name)
            rules.save()
            update.message.reply_text(f"✅ Switched to {profile_name} profile")
            
            from assistant_dev import audit_log
            audit_log(f"RULES_PROFILE: user_id:{user_id} switched to {profile_name}")
        else:
            available = ', '.join(rules.profiles.keys())
            update.message.reply_text(f"❌ Profile '{profile_name}' not found. Available: {available}")
            
    except Exception as e:
        update.message.reply_text(f"❌ Error switching profile: {str(e)}")

def cmd_rules_set(update, context):
    """Update a rules value"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Not authorized.")
        return
    
    args = update.message.text.split(maxsplit=3)
    if len(args) != 4:
        update.message.reply_text("Usage: /rules_set <profile> <filter_key> <value>\nExample: /rules_set conservative min_liquidity_usd 50000")
        return
    
    _, profile_name, filter_key, value_str = args
    
    try:
        from rules_loader import Rules
        rules = Rules()
        
        # Parse value
        try:
            if value_str.lower() in ['true', 'false']:
                value = value_str.lower() == 'true'
            elif '.' in value_str:
                value = float(value_str)
            else:
                value = int(value_str)
        except ValueError:
            value = value_str  # Keep as string
        
        if rules.update_filter(profile_name, filter_key, value):
            rules.save()
            update.message.reply_text(f"✅ Updated {profile_name}.{filter_key} = {value}")
            
            from assistant_dev import audit_log
            audit_log(f"RULES_SET: user_id:{user_id} {profile_name}.{filter_key}={value}")
        else:
            update.message.reply_text(f"❌ Failed to update {profile_name}.{filter_key}")
            
    except Exception as e:
        update.message.reply_text(f"❌ Error updating rule: {str(e)}")

def cmd_rules_reload(update, context):
    """Reload rules from file"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Not authorized.")
        return
    
    try:
        from rules_loader import Rules
        rules = Rules()
        
        if rules.reload():
            profile = rules.meta.get("default_profile", "conservative")
            update.message.reply_text(f"✅ Rules reloaded successfully\nActive profile: {profile}")
            
            from assistant_dev import audit_log
            audit_log(f"RULES_RELOAD: user_id:{user_id}")
        else:
            update.message.reply_text("❌ Failed to reload rules")
            
    except Exception as e:
        update.message.reply_text(f"❌ Error reloading rules: {str(e)}")

def cmd_assistant_diff_old(update, context):
    """Legacy assistant_diff command handler (deprecated - use bot.py methods)"""
    user_id = update.effective_user.id
    
    # Strict admin-only access control
    if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Access denied. Admin privileges required.")
        from assistant_dev import audit_log
        audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
        return
    
    # Extract file path
    file_path = update.message.text.partition(" ")[2].strip()
    if not file_path:
        update.message.reply_text("Usage: /assistant_diff <file_path>")
        return
    
    # Get file content
    content = get_file_tail(file_path, 100)
    
    # Format for Telegram
    response = f"📄 **{file_path}** (last 100 lines):\n\n```\n{content}\n```"
    
    # Split long messages
    if len(response) > 4000:
        response = response[:3900] + "\n... (truncated)\n```"
    
    update.message.reply_text(response, parse_mode='Markdown')
    
    from assistant_dev import audit_log
    audit_log(f"FILE_INSPECT: user_id:{user_id} viewed {file_path}")

def cmd_assistant_approve(update, context):
    """Standalone assistant_approve command handler"""
    user_id = update.effective_user.id
    
    # Strict admin-only access control
    if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Access denied. Admin privileges required.")
        from assistant_dev import audit_log
        audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
        return
    
    if not ASSISTANT_GIT_BRANCH:
        update.message.reply_text("❌ Git staging not enabled. Set ASSISTANT_GIT_BRANCH environment variable.")
        return
    
    update.message.reply_text("🔄 Approving and merging staged changes...")
    
    # Merge the staging branch
    if git_approve_merge(ASSISTANT_GIT_BRANCH):
        update.message.reply_text(f"✅ Successfully merged branch `{ASSISTANT_GIT_BRANCH}` to main")
        from assistant_dev import audit_log
        audit_log(f"GIT_APPROVED: user_id:{user_id} merged branch {ASSISTANT_GIT_BRANCH}")
    else:
        update.message.reply_text(f"❌ Failed to merge branch `{ASSISTANT_GIT_BRANCH}`")
        from assistant_dev import audit_log  
        audit_log(f"GIT_APPROVE_FAILED: user_id:{user_id} could not merge {ASSISTANT_GIT_BRANCH}")

def cmd_assistant_backup(update, context):
    """Standalone backup command handler"""
    user_id = update.effective_user.id
    
    # Strict admin-only access control
    if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Access denied. Admin privileges required.")
        from assistant_dev import audit_log
        audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
        return
    
    command_args = update.message.text.split()
    
    if len(command_args) < 2:
        # List backups
        backups = list_backups(10)
        if not backups:
            update.message.reply_text("📦 No backups available")
            return
        
        backup_list = "\n".join(f"{i+1}. {backup}" for i, backup in enumerate(backups))
        update.message.reply_text(f"📦 **Available Backups:**\n\n```\n{backup_list}\n```\n\nUse: `/assistant_backup restore <name>`", parse_mode='Markdown')
        return
    
    action = command_args[1].lower()
    
    if action == "create":
        label = command_args[2] if len(command_args) > 2 else "manual"
        try:
            backup_name = create_backup(label)
            prune_backups(20)
            update.message.reply_text(f"✅ Created backup: `{backup_name}`", parse_mode='Markdown')
            from assistant_dev import audit_log
            audit_log(f"BACKUP_CREATE: user_id:{user_id} created {backup_name}")
        except Exception as e:
            update.message.reply_text(f"❌ Backup failed: {e}")
    
    elif action == "restore":
        if len(command_args) < 3:
            update.message.reply_text("Usage: `/assistant_backup restore <backup_name>`")
            return
        
        backup_name = command_args[2]
        try:
            update.message.reply_text("🔄 Restoring backup...")
            revert_to_backup(backup_name)
            update.message.reply_text(f"✅ Restored backup: `{backup_name}`", parse_mode='Markdown')
            from assistant_dev import audit_log
            audit_log(f"BACKUP_RESTORE: user_id:{user_id} restored {backup_name}")
        except Exception as e:
            update.message.reply_text(f"❌ Restore failed: {e}")
    
    else:
        update.message.reply_text("Usage:\n`/assistant_backup` - List backups\n`/assistant_backup create [label]` - Create backup\n`/assistant_backup restore <name>` - Restore backup", parse_mode='Markdown')

def cmd_assistant_backup_standalone(update, context):
    """Create manual backup - standalone function"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("Not authorized.")
        return
    label = "manual"
    try:
        name = create_backup(label)
        update.message.reply_text(f"✅ Backup created: {name}")
        from assistant_dev import audit_log
        audit_log(f"MANUAL_BACKUP: user_id:{user_id} created {name}")
    except Exception as e:
        update.message.reply_text(f"❌ Backup failed: {e}")

def cmd_assistant_list_backups(update, context):
    """List available backups"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("Not authorized.")
        return
    names = list_backups(30)
    if not names:
        update.message.reply_text("No backups yet.")
        return
    text = "🗂️ Latest backups (newest first):\n" + "\n".join(f"- {n}" for n in names)
    update.message.reply_text(text[:4000])

def cmd_assistant_revert(update, context):
    """Revert to backup"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("Not authorized.")
        return
    arg = update.message.text.split(maxsplit=1)
    target = None
    if len(arg) == 2:
        target = arg[1].strip()
    try:
        if not target or target == "latest":
            names = list_backups(1)
            if not names:
                update.message.reply_text("No backups available to restore.")
                return
            target = names[0]
        restored = revert_to_backup(target)
        update.message.reply_text(f"♻️ Restored backup: {restored}\nRestarting…")
        from assistant_dev import audit_log
        audit_log(f"BACKUP_REVERT: user_id:{user_id} restored {restored}")
        # Safe restart
        import os; os._exit(0)
    except Exception as e:
        update.message.reply_text(f"❌ Restore failed: {e}")

def cmd_assistant_diff(update, context):
    """Show file contents"""
    user_id = update.effective_user.id
    if user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("Not authorized.")
        return
    arg = update.message.text.split(maxsplit=1)
    if len(arg) != 2:
        update.message.reply_text("Usage: /assistant_diff <relative/path.py>")
        return
    path = arg[1].strip()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        # Telegram message limit safety
        MAX = 3500
        if len(data) > MAX:
            data = data[-MAX:]
            prefix = "(tail)\n"
        else:
            prefix = ""
        update.message.reply_text(f"📄 {path}\n{prefix}```\n{data}\n```", parse_mode="Markdown")
        from assistant_dev import audit_log
        audit_log(f"FILE_DIFF: user_id:{user_id} viewed {path}")
    except Exception as e:
        update.message.reply_text(f"❌ Could not read {path}: {e}")