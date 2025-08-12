# --- BEGIN FILE: birdeye_ws.py ---
import os, logging
FEATURE_WS = os.getenv("FEATURE_WS", "on").lower()

class DisabledWS:
    running = False
    connected = False
    thread_alive = False
    subs = set()
    def start(self, *a, **kw):
        logging.info("[WS] Disabled by FEATURE_WS=%s; not starting", FEATURE_WS)
    def stop(self, *a, **kw):
        logging.info("[WS] Disabled; stop noop")
    def status(self):
        return {
            "running": False, "connected": False, "threadalive": False,
            "mode": "disabled", "messagesreceived": 0, "newtokens": 0, "cachesize": 0
        }
    def subscribe(self, *a, **kw):
        logging.info("[WS] Disabled; subscribe noop")

if FEATURE_WS != "on":
    # Export a no-op singleton so imports don't break
    ws_singleton = DisabledWS()
    
    # Global WebSocket connection status (disabled)
    WS_CONNECTED = False
    WS_TAP_ENABLED = False
    
    def is_ws_connected():
        """Check if WebSocket is currently connected to Birdeye feed"""
        return False
    
    def set_ws_tap(enabled: bool):
        """Enable or disable WebSocket message tapping for debug"""
        logging.info("[WS] Disabled; tap control noop")
        
    def get_ws_disabled(*args, **kwargs):
        """Return disabled WebSocket singleton"""
        return ws_singleton
        
    def get_ws_scanner_disabled(*args, **kwargs):
        """Return disabled WebSocket scanner"""
        return ws_singleton
    
    # Aliases for compatibility
    get_ws = get_ws_disabled
    get_ws_scanner = get_ws_scanner_disabled
        
else:
    # WebSocket enabled - use synchronous implementation
    import json, time, threading, re, random
    from collections import deque
    from typing import Any, Dict

    # Global WebSocket connection status
    WS_CONNECTED = False
    WS_TAP_ENABLED = False
    WS_DEBUG_ENABLED = False
    WS_DEBUG_CACHE = deque(maxlen=30)

    def is_ws_connected():
        """Check if WebSocket is currently connected to Birdeye feed"""
        return WS_CONNECTED

    def set_ws_tap(enabled: bool):
        """Enable or disable WebSocket message tapping for debug"""
        global WS_TAP_ENABLED
        WS_TAP_ENABLED = enabled
        logging.info("[WS] Debug tap %s", "enabled" if enabled else "disabled")

    try:
        # Use synchronous websocket-client library (stable with Gunicorn/threading)
        import websocket  # from websocket-client
        websocket_available = True
        logging.info("[WS] websocket-client library imported successfully")
    except ImportError as e:
        websocket = None
        websocket_available = False
        logging.error("[WS] websocket-client library not available: %s", e)

    # Birdeye configuration
    BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY", "")
    BIRDEYE_WS_URL = os.getenv("BIRDEYE_WS_URL", "wss://public-api.birdeye.so/socket")
    BIRDEYE_WS_BASE = "wss://public-api.birdeye.so/socket"

    # Auto-configure authenticated WebSocket URL 
    if BIRDEYE_WS_URL == "wss://public-api.birdeye.so/socket" and BIRDEYE_KEY:
        BIRDEYE_WS_URL = f"{BIRDEYE_WS_BASE}?x-api-key={BIRDEYE_KEY}"

    SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SEC", "8"))
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
        return True

    def _extract_token(obj):
        """Try to extract a token-like payload (mint/address + meta) from any WS message."""
        if not isinstance(obj, dict):
            return None
        mint = obj.get("mint") or obj.get("address") or obj.get("tokenAddress")
        if not mint:
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

    # Import the clean synchronous implementation from sync file
    from birdeye_ws_sync import BirdeyeWS as SyncBirdeyeWS

    # Use the synchronous implementation with compatibility wrapper
    class BirdeyeWS(SyncBirdeyeWS):
        def __init__(self, publish=None, notify=None):
            # Initialize the sync implementation
            super().__init__(api_key=BIRDEYE_KEY, publish=publish)
            self.notify = notify or (lambda _m: None)
            
            # Add legacy compatibility attributes that old code expects
            self.running = False
            self.seen = deque(maxlen=8000)
            self._seen_set = set()
            self.ws_debug = False
            self._debug_cache = deque(maxlen=100)
            self._debug_mode = False
            self._debug_rate = {"last_ts": 0.0, "count_min": 0, "window_start": 0.0}

        def start(self):
            """Start WebSocket with legacy compatibility"""
            result = super().start()
            self.running = self._running  # sync legacy attribute
            return result

        def stop(self):
            """Stop WebSocket with legacy compatibility"""
            super().stop()
            self.running = False

        def _mark_seen(self, mint):
            """Legacy seen token tracking"""
            if mint in self._seen_set: 
                return False
            self.seen.append(mint)
            self._seen_set.add(mint)
            if self.seen.maxlen and len(self._seen_set) > self.seen.maxlen:
                old = self.seen.popleft()
                self._seen_set.discard(old)
            return True

        def dump_debug_msgs(self, n=10):
            """Get last N debug messages from cache"""
            n = max(1, min(n, 30))
            out = list(self._debug_cache)[-n:]
            return out

        def inject_debug_event(self, label: str = "synthetic"):
            """Push a fake event through the normal message path for pipeline verification"""
            payload: Dict[str, Any] = {
                "event": "debug.synthetic",
                "label": label,
                "token": {
                    "name": "moonpepe",
                    "symbol": "moonpepe", 
                    "mint": "8DX27KPjZMpLi3pBBTaEVqSNq33gAaWkL2v7N8kCNpump",
                    "price": "0.0000700144"
                }
            }
            try:
                self._debug_cache.append(payload)
            except Exception:
                pass
            # Echo via publish like a real message
            self.publish("ws.debug", {
                "ts": int(time.time()),
                "event": payload["event"],
                "preview": json.dumps(payload)[:900]
            })
            logging.info("[WS] injected synthetic debug event")

    # Singleton helper
    _ws_singleton = None
    ws_client_singleton = None

    def get_ws_scanner(publish, notify):
        global _ws_singleton, ws_client_singleton
        if _ws_singleton is None:
            _ws_singleton = BirdeyeWS(publish=publish, notify=notify)
            ws_client_singleton = _ws_singleton
        return _ws_singleton

    def get_ws(publish=None, notify=None):
        """Enhanced WebSocket client accessor with debug capabilities"""
        global _ws_singleton, ws_client_singleton
        if _ws_singleton is None and publish and notify:
            _ws_singleton = BirdeyeWS(publish=publish, notify=notify)
            ws_client_singleton = _ws_singleton
        return _ws_singleton or ws_client_singleton

# --- END FILE: birdeye_ws.py ---