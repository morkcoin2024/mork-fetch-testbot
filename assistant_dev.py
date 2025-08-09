# assistant_dev.py
import os, subprocess, textwrap, tempfile, pathlib
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from unidiff import PatchSet
from openai import OpenAI
from config import OPENAI_API_KEY, ASSISTANT_MODEL, ASSISTANT_WRITE_GUARD

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
        return {"plan":"OpenAI API key not configured", "diffs":[], "commands":[], "restart":"none"}
    
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
            {"role":"system","content":ASSISTANT_SYSTEM_PROMPT},
            {"role":"user","content":prompt},
        ],
        temperature=0.2,
    )
    import json
    content = resp.choices[0].message.content
    try:
        data = json.loads(content or "{}")
        audit_log(f"RESPONSE: plan='{data.get('plan', '')[:50]}...' diffs={len(data.get('diffs', []))} commands={len(data.get('commands', []))} restart={data.get('restart', 'none')}")
    except Exception as e:
        audit_log(f"ERROR: Failed to parse OpenAI response - {e}")
        data = {"plan":"(failed to parse)", "diffs":[], "commands":[], "restart":"none", "raw":content}
    return data

@dataclass
class ApplyResult:
    applied_files: List[str]
    failed_files: List[str]
    dry_run: bool
    stdout: str

def apply_unified_diffs(diffs: List[str]) -> ApplyResult:
    applied, failed = [], []
    dry_run = (ASSISTANT_WRITE_GUARD.upper() != "ON")
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

    for idx, diff in enumerate(diffs):
        try:
            patch = PatchSet(diff.splitlines(True))
        except Exception as e:
            failed.append(f"diff[{idx}] parse error: {e}")
            continue
        for patched_file in patch:
            target = patched_file.target_file
            # Handle "a/..." "b/..." headers:
            if target.startswith("b/"): target = target[2:]
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
    return ApplyResult(applied, failed, dry_run, "\n".join(stdout_lines))

def _apply_single_file_patch(original_text: str, patched_file) -> Optional[str]:
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
                if line.is_added:
                    out.append(text)
                elif line.is_context:
                    out.append(text)
                # removed lines are skipped
        out.extend(lines[cursor:])
        return "".join(out)
    except Exception:
        return None

def maybe_run_commands(cmds: List[str]) -> str:
    if not cmds:
        return ""
    if ASSISTANT_WRITE_GUARD.upper() != "ON":
        return "(dry-run) would run:\n" + "\n".join(cmds)
    out = []
    for c in cmds:
        audit_log(f"COMMAND_EXEC: {c}")
        proc = subprocess.run(c, shell=True, capture_output=True, text=True)
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

def safe_restart_if_needed(mode: str):
    if mode != "safe":
        return
    # In Replit Reserved VM, the supervisor will restart the process when it exits.
    os._exit(0)