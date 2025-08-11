# --- BEGIN FILE: birdeye_ws.py ---
import os, json, time, threading, logging, re
from collections import deque

# Global WebSocket connection status
WS_CONNECTED = False
WS_TAP_ENABLED = False

def is_ws_connected():
    """Check if WebSocket is currently connected to Birdeye feed"""
    return WS_CONNECTED

def set_ws_tap(enabled: bool):
    """Enable or disable WebSocket message tapping for debug"""
    global WS_TAP_ENABLED
    WS_TAP_ENABLED = enabled
    logging.info("[WS] Debug tap %s", "enabled" if enabled else "disabled")

try:
    import websocket  # from websocket-client
except Exception as e:
    websocket = None
    logging.warning("[WS] websocket-client not available: %s", e)

BIRDEYE_KEY   = os.getenv("BIRDEYE_API_KEY", "")
BIRDEYE_WS_URL = os.getenv("BIRDEYE_WS_URL", "")  # e.g. wss://ws.birdeye.so/socket (your Business plan URL)

# Auto-configure public API URL if no custom URL provided but API key exists
if not BIRDEYE_WS_URL and BIRDEYE_KEY:
    BIRDEYE_WS_URL = f"wss://public-api.birdeye.so/socket/solana?x-api-key={BIRDEYE_KEY}"
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
        if self.seen.maxlen and len(self._seen_set) > self.seen.maxlen:
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
            "connected": WS_CONNECTED,
            "recv": self.recv_count,
            "new": self.new_count,
            "seen_cache": len(self._seen_set),
            "thread_alive": self._th.is_alive() if self._th else False,
            "mode": SCAN_MODE,
            "tap_enabled": WS_TAP_ENABLED or os.getenv("WS_TAP") == "1",
        }

    # Birdeye Business plan usually authenticates via header "X-API-KEY".
    # Some deployments also require an initial subscription message.
    def _on_open(self, ws):
        global WS_CONNECTED
        WS_CONNECTED = True
        logging.info("[WS] Connected to Birdeye feed")
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
        else:
            # Default subscription for token.created events
            default_sub = {
                "type": "subscribe", 
                "channels": [{"name": "token.created"}]
            }
            try:
                ws.send(json.dumps(default_sub))
                logging.info("[WS] sent default token.created subscription")
            except Exception as e:
                logging.warning("[WS] failed to send default subscription: %s", e)

    def _on_message(self, _ws, msg):
        self.recv_count += 1
        
        # Debug tap: log raw messages when enabled
        if WS_TAP_ENABLED or os.getenv("WS_TAP") == "1":
            logging.info("[WS_TAP] Raw message: %s", msg[:200] + "..." if len(msg) > 200 else msg)
            
        try:
            data = json.loads(msg)
        except Exception:
            # non-JSON message; ignore but keep alive
            return

        # Handle both generic token extraction and specific token.created events
        event_type = data.get("type")
        if event_type == "token.created":
            tok_data = data.get("data", {})
            tok = {
                "mint": tok_data.get("address") or tok_data.get("mint"),
                "symbol": tok_data.get("symbol") or "?",
                "name": tok_data.get("name") or "?",
                "price": tok_data.get("price") or tok_data.get("priceUsd")
            }
        else:
            tok = _extract_token(data)
            
        if not tok or not tok.get("mint"):
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
                f"⚡ *Birdeye WS — New token*\n"
                f"*{name}* ({sym})\n"
                f"`{mint}`\n"
                f"[Birdeye]({LINK_BE.format(mint=mint)}) • [Pump.fun]({LINK_PF.format(mint=mint)})"
            )
            try:
                self.notify(text)
                logging.info("[WS] Alert sent: %s (%s) %s", name, sym, mint)
            except Exception:
                pass

    def _on_error(self, _ws, err):
        global WS_CONNECTED
        WS_CONNECTED = False
        logging.warning("[WS] error: %s", err)
        self.publish("scan.birdeye.ws.error", {"err": str(err)})

    def _on_close(self, _ws, code, reason):
        global WS_CONNECTED
        WS_CONNECTED = False
        logging.info("[WS] Disconnected - code=%s reason=%s", code, reason)
        self.publish("scan.birdeye.ws.close", {"code": code, "reason": str(reason)})

    def _run(self):
        backoff = 1.0
        while not self._stop.is_set():
            try:
                # Support both header and URL parameter authentication
                if "?x-api-key=" in BIRDEYE_WS_URL:
                    # URL parameter auth (public API style)
                    hdrs = {"User-Agent": "MorkFetchBot/1.0"}
                else:
                    # Header auth (business plan style)
                    hdrs = {
                        "X-API-KEY": BIRDEYE_KEY,
                        "User-Agent": "MorkFetchBot/1.0",
                    }
                    
                if websocket:
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

# Direct singleton instance for simple imports (compatibility)
ws_client = None

def get_ws_client():
    global ws_client
    if ws_client is None:
        from eventbus import publish
        ws_client = BirdeyeWS(publish=publish, notify=lambda msg: logging.info("[WS] %s", msg))
    return ws_client

# Make ws_client available immediately
ws_client = get_ws_client()
# --- END FILE: birdeye_ws.py ---