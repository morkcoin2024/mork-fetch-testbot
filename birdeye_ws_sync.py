# birdeye_ws_sync.py - Synchronous WebSocket implementation for Gunicorn stability
import json, os, threading, time, random, logging
try:
    import websocket  # from websocket-client package
    from websocket._app import WebSocketApp  # Import WebSocketApp from correct module
    websocket.WebSocketApp = WebSocketApp  # Make it available via websocket.WebSocketApp
except (ImportError, AttributeError):
    websocket = None
    WebSocketApp = None
from collections import deque

log = logging.getLogger(__name__)

BIRDEYE_WS_BASE = "wss://public-api.birdeye.so/socket"

# Global connection status
WS_CONNECTED = False
WS_TAP_ENABLED = False
WS_DEBUG_ENABLED = False
WS_DEBUG_CACHE = deque(maxlen=30)

def is_ws_connected():
    """Global function to check WebSocket connection status"""
    return WS_CONNECTED

def set_ws_tap(enabled: bool):
    """Enable or disable WebSocket message tapping for debug"""
    global WS_TAP_ENABLED
    WS_TAP_ENABLED = enabled
    logging.info("[WS] Debug tap %s", "enabled" if enabled else "disabled")

class BirdeyeWS:
    def __init__(self, api_key: str, publish=None):
        self.api_key = api_key or os.getenv("BIRDEYE_API_KEY", "")
        self.url = f"{BIRDEYE_WS_BASE}?x-api-key={self.api_key}"
        self.publish = publish  # Event publishing callback
        
        # Birdeye-required headers + subprotocol
        self.headers = [
            "Origin: ws://public-api.birdeye.so",
            "Sec-WebSocket-Origin: ws://public-api.birdeye.so",
        ]
        self.subprotocols = ["echo-protocol"]

        self._ws = None
        self._th = None
        self._running = False
        self._connected_event = threading.Event()  # Thread-safe connection status
        self.recv_count = 0
        self.new_count = 0
        self.last_msg_time = None  # Timestamp of last received message
        self._debug = False
        self._tap_until = 0
        
        # Token deduplication
        self.seen_tokens = set()
        self.seen_tokens_deque = deque(maxlen=8000)

    # --- public API used by app.py ---
    def start(self):
        if self._running: 
            return True
        self._running = True
        self._th = threading.Thread(target=self._run_loop, name="BirdeyeWS", daemon=True)
        self._th.start()
        self._log("Birdeye WS started (sync client)")
        if self.publish:
            self.publish("scan.birdeye.ws.start", {})
        return True

    def stop(self):
        self._running = False
        try:
            if self._ws:
                self._ws.close(timeout=2)
        except Exception:
            pass
        self._log("Birdeye WS stopped")
        if self.publish:
            self.publish("scan.birdeye.ws.stop", {})

    def status(self):
        return {
            "running": self._running,
            "connected": self._connected_event.is_set(),
            "recv": self.recv_count,
            "new": self.new_count,
            "seen_cache": len(self.seen_tokens),
            "thread_alive": bool(self._th and self._th.is_alive()),
            "mode": "strict",
            "tap_enabled": time.time() < self._tap_until,
            "last_msg_time": self.last_msg_time,
            "last_msg_ago": int(time.time() - self.last_msg_time) if self.last_msg_time else None,
        }

    def set_debug(self, on: bool):
        self._debug = bool(on)
        global WS_DEBUG_ENABLED
        WS_DEBUG_ENABLED = self._debug
        return self._debug

    def injectdebugevent(self, payload: dict):
        # simulate a message
        self.recv_count += 1
        if self._debug:
            self._log(f"injected debug event: {payload}")
        return True

    def getdebugcache(self):
        return {"recv": self.recv_count, "new": self.new_count, "cache": list(WS_DEBUG_CACHE)}

    def enable_tap(self, seconds: int):
        self._tap_until = time.time() + max(1, seconds)
        self._log(f"TAP enabled for {seconds} seconds")

    # --- internal ---
    def _log(self, msg, level="info"):
        """Internal logging with [WS] prefix"""
        getattr(log, level)(f"[WS] {msg}")

    def _run_loop(self):
        backoff = 2
        while self._running:
            try:
                self._run_once()
                backoff = 2  # reset after a successful run
            except Exception as e:
                self._log(f"run error: {type(e).__name__}: {e}", level="warning")
                time.sleep(backoff + random.random())
                backoff = min(backoff * 1.6, 30)

    def _run_once(self):
        global WS_CONNECTED
        WS_CONNECTED = False
        self._connected_event.clear()
        
        self._log("Creating WebSocket connection...")
        self._ws = websocket.WebSocketApp(
            self.url,
            header=self.headers,
            subprotocols=self.subprotocols,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        
        # Run WebSocket with ping to keep Cloudflare happy
        self._log("Starting WebSocket run_forever...")
        self._ws.run_forever(ping_interval=20, ping_timeout=10)

    def _on_open(self, ws):
        global WS_CONNECTED
        WS_CONNECTED = True
        self._connected_event.set()
        self._log("✅ Connected to Birdeye WebSocket feed")
        
        # Send subscriptions for Launchpad priority
        subscriptions = [
            {"type": "subscribe", "topic": "launchpad.created", "chain": "solana"},
            {"type": "subscribe", "topic": "token.created", "chain": "solana"},
            {"type": "subscribe", "topic": "token.updated", "chain": "solana"},
        ]
        
        for sub in subscriptions:
            try:
                ws.send(json.dumps(sub))
                self._log(f"📡 Subscribed to {sub.get('topic')}")
            except Exception as e:
                self._log(f"subscription error for {sub.get('topic')}: {e}", level="warning")

    def _on_message(self, ws, message):
        global WS_DEBUG_CACHE
        self.recv_count += 1
        self.last_msg_time = time.time()
        
        # Store in debug cache
        WS_DEBUG_CACHE.append({
            "timestamp": time.time(),
            "length": len(message) if hasattr(message, "__len__") else 0,
            "content": str(message)[:100] + "..." if len(str(message)) > 100 else str(message)
        })
        
        if self._debug or WS_DEBUG_ENABLED:
            self._log(f"📨 Message received (len={len(message) if hasattr(message, '__len__') else 'unknown'})")
        
        # Process message for new tokens
        try:
            data = json.loads(message) if isinstance(message, str) else message
            if isinstance(data, dict) and "address" in data:
                token_addr = data["address"]
                if token_addr not in self.seen_tokens:
                    self.seen_tokens.add(token_addr)
                    self.seen_tokens_deque.append(token_addr)
                    self.new_count += 1
                    
                    # Publish new token event
                    if self.publish:
                        self.publish("scan.birdeye.ws.new_token", {
                            "source": "birdeye_ws",
                            "address": token_addr,
                            "data": data
                        })
                    
                    self._log(f"🚀 New token detected: {token_addr[:8]}... (total: {self.new_count})")
        except Exception as e:
            if self._debug:
                self._log(f"message processing error: {e}", level="warning")

        # Optional tap to admin for debugging
        if time.time() < self._tap_until:
            try:
                self._log(f"TAP sample: {str(message)[:140]}")
            except Exception:
                pass

    def _on_error(self, ws, error):
        global WS_CONNECTED
        WS_CONNECTED = False
        self._connected_event.clear()
        self._log(f"❌ WebSocket error: {type(error).__name__}: {error}", level="error")

    def _on_close(self, ws, close_status_code, close_msg):
        global WS_CONNECTED
        WS_CONNECTED = False
        self._connected_event.clear()
        self._log(f"🔌 Disconnected - code={close_status_code} reason={close_msg}")

# Factory function for compatibility
def get_ws_scanner(api_key=None, publish=None):
    """Create a new BirdeyeWS scanner instance"""
    return BirdeyeWS(api_key=api_key or os.getenv("BIRDEYE_API_KEY", ""), publish=publish)

def get_ws(api_key=None, publish=None):
    """Alias for get_ws_scanner"""
    return get_ws_scanner(api_key=api_key, publish=publish)