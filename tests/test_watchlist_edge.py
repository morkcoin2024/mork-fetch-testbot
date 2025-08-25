# tests/test_watchlist_edge.py

import multiprocessing as mp
import os
import sys

# Ensure we can "import app" when running from tests/
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import app  # noqa: E402

CHAT = -1002782542798
ADMIN = 1653046781

SOL_L = "So11111111111111111111111111111111111111112"
SOL_S = "So1111…111112"

TIMEOUT = float(os.getenv("TEST_TIMEOUT", "6"))


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
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(1)
        return "__TIMEOUT__"
    return q.get() if not q.empty() else ""


def data_rows(s):
    return [ln for ln in s.splitlines() if " `" in ln and "—" in ln]


def header_line(s):
    return s.splitlines()[0] if s else ""


def ck(ok, msg):
    print(("✅" if ok else "❌"), msg)
    return 0 if ok else 1


def main():
    fails = 0

    # 1) watch_clear idempotent
    ack1 = send("/watch_clear")
    fails += ck(bool(ack1) and "cleared" in ack1.lower(), "watch_clear #1")
    ack2 = send("/watch_clear")
    fails += ck(bool(ack2) and "cleared" in ack2.lower(), "watch_clear #2 (idempotent)")

    # 2) Empty watchlist -> headers render; zero data rows for each mode
    for mode in ["supply", "fdv", "holders", "prices", "caps", "volumes"]:
        resp = send(f"/watchlist {mode}")
        ok_header = bool(resp) and "Watchlist" in resp
        ok_empty = len(data_rows(resp)) == 0
        fails += ck(ok_header, f"empty header {mode}")
        fails += ck(ok_empty, f"empty rows {mode}")

    # 3) Sorting while empty: expect valid headers and still zero rows
    resp = send("/watchlist volumes desc")
    fails += ck(bool(resp) and "Watchlist" in resp, "sort volumes desc (empty header)")
    fails += ck(len(data_rows(resp)) == 0, "sort volumes desc (empty rows)")

    resp = send("/watchlist supply asc")
    fails += ck(bool(resp) and "Watchlist" in resp, "sort supply asc (empty header)")
    fails += ck(len(data_rows(resp)) == 0, "sort supply asc (empty rows)")

    # 4) Add a token twice; ensure row present and short mint shows up
    send(f"/watch {SOL_L}")
    send(f"/watch {SOL_L}")  # duplicate on purpose
    resp = send("/watchlist prices")
    present = (SOL_S in resp) or (SOL_L in resp)
    fails += ck(present, "present after duplicate /watch")
    fails += ck(len(data_rows(resp)) >= 1, "has >=1 data row after add")

    # 5) Now that list has rows, sorting headers should include marker tags
    resp = send("/watchlist volumes desc")
    fails += ck("(desc)" in header_line(resp), "sort volumes desc (non-empty)")
    resp = send("/watchlist supply asc")
    fails += ck("(asc)" in header_line(resp), "sort supply asc (non-empty)")

    print("\nPASS" if fails == 0 else f"FAIL({fails})")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
