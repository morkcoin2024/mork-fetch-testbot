import os, re, sys, multiprocessing as mp

# Ensure local imports work
sys.path.insert(0, os.getcwd())
import app  # noqa: E402

CHAT = -1002782542798
ADMIN = 1653046781

SOL = "So11111111111111111111111111111111111111112"
TIMEOUT = float(os.getenv("TEST_TIMEOUT", "8"))

def _worker(cmd, q):
    upd = {
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": CHAT, "type": "supergroup"},
            "from": {"id": ADMIN, "is_bot": False, "username": "turk"},
            "text": cmd,
        }
    }
    out = app.process_telegram_command(upd) or {}
    q.put(out.get("text") or out.get("response") or "")

def send(cmd, timeout=TIMEOUT):
    q = mp.Queue()
    p = mp.Process(target=_worker, args=(cmd, q), daemon=True)
    p.start(); p.join(timeout)
    if p.is_alive():
        p.terminate(); p.join(1)
        return "__TIMEOUT__"
    return q.get() if not q.empty() else ""

def shortify(addr: str) -> str:
    # Matches UI: first 6 + ellipsis + last 6
    return addr[:6] + "…" + addr[-6:]

def mint_list(n_unknown=19):
    # Build: [SOL] + N neighbors by tweaking the final character(s).
    # Note: Short forms can collide once we append multi-digit suffixes.
    base = SOL[:-1]
    mints = [SOL] + [base + str(i) for i in range(3, 3 + n_unknown)]
    return mints

SHORT_MINT_RE = re.compile(r"`([A-Za-z0-9]{6}…[A-Za-z0-9]{6})`")

def minted_set(resp: str):
    # Only count backticked short-mints, ignore backticked tips/commands.
    return set(SHORT_MINT_RE.findall(resp or ""))

def rows(s: str):
    return [ln for ln in (s or "").splitlines() if " `" in ln and "—" in ln]

def ck(ok, msg):
    print(("✅" if ok else "❌"), msg)
    return 0 if ok else 1

fails = 0

# 1) clear
ack = send("/watch_clear")
fails += ck(bool(ack) and "cleared" in ack.lower(), "watch_clear")

# 2) add many
mints = mint_list(19)
for m in mints:
    send(f"/watch {m}")

resp = send("/watchlist prices")
init_set = minted_set(resp)
expected_shorts = set(shortify(m) for m in mints)  # account for collisions
fails += ck("Watchlist" in resp, "list header")
fails += ck(len(rows(resp)) >= 1, "has many rows")
fails += ck(expected_shorts.issubset(init_set), f"all added mints present ({len(init_set)} seen)")

# 3) sorting preserves *the token set*, ignoring tips
resp_desc = send("/watchlist prices desc")
resp_asc = send("/watchlist prices asc")
set_desc = minted_set(resp_desc)
set_asc = minted_set(resp_asc)
fails += ck(init_set == set_desc == set_asc, "sorting preserves set of items")

# 4) re-adding everything does not duplicate
for m in mints:
    send(f"/watch {m}")
resp2 = send("/watchlist prices")
fails += ck(minted_set(resp2) == init_set, "idempotent re-add keeps same set")

print("\nPASS" if fails == 0 else f"FAIL({fails})")
sys.exit(0 if fails == 0 else 1)
