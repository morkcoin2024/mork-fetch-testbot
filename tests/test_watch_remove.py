import os, re, sys, multiprocessing as mp

# ensure we can import app.py from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app  # noqa: E402

CHAT = -1002782542798
ADMIN = 1653046781

SOL_L = "So11111111111111111111111111111111111111112"
UNK_L = "So11111111111111111111111111111111111111113"
SOL_S = "So1111…111112"
UNK_S = "So1111…111113"

REMOVE_CANDIDATES = [
    os.getenv("WATCH_REMOVE_CMD", "/watch_remove"),
    "/unwatch",
]

TIMEOUT = float(os.getenv("TEST_TIMEOUT", "8"))
STRICT  = os.getenv("STRICT", "0") == "1"

USD2 = re.compile(r"\$\d[\d,]*\.\d{2}(?!\d)")
QTY2 = re.compile(r"\b\d[\d,]*\.\d{2}(?!\d)\b")
INTC = re.compile(r"\b\d[\d,]*\b")

def _worker(cmd, q):
    upd = {"message":{"message_id":1,"date":0,"chat":{"id":CHAT,"type":"supergroup"},
                      "from":{"id":ADMIN,"is_bot":False,"username":"turk"},"text":cmd}}
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

def row_for(s, needle):
    m = re.search(rf"(?:^|\n)([^\n]*`{re.escape(needle)}`[^\n]*)", s)
    if m: return m.group(1).strip()
    m2 = re.search(rf"(?:^|\n)([^\n]*{re.escape(needle.split('…')[0])}…[^\n]*)", s)
    return m2.group(1).strip() if m2 else ""

def value_ok(mode, row):
    if not row: return False
    if " ?  `" in row:
        return not STRICT
    if mode in ("prices","caps","fdv","volumes"): return bool(USD2.search(row))
    if mode == "supply": return bool(QTY2.search(row))
    if mode == "holders": return bool(INTC.search(row))
    return False

def rows_count(resp):
    return sum(1 for ln in resp.splitlines() if " `" in ln and "—" in ln)

def try_remove(mint_full):
    last = ""
    for cmd in REMOVE_CANDIDATES:
        out = send(f"{cmd} {mint_full}")
        last = out
        if out and ("Removed" in out or "Watchlist" in out):
            return cmd, out
    return REMOVE_CANDIDATES[-1], last

def ck(passed, msg):
    print(("✅" if passed else "❌"), msg)
    return 0 if passed else 1

fails = 0

ack = send("/watch_clear")
fails += ck(bool(ack) and "cleared" in ack.lower(), "watch_clear")

send(f"/watch {SOL_L}")
send(f"/watch {UNK_L}")

resp = send("/watchlist prices")
fails += ck(bool(resp) and "Watchlist" in resp, "list present")
sol_row = row_for(resp, SOL_S)
unk_row = row_for(resp, UNK_S)
fails += ck(bool(sol_row), "SOL row present")
fails += ck(bool(unk_row), "UNK row present")
fails += ck(value_ok("prices", sol_row), "SOL has value")

before_n = rows_count(resp)
cmd_used, _ = try_remove(UNK_L)
resp2 = send("/watchlist prices")
after_n = rows_count(resp2)

fails += ck(UNK_S not in resp2, f"UNK removed via {cmd_used}")
fails += ck(after_n == max(0, before_n-1), "row count decremented")
fails += ck(SOL_S in resp2, "SOL still present")

_ = try_remove(UNK_L)
resp3 = send("/watchlist prices")
fails += ck(SOL_S in resp3 and UNK_S not in resp3, "idempotent remove safe")

_ = try_remove(SOL_L)
resp4 = send("/watchlist prices")
empty_header = bool(resp4) and "Watchlist" in resp4
empty_rows = rows_count(resp4) == 0
fails += ck(empty_header, "empty header after last remove")
fails += ck(empty_rows, "empty rows after last remove")

print("\nPASS" if fails == 0 else f"FAIL({fails})")
sys.exit(0 if fails == 0 else 1)
