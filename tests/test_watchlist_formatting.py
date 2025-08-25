import os, re, sys, multiprocessing as mp

# Ensure local imports work
sys.path.insert(0, os.getcwd())
import app

CHAT=-1002782542798; ADMIN=1653046781
SOL="So11111111111111111111111111111111111111112"

def _w(cmd,q):
    upd={"message":{"message_id":1,"date":0,"chat":{"id":CHAT,"type":"supergroup"},
                    "from":{"id":ADMIN,"is_bot":False,"username":"turk"},"text":cmd}}
    out=app.process_telegram_command(upd) or {}
    q.put(out.get("text") or out.get("response") or "")

def send(cmd,timeout=6):
    q=mp.Queue(); p=mp.Process(target=_w,args=(cmd,q),daemon=True)
    p.start(); p.join(timeout)
    if p.is_alive(): p.terminate(); p.join(1); return "__TIMEOUT__"
    return q.get() if not q.empty() else ""

def must(p, msg):
    print(("✅" if p else "❌"), msg)
    if not p: raise SystemExit(1)

ack = send("/watch_clear")
must(ack and "cleared" in ack.lower(), "watch_clear")

send(f"/watch {SOL}")
txt = send("/watchlist prices")
must("Watchlist" in txt, "has header")
# rows look like: NAME — Label  <value or ?>  `ShortMint`
row_re = re.compile(r"^[^\n`]+—[^\n`]+?\s+(?:\$\d[\d,]*\.\d{2}|\?)\s+`[^`]+`$", re.MULTILINE)
must(bool(row_re.search(txt)), "row format: name — label  value/?  `mint`")

print("PASS")