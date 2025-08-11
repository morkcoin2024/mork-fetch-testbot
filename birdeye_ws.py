# --- BEGIN FILE: birdeye_ws.py ---
import os, json, time, threading, logging, re
from collections import deque

try:
    import websocket  # from websocket-client
except Exception as e:
    websocket = None
    logging.warning("[WS] websocket-client not available: %s", e)

BIRDEYE_KEY   = os.getenv("BIRDEYE_API_KEY", "")
BIRDEYE_WS_URL = os.getenv("BIRDEYE_WS_URL", "")  # e.g. wss://ws.birdeye.so/socket (your Business plan URL)
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SEC", "8"))

# share mode + filter helpers with HTTP scanner if present
SCAN_MODE = "strict"     # "strict" | "all"
SEEN_MINTS = set()

def set_ws_mode(mode: str):
    global SCAN_MODE
    SCAN_MODE = "all" if str(mode).lower() == "all" else "strict"
    logging.info("[WS] mode set -> %s", SCAN_MODE)
    try:
        from eventbus import publish
        publish("scan.ws.mode", {"mode": SCAN_MODE})
    except Exception:
        pass

def _passes_filters(tok: dict) -> bool:
    if SCAN_MODE == "all":
        return True
    # keep/extend your strict rules here as needed
    return True

def _extract_token(obj):
    """Try to extract a token-like payload (mint/address + meta) from any WS message."""
    if not isinstance(obj, dict):
        return None
    # Common field names we might see
    mint = obj.get("mint") or obj.get("address") or obj.get("tokenAddress")
    if not mint:
        # search nested dicts
        for k, v in obj.items():
            if isinstance(v, dict):
                r = _extract_token(v)
                if r: return r
        return None
    return {
        "mint": mint,
        "symbol": obj.get("symbol") or obj.get("ticker") or "?",
        "name": obj.get("name") or "?",
        "price": obj.get("price") or obj.get("priceUsd"),
    }

LINK_BE = "https://birdeye.so/token/{mint}?chain=solana"
LINK_PF = "https://pump.fun/{mint}"

class BirdeyeWS:
    def __init__(self, publish=None, notify=None):
        self.publish = publish or (lambda _t,_d: None)
        self.notify  = notify  or (lambda _m: None)
        self._ws   = None
        self._th   = None
        self._stop = threading.Event()
        self.running = False
        self.recv_count = 0
        self.new_count  = 0
        self.seen = deque(maxlen=8000)
        self._seen_set = set()

    def _mark_seen(self, mint):
        if mint in self._seen_set: return False
        self.seen.append(mint); self._seen_set.add(mint)
        if len(self._seen_set) > self.seen.maxlen:
            old = self.seen.popleft(); self._seen_set.discard(old)
        return True

    def start(self):
        if self.running: return
        if not websocket:
            logging.error("[WS] websocket-client lib missing")
            self.publish("scan.birdeye.ws.error", {"err":"lib_missing"})
            return
        if not BIRDEYE_KEY or not BIRDEYE_WS_URL:
            logging.error("[WS] missing BIRDEYE_API_KEY or BIRDEYE_WS_URL")
            self.publish("scan.birdeye.ws.error", {"err":"missing_env"})
            return

        self.running = True
        self._stop.clear()
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()
        self.publish("scan.birdeye.ws.start", {})
        logging.info("[WS] Birdeye WS started")

    def stop(self):
        self.running = False
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        if self._th and self._th.is_alive():
            self._th.join(timeout=2.0)
        self.publish("scan.birdeye.ws.stop", {})
        logging.info("[WS] Birdeye WS stopped")

    def status(self):
        return {
            "running": self.running,
            "recv": self.recv_count,
            "new": self.new_count,
            "seen_cache": len(self._seen_set),
            "thread_alive": self._th.is_alive() if self._th else False,
            "mode": SCAN_MODE,
        }

    # Birdeye Business plan usually authenticates via header "X-API-KEY".
    # Some deployments also require an initial subscription message.
    def _on_open(self, ws):
        logging.info("[WS] open")
        self.publish("scan.birdeye.ws.open", {})
        # If your plan needs a subscribe frame, set env BIRDEYE_WS_SUB JSON and we'll send it:
        sub = os.getenv("BIRDEYE_WS_SUB", "")
        if sub:
            try:
                payload = json.loads(sub)
                ws.send(json.dumps(payload))
                logging.info("[WS] sent subscription payload")
            except Exception as e:
                logging.warning("[WS] bad BIRDEYE_WS_SUB: %s", e)

    def _on_message(self, _ws, msg):
        self.recv_count += 1
        try:
            data = json.loads(msg)
        except Exception:
            # non-JSON message; ignore but keep alive
            return

        tok = _extract_token(data)
        if not tok:
            return
        mint = tok["mint"]
        if not self._mark_seen(mint):
            return

        if _passes_filters(tok):
            self.new_count += 1
            self.publish("scan.birdeye.ws.new", {"token": tok})
            name = tok["name"] or "?"
            sym  = tok["symbol"] or "?"
            text = (
                f"🔔 *Birdeye WS — New token*\n"
                f"*{name}* ({sym})\n"
                f"`{mint}`\n"
                f"[Birdeye]({LINK_BE.format(mint=mint)}) • [Pump.fun]({LINK_PF.format(mint=mint)})"
            )
            try:
                self.notify(text)
            except Exception:
                pass

    def _on_error(self, _ws, err):
        logging.warning("[WS] error: %s", err)
        self.publish("scan.birdeye.ws.error", {"err": str(err)})

    def _on_close(self, _ws, code, reason):
        logging.info("[WS] closed code=%s reason=%s", code, reason)
        self.publish("scan.birdeye.ws.close", {"code": code, "reason": str(reason)})

    def _run(self):
        backoff = 1.0
        while not self._stop.is_set():
            try:
                hdrs = {
                    "X-API-KEY": BIRDEYE_KEY,
                    "User-Agent": "MorkFetchBot/1.0",
                }
                self._ws = websocket.WebSocketApp(
                    BIRDEYE_WS_URL,
                    header=[f"{k}: {v}" for k,v in hdrs.items()],
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logging.warning("[WS] run_forever error: %s", e)

            if self._stop.is_set():
                break
            # reconnect with backoff
            time.sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)
# singleton helper
_ws_singleton = None

def get_ws_scanner(publish, notify):
    global _ws_singleton
    if _ws_singleton is None:
        _ws_singleton = BirdeyeWS(publish=publish, notify=notify)
    return _ws_singleton
# --- END FILE: birdeye_ws.py ---