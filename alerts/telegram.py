"""
Telegram Alert Handlers for Mork F.E.T.C.H Bot
Standalone command functions for easy integration
"""

from config import ASSISTANT_ADMIN_TELEGRAM_ID
from assistant_dev import assistant_codegen, apply_unified_diffs, maybe_run_commands, safe_restart_if_needed

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