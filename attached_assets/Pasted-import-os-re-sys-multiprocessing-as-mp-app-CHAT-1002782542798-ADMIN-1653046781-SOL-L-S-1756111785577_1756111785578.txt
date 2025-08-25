import os, re, sys, multiprocessing as mp, app

CHAT = -1002782542798
ADMIN = 1653046781

SOL_L = "So11111111111111111111111111111111111111112"
UNK_L = "So11111111111111111111111111111111111111113"
def short_mint(m): return m[:6] + "…" + m[-6:]
SOL_S, UNK_S = short_mint(SOL_L), short_mint(UNK_L)

TIMEOUT = float(os.getenv("TEST_TIMEOUT", "10"))

def _worker(cmd, q):
    upd = {"message": {"message_id": 1, "date": 0,
                       "chat": {"id": CHAT, "type": "supergroup"},
                       "from": {"id": ADMIN, "is_bot": False, "username": "turk"},
                       "text": cmd}}
    out = app.process_telegram_command(upd) or {}
    q.put(out.get("text") or out.get("response") or "")

def _do_send(cmd, timeout=TIMEOUT):
    q = mp.Queue()
    p = mp.Process(target=_worker, args=(cmd, q), daemon=True)
    p.start(); p.join(timeout)
    if p.is_alive():
        p.terminate(); p.join(1)
        return "__TIMEOUT__"
    return q.get() if not q.empty() else ""

def send(cmd, timeout=TIMEOUT):
    r = _do_send(cmd, timeout)
    return r if r != "__TIMEOUT__" else _do_send(cmd, timeout)

def rows(resp): return [ln for ln in resp.splitlines() if " `" in ln and "—" in ln]

def ck(ok, msg):
    print(("✅" if ok else "❌"), msg)
    return 0 if ok else 1

fails = 0

# 1) clean
ack = send("/watch_clear")
fails += ck(bool(ack) and "cleared" in ack.lower(), "watch_clear")

# 2) seed many
send(f"/watch {SOL_L}")
send(f"/watch {UNK_L}")

# fabricate additional unique unknown mints by varying last char
SUFFIXES = list("3456789ABCDEFGHJKMNPRSTUVWXYZ")  # avoid ambiguous chars
EXTRA = [UNK_L[:-1] + s for s in SUFFIXES[:18]]   # cap to keep runtime modest

for m in EXTRA: send(f"/watch {m}")

# 3) sanity: prices view contains all shorts
resp = send("/watchlist prices")
fails += ck(bool(resp) and "Watchlist" in resp, "list header")
R = rows(resp)
fails += ck(len(R) >= 10, "has many rows")

shorts = {short_mint(x) for x in ([SOL_L, UNK_L] + EXTRA)}
missing = [s for s in shorts if f"`{s}`" not in resp]
fails += ck(not missing, f"all added mints present ({len(shorts)} total)")

# 4) sorting stability (set equality preserved)
resp_desc = send("/watchlist prices desc")
resp_asc  = send("/watchlist prices asc")
set_desc = {ln.split("`")[-2] for ln in rows(resp_desc)}  # grab short mint in backticks
set_asc  = {ln.split("`")[-2] for ln in rows(resp_asc)}
fails += ck(set_desc == set_asc == shorts, "sorting preserves set of items")

print("\nPASS" if fails == 0 else f"FAIL({fails})")
sys.exit(0 if fails == 0 else 1)