"""
Telegram Alert Handlers for Mork F.E.T.C.H Bot
Standalone command functions for easy integration
"""

from config import ASSISTANT_ADMIN_TELEGRAM_ID, ASSISTANT_GIT_BRANCH  
from assistant_dev import assistant_codegen, apply_unified_diffs, maybe_run_commands, safe_restart_if_needed, get_file_tail, git_approve_merge, revert_to_backup
from backup_manager import create_backup, list_backups, restore_backup, prune_backups

def cmd_assistant(update, context):
    """Standalone assistant command handler for dispatcher integration"""
    user_id = update.effective_user.id
    
    # Strict admin-only access control
    if not ASSISTANT_ADMIN_TELEGRAM_ID or user_id != ASSISTANT_ADMIN_TELEGRAM_ID:
        update.message.reply_text("❌ Access denied. Admin privileges required.")
        from assistant_dev import audit_log
        audit_log(f"ACCESS_DENIED: user_id:{user_id} (admin:{ASSISTANT_ADMIN_TELEGRAM_ID})")
        return
    
    # Check failsafe toggle
    from config import ASSISTANT_FAILSAFE
    if ASSISTANT_FAILSAFE == "ON":
        update.message.reply_text("🚫 Assistant patching is currently DISABLED via failsafe toggle.")
        return

    request_text = update.message.text.partition(" ")[2].strip()
    if not request_text:
        update.message.reply_text("Usage: /assistant <what you want changed>")
        return

    update.message.reply_text("🤖 Thinking… generating patch.")
    result = assistant_codegen(request_text, user_id)
    plan = result.get("plan","(no plan)")
    diffs = result.get("diffs", [])
    commands = result.get("commands", [])
    restart = result.get("restart", "none")

    # Apply diffs
    apply_res = apply_unified_diffs(diffs)

    # Extract backup info from stdout if present
    backup_name = None
    if "Created backup:" in apply_res.stdout:
        for line in apply_res.stdout.split("\n"):
            if "Created backup:" in line:
                backup_name = line.replace("Created backup:", "").strip()
                break

    # Maybe run commands
    cmd_out = maybe_run_commands(commands)
    
    # Log the execution results
    from assistant_dev import audit_log
    audit_log(f"EXECUTION: user_id:{user_id} applied:{len(apply_res.applied_files)} failed:{len(apply_res.failed_files)} commands:{len(commands)} restart:{restart}")
    
    # Log backup if created
    if backup_name:
        audit_log(f"ASSISTANT_BACKUP: user_id:{user_id} auto-backup {backup_name}")
    
    # Handle oversized diffs with helpful message
    if any("exceeds" in f for f in apply_res.failed_files):
        update.message.reply_text("⚠️ **Size Limit Exceeded**\n\nSome diffs were too large (>50KB per diff, max 2 diffs). Please break your request into smaller, more focused changes.")

    # Summarize
    summary = [
        "✅ Plan:\n" + plan,
        f"✍️ Write mode: {'ON' if not apply_res.dry_run else 'DRY-RUN (no files written)'}",
        f"📝 Applied: {len(apply_res.applied_files)} files",
        (("❌ Failed: " + ", ".join(apply_res.failed_files)) if apply_res.failed_files else "❌ Failed: none"),
        (f"🔧 Commands run:\n{cmd_out[:1500]}..." if cmd_out else "🔧 Commands: none"),
        f"♻️ Restart: {restart}",
    ]
    
    # Add backup information to summary
    if backup_name:
        summary.append(f"💾 Backup: {backup_name}")
    elif apply_res.dry_run:
        from config import ASSISTANT_WRITE_GUARD
        if ASSISTANT_WRITE_GUARD.upper() == "OFF":
            summary.append("🧪 Dry-run only. No backup created. Toggle ASSISTANT_WRITE_GUARD=ON to write & auto-backup.")
    
    update.message.reply_text("\n\n".join(summary)[:4000])

    # Optional preview of first diff
    if diffs:
        preview = diffs[0]
        update.message.reply_text("Diff preview (first patch):\n\n" + preview[:3500])

    # Restart if requested
    safe_restart_if_needed(restart)

def cmd_assistant_diff(update, context):
    """Standalone assistant_diff command handler"""
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