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

    # Maybe run commands
    cmd_out = maybe_run_commands(commands)
    
    # Log the execution results
    from assistant_dev import audit_log
    audit_log(f"EXECUTION: user_id:{user_id} applied:{len(apply_res.applied_files)} failed:{len(apply_res.failed_files)} commands:{len(commands)} restart:{restart}")
    
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