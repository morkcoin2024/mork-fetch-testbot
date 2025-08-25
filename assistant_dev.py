# assistant_dev.py
import logging
import os
import pathlib
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from unidiff import PatchSet

from backup_manager import create_backup, prune_backups, restore_backup
from config import ASSISTANT_GIT_BRANCH, ASSISTANT_MODEL, ASSISTANT_WRITE_GUARD, OPENAI_API_KEY

# Where we persist the chosen model across restarts
_PERSIST_PATH = Path(".assistant_model")


def get_current_model() -> str:
    """
    Returns the currently selected assistant model.
    Priority: persisted file -> env ASSISTANT_MODEL -> default.
    """
    try:
        if _PERSIST_PATH.exists():
            name = _PERSIST_PATH.read_text(encoding="utf-8").strip()
            if name:
                return name
    except Exception as e:
        logging.warning("get_current_model: read persist failed: %s", e)

    # Fallback to env or sensible default
    return os.environ.get("ASSISTANT_MODEL", "gpt-4o")


def set_current_model(name: str) -> str:
    """
    Sets and persists the assistant model. Also updates the process env
    so the running app immediately uses it without restart.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Model name cannot be empty")

    os.environ["ASSISTANT_MODEL"] = name  # live for this process
    try:
        _PERSIST_PATH.write_text(name, encoding="utf-8")
    except Exception as e:
        logging.warning("set_current_model: write persist failed: %s", e)

    logging.info("[ADMIN] Assistant model persisted to %s", name)
    return name


# Safety limits
MAX_DIFFS = 2
MAX_DIFF_BYTES = 50_000

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

ASSISTANT_SYSTEM_PROMPT = """You are the in-repo developer assistant for the Mork fetch bot running on Replit.
- Output ONLY JSON with keys: "plan", "diffs", "commands", "restart".
- "diffs" must be a list of unified diffs (git-style) that apply cleanly to the current working directory.
- Keep changes minimal and cohesive. Include new files via unified diff with proper headers.
- If migrations/installs needed, put shell commands in "commands".
- Set "restart" to "safe" if a restart is recommended, otherwise "none".
- Never include secrets. Always produce valid unified diff format.
"""


def assistant_codegen(user_request: str, user_id: int = 0) -> dict:
    if not client:
        audit_log(f"ERROR: OpenAI API key not configured - user_id:{user_id}")
        return {
            "plan": "OpenAI API key not configured",
            "diffs": [],
            "commands": [],
            "restart": "none",
        }

    audit_log(f"REQUEST: user_id:{user_id} - {user_request[:100]}")

    prompt = f"""User request for repository update:

{user_request}

Environment:
- Python project on Replit
- Telegram bot + Flask (webhooks)
- Goal: modify files directly via unified diffs.

Return JSON with keys plan/diffs/commands/restart as specified."""
    resp = client.chat.completions.create(
        model=ASSISTANT_MODEL,
        messages=[
            {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    import json

    content = resp.choices[0].message.content
    try:
        data = json.loads(content or "{}")
        audit_log(
            f"RESPONSE: plan='{data.get('plan', '')[:50]}...' diffs={len(data.get('diffs', []))} commands={len(data.get('commands', []))} restart={data.get('restart', 'none')}"
        )
    except Exception as e:
        audit_log(f"ERROR: Failed to parse OpenAI response - {e}")
        data = {
            "plan": "(failed to parse)",
            "diffs": [],
            "commands": [],
            "restart": "none",
            "raw": content,
        }
    return data


@dataclass
class ApplyResult:
    applied_files: list[str]
    failed_files: list[str]
    dry_run: bool
    stdout: str


def apply_unified_diffs(diffs: list[str]) -> ApplyResult:
    applied, failed = [], []
    dry_run = ASSISTANT_WRITE_GUARD.upper() != "ON"
    staging_mode = bool(ASSISTANT_GIT_BRANCH and not dry_run)
    stdout_lines = []

    # Apply safety limits
    if len(diffs) > MAX_DIFFS:
        audit_log(f"LIMIT_HIT: Truncated {len(diffs)} diffs to {MAX_DIFFS}")
        diffs = diffs[:MAX_DIFFS]

    # Check diff sizes and filter out oversized ones
    filtered_diffs = []
    for i, diff in enumerate(diffs):
        size = len(diff.encode("utf-8"))
        if size > MAX_DIFF_BYTES:
            failed.append(f"diff[{i}] size {size} bytes exceeds {MAX_DIFF_BYTES} limit")
            audit_log(f"LIMIT_HIT: Diff {i} size {size} bytes exceeds limit")
        else:
            filtered_diffs.append(diff)

    diffs = filtered_diffs

    # Create backup before writing any files (only in live mode with diffs)
    backup_created = False
    if ASSISTANT_WRITE_GUARD.upper() == "ON" and diffs:
        backup_name = create_backup("prepatch")
        stdout_lines.append(f"Created backup: {backup_name}")
        prune_backups(20)
        backup_created = True

    for idx, diff in enumerate(diffs):
        try:
            patch = PatchSet(diff.splitlines(True))
        except Exception as e:
            failed.append(f"diff[{idx}] parse error: {e}")
            continue
        for patched_file in patch:
            target = patched_file.target_file
            # Handle "a/..." "b/..." headers:
            if target.startswith("b/"):
                target = target[2:]
            path = pathlib.Path(target)
            # Ensure directories exist
            if not dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
            # Read original
            original = ""
            if path.exists():
                original = path.read_text(encoding="utf-8")
            # Apply hunks manually (simple approach)
            new_content = _apply_single_file_patch(original, patched_file)
            if new_content is None:
                failed.append(str(path))
            else:
                applied.append(str(path))
                if not dry_run:
                    path.write_text(new_content, encoding="utf-8")

    # Handle Git staging if enabled
    if staging_mode and applied:
        if git_stage_changes(applied, ASSISTANT_GIT_BRANCH):
            stdout_lines.append(f"staged {len(applied)} files on branch {ASSISTANT_GIT_BRANCH}")
        else:
            stdout_lines.append("failed to stage changes on Git branch")

    return ApplyResult(applied, failed, dry_run, "\n".join(stdout_lines))


def _apply_single_file_patch(original_text: str, patched_file) -> str | None:
    # Minimal in-memory unified patch apply (no external 'patch' binary)
    # We rely on the hunks' target lines to reconstruct file
    # If complexity is high, return None to fail safe.
    try:
        lines = original_text.splitlines(True)
        out = []
        cursor = 0
        for hunk in patched_file:
            # Copy unchanged prefix
            src_start = hunk.source_start - 1
            out.extend(lines[cursor:src_start])
            cursor = hunk.source_start - 1 + hunk.source_length
            # Apply hunk:
            for line in hunk:
                text = line.value
                if line.is_added or line.is_context:
                    out.append(text)
                # removed lines are skipped
        out.extend(lines[cursor:])
        return "".join(out)
    except Exception:
        return None


def maybe_run_commands(cmds: list[str]) -> str:
    if not cmds:
        return ""
    if ASSISTANT_WRITE_GUARD.upper() != "ON":
        return "(dry-run) would run:\n" + "\n".join(cmds)
    out = []
    for c in cmds:
        audit_log(f"COMMAND_EXEC: {c}")
        proc = subprocess.run(c, shell=True, capture_output=True, text=True, check=False)
        out.append(f"$ {c}\n{proc.stdout}\n{proc.stderr}")
    return "\n".join(out)


def audit_log(entry: str):
    """Log assistant actions to audit file"""
    try:
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("logs/assistant_audit.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {entry}\n")
    except Exception as e:
        print(f"Audit log error: {e}")


def git_stage_changes(files: list[str], branch: str) -> bool:
    """Stage changes on specified Git branch"""
    try:
        # Check if git is available and we're in a repo
        proc = subprocess.run(["git", "status"], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            audit_log("GIT_ERROR: Not in a git repository")
            return False

        # Create and checkout branch if it doesn't exist
        subprocess.run(["git", "checkout", "-b", branch], capture_output=True, check=False)
        if (
            subprocess.run(["git", "checkout", branch], capture_output=True, check=False).returncode
            != 0
        ):
            audit_log(f"GIT_ERROR: Could not checkout branch {branch}")
            return False

        # Stage the files
        for file_path in files:
            subprocess.run(["git", "add", file_path], capture_output=True, check=False)

        # Commit changes
        commit_msg = "Assistant: staged changes for review"
        proc = subprocess.run(
            ["git", "commit", "-m", commit_msg], capture_output=True, text=True, check=False
        )

        if proc.returncode == 0:
            audit_log(f"GIT_STAGED: {len(files)} files staged on branch {branch}")
            return True
        else:
            audit_log(f"GIT_ERROR: Commit failed - {proc.stderr}")
            return False

    except Exception as e:
        audit_log(f"GIT_ERROR: {e}")
        return False


def git_approve_merge(branch: str) -> bool:
    """Merge staging branch to main"""
    try:
        # Switch to main and merge
        subprocess.run(["git", "checkout", "main"], capture_output=True, check=False)
        proc = subprocess.run(["git", "merge", branch], capture_output=True, text=True, check=False)

        if proc.returncode == 0:
            # Clean up branch
            subprocess.run(["git", "branch", "-d", branch], capture_output=True, check=False)
            audit_log(f"GIT_MERGED: Branch {branch} merged and deleted")
            return True
        else:
            audit_log(f"GIT_MERGE_ERROR: {proc.stderr}")
            return False

    except Exception as e:
        audit_log(f"GIT_MERGE_ERROR: {e}")
        return False


def get_file_tail(file_path: str, lines: int = 100) -> str:
    """Get last N lines of a file for inspection"""
    try:
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"

        with open(file_path, encoding="utf-8") as f:
            all_lines = f.readlines()

        if len(all_lines) <= lines:
            content = "".join(all_lines)
        else:
            content = "".join(all_lines[-lines:])
            content = f"... (showing last {lines} lines)\n" + content

        return content[:3000]  # Limit for Telegram

    except Exception as e:
        return f"Error reading file: {e}"


def revert_to_backup(name: str) -> str:
    return restore_backup(name)


def safe_restart_if_needed(mode: str):
    if mode != "safe":
        return
    # In Replit Reserved VM, the supervisor will restart the process when it exits.
    os._exit(0)
