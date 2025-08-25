# assistant_dev.py

import json
import os
import pathlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from unidiff import PatchSet

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PERSIST_PATH = Path(".assistant_model")  # simple local persistence between restarts
DEFAULT_MODEL = os.getenv("ASSISTANT_MODEL", "gpt-5-thinking")
FALLBACK_MODEL = "gpt-4o"


def _load_model_name() -> str:
    try:
        if PERSIST_PATH.exists():
            name = PERSIST_PATH.read_text(encoding="utf-8").strip()
            if name:
                return name
    except Exception:
        pass
    return DEFAULT_MODEL


def _save_model_name(name: str):
    PERSIST_PATH.write_text(name.strip(), encoding="utf-8")


def get_current_model() -> str:
    return _load_model_name()


def set_current_model(name: str) -> str:
    name = name.strip()
    _save_model_name(name)
    return name


ASSISTANT_WRITE_GUARD = os.getenv("ASSISTANT_WRITE_GUARD", "OFF").upper()

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM = """You are the in-repo dev assistant for the Mork fetch bot on Replit.
Return ONLY valid JSON with keys: plan (str), diffs (list[str]), commands (list[str]), restart ("safe"|"none").
Diffs must be unified diffs (git-style) that apply cleanly to current working directory. Keep changes minimal. No secrets.
"""


def assistant_codegen(user_request: str) -> dict:
    import logging

    model = get_current_model()  # <— dynamic
    msg = f"User request:\n{user_request}\nProject: Python Telegram bot + Flask on Replit."
    try:
        r = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
        )
    except Exception as e:
        logging.warning(f"Assistant model {model} failed: {e}")
        logging.warning(f"Falling back to {FALLBACK_MODEL}")
        r = client.chat.completions.create(
            model=FALLBACK_MODEL,
            temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
        )
    content = r.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except Exception:
        return {
            "plan": "parse_error",
            "diffs": [],
            "commands": [],
            "restart": "none",
            "raw": content,
        }


@dataclass
class ApplyResult:
    applied_files: list[str]
    failed_files: list[str]
    dry_run: bool
    notes: str


def _apply_single_file_patch(original_text: str, patched_file) -> str | None:
    try:
        lines = original_text.splitlines(True)
        out, cursor = [], 0
        for hunk in patched_file:
            src_start = hunk.source_start - 1
            out.extend(lines[cursor:src_start])
            cursor = src_start + hunk.source_length
            for line in hunk:
                if line.is_added or line.is_context:
                    out.append(line.value)
        out.extend(lines[cursor:])
        return "".join(out)
    except Exception:
        return None


def apply_unified_diffs(diffs: list[str]) -> ApplyResult:
    MAX_DIFFS, MAX_BYTES = 2, 50_000
    diffs = [d for d in diffs[:MAX_DIFFS] if len(d.encode("utf-8")) <= MAX_BYTES]
    applied, failed = [], []
    dry = ASSISTANT_WRITE_GUARD != "ON"
    notes = []

    for idx, diff in enumerate(diffs):
        try:
            patch = PatchSet(diff.splitlines(True))
        except Exception as e:
            failed.append(f"diff[{idx}] parse error: {e}")
            continue

        for pf in patch:
            target = pf.target_file[2:] if pf.target_file.startswith("b/") else pf.target_file
            path = pathlib.Path(target)
            original = path.read_text(encoding="utf-8") if path.exists() else ""
            new_text = _apply_single_file_patch(original, pf)

            if new_text is None:
                failed.append(target)
                continue

            applied.append(target)

            if not dry:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new_text, encoding="utf-8")
                notes.append(f"wrote {target}")
            else:
                notes.append(f"would write {target}")

    return ApplyResult(applied, failed, dry, "; ".join(notes))


def maybe_run_commands(commands: list[str]) -> str:
    if ASSISTANT_WRITE_GUARD != "ON":
        return f"dry-run: would run {len(commands)} commands"

    results = []
    for cmd in commands[:3]:  # Max 3 commands
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30, check=False
            )
            results.append(f"{cmd}: exit={result.returncode}")
        except Exception as e:
            results.append(f"{cmd}: error={e}")

    return "; ".join(results)


def safe_restart_if_needed(restart: str):
    if restart == "safe" and ASSISTANT_WRITE_GUARD == "ON":
        # Signal restart needed (in production this would trigger a restart)
        with open("restart_needed.flag", "w") as f:
            f.write("assistant requested restart")


def audit_log(message: str):
    """Simple audit logging"""
    log_dir = pathlib.Path("logs")
    log_dir.mkdir(exist_ok=True)

    with open(log_dir / "assistant_audit.log", "a") as f:
        import datetime

        timestamp = datetime.datetime.now().isoformat()
        f.write(f"{timestamp}: {message}\n")
