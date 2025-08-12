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
    # existing implementation (unchanged)
    import json, time, threading, re
    from collections import deque
    from typing import Any, Dict

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

    # --- Birdeye WS required headers & subprotocols ---
    WS_HEADERS = [
        "Origin: ws://public-api.birdeye.so",
        "Sec-WebSocket-Origin: ws://public-api.birdeye.so",
        # NOTE: Sec-WebSocket-Protocol is negotiated via the 'subprotocols' arg below
    ]

    WS_SUBPROTOCOLS = ["echo-protocol"]

    BIRDEYE_KEY   = os.getenv("BIRDEYE_API_KEY", "")
    BIRDEYE_WS_URL = os.getenv("BIRDEYE_WS_URL", "wss://public-api.birdeye.so/socket")

    # Auto-configure public API URL if no custom URL provided but API key exists
    if BIRDEYE_WS_URL == "wss://public-api.birdeye.so/socket" and BIRDEYE_KEY:
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
            
            # --- Enhanced Debug Support ---
            self.ws_debug = False                 # on/off toggle
            self._debug_cache = deque(maxlen=100) # store recent WS messages/events
            self._debug_mode = False
            self._debug_rate = {"last_ts": 0.0, "count_min": 0, "window_start": 0.0}

        def _log(self, msg):
            """Unified logging with debug cache support"""
            logging.info(f"[WS] {msg}")              # unify tag so /a_logs_tail contains=[WS] works
            if self._debug_mode:
                self._debug_cache.append(f"{time.time():.0f} {msg}")

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
            
            # Enhanced subscription topics - prefer Launchpad if available
            self.subscription_topics = [
                "launchpad.created",  # Priority: Launchpad new tokens
                "token.created",      # Fallback: Generic token events
            ]
            
            self._stop.clear()
            self._th = threading.Thread(target=self._run_loop, daemon=True)
            self._th.start()
            self.publish("scan.birdeye.ws.start", {})
            logging.info("[WS] Birdeye WS started with Launchpad priority")
            
        def _run_loop(self):
            backoff = 1.0
            while not self._stop.is_set():
                try:
                    # WebSocket connection with required headers including X-API-KEY as requested by Birdeye support
                    if websocket:
                        # Use getattr to safely access WebSocketApp
                        WebSocketApp = getattr(websocket, 'WebSocketApp', None)
                        if WebSocketApp:
                            # Build headers with X-API-KEY as required by Birdeye support
                            headers = [
                                "Origin: ws://public-api.birdeye.so",
                                "Sec-WebSocket-Origin: ws://public-api.birdeye.so",
                                f"X-API-KEY: {BIRDEYE_KEY}",
                            ]
                            
                            self._ws = WebSocketApp(
                                BIRDEYE_WS_URL,
                                header=headers,
                                subprotocols=["echo-protocol"],   # as Birdeye instructed
                                on_open=self._on_open,
                                on_message=self._on_message,
                                on_error=self._on_error,
                                on_close=self._on_close,
                            )
                            # Keepalive (avoid CF idle closes)
                            self._ws.run_forever(
                                ping_interval=20,
                                ping_timeout=10,
                                ping_payload="keepalive",
                            )
                except Exception as e:
                    logging.warning("[WS] run_forever error: %s", e)

                if self._stop.is_set():
                    break
                # reconnect with backoff
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)

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
        # Enhanced subscription with Launchpad priority
        sub = os.getenv("BIRDEYE_WS_SUB", "")
        if sub:
            try:
                payload = json.loads(sub)
                ws.send(json.dumps(payload))
                logging.info("[WS] sent custom subscription payload")
            except Exception as e:
                logging.warning("[WS] bad BIRDEYE_WS_SUB: %s", e)
        else:
            # Try subscribing to multiple topics with priority for Launchpad
            topics_to_try = getattr(self, 'subscription_topics', ["token.created"])
            
            for topic in topics_to_try:
                try:
                    # Try Birdeye topic-based subscription format
                    topic_sub = {
                        "type": "subscribe",
                        "topic": topic,
                        "chain": "solana"
                    }
                    ws.send(json.dumps(topic_sub))
                    logging.info("[WS] sent %s subscription", topic)
                except Exception as e:
                    logging.debug("[WS] %s subscription failed: %s", topic, e)
            
            # Fallback: original channel-based format
            try:
                default_sub = {
                    "type": "subscribe", 
                    "channels": [{"name": "token.created"}]
                }
                ws.send(json.dumps(default_sub))
                logging.info("[WS] sent fallback channel subscription")
            except Exception as e:
                logging.warning("[WS] fallback subscription failed: %s", e)

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

        # --- ENHANCED DEBUG ECHO ---
        if self.ws_debug:
            # Store in debug cache (raw)
            try:
                self._debug_cache.append(data)
            except Exception:
                pass
            # Simple rate limit: max 6 debug pushes / minute
            now = time.time()
            win = self._debug_rate
            if now - win.get("window_start", 0) > 60:
                win["window_start"] = now
                win["count_min"] = 0
            if win["count_min"] < 6:
                win["count_min"] += 1
                # Publish a compact summary to app -> Telegram
                try:
                    event = data.get("event") or data.get("type", "?")
                    # Trim payload to keep Telegram happy
                    preview = json.dumps(data)[:900]
                    self.publish("ws.debug", {
                        "ts": int(now),
                        "event": event,
                        "preview": preview
                    })
                    logging.info("[WS] debug echo sent (%s)", event)
                except Exception as e:
                    logging.warning("[WS] debug echo error: %s", e)

        # Enhanced event handling for multiple topic types
        event_type = data.get("type") or data.get("topic", "")
        
        # Handle specific Launchpad and token creation events
        if event_type in ("launchpad.created", "token.created"):
            tok_data = data.get("data", {})
            tok = {
                "mint": tok_data.get("address") or tok_data.get("mint"),
                "symbol": tok_data.get("symbol") or "?",
                "name": tok_data.get("name") or "?",
                "price": tok_data.get("price") or tok_data.get("priceUsd"),
                "source": event_type  # Track which topic provided the token
            }
        else:
            # Fallback to generic token extraction
            tok = _extract_token(data)
            if tok:
                tok["source"] = "generic"
            
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
            source = tok.get("source", "ws")
            
            # Enhanced alert with source information
            source_emoji = "🚀" if source == "launchpad.created" else "⚡"
            source_text = "Launchpad" if source == "launchpad.created" else "WS"
            
            text = (
                f"{source_emoji} *Birdeye {source_text} — New token*\n"
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
        # Enhanced error logging to capture full handshake details
        error_details = {
            "error": str(err),
            "type": type(err).__name__,
            "ws_url": BIRDEYE_WS_URL,
            "headers": WS_HEADERS,
            "subprotocols": WS_SUBPROTOCOLS
        }
        
        # Check if this is a handshake error (403 Forbidden, etc.)
        if "handshake" in str(err).lower() or "403" in str(err) or "forbidden" in str(err).lower():
            logging.error("[WS] HANDSHAKE ERROR: %s", err)
            logging.error("[WS] Full error details: %s", error_details)
            # Send detailed error to admin for debugging
            try:
                if hasattr(self, 'notify') and self.notify:
                    self.notify(f"🚨 *WebSocket Handshake Error*\n```\n{err}\n```\nURL: `{BIRDEYE_WS_URL}`\nHeaders: {WS_HEADERS}\nSubprotocols: {WS_SUBPROTOCOLS}")
            except:
                pass
        else:
            logging.warning("[WS] error: %s", err)
        
        self.publish("scan.birdeye.ws.error", error_details)

    def _on_close(self, _ws, code, reason):
        global WS_CONNECTED
        WS_CONNECTED = False
        logging.info("[WS] Disconnected - code=%s reason=%s", code, reason)
        self.publish("scan.birdeye.ws.close", {"code": code, "reason": str(reason)})



    # ===== Debug helpers (called from app.py) =====
    def set_debug(self, on: bool):
        """Enable/disable debug mode with rate-limited message forwarding"""
        self.ws_debug = bool(on)
        logging.info("[WS] debug mode: %s", "ON" if self.ws_debug else "OFF")
        self.publish("ws.debug.mode", {"on": self.ws_debug})

    def get_debug_cache(self, n: int = 10):
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

    # --- New helpers expected by /ws_* commands ---
    def injectdebugevent(self, payload: dict):
        """Allow /ws_probe to inject a synthetic event into the debug cache."""
        self._log(f"probe inject: {payload}")
        self._debug_cache.append(f"inject {payload}")
        return True

    def getdebugcache(self):
        """Return a list of recent debug lines for /ws_dump."""
        return list(self._debug_cache)

    def set_debug(self, on: bool):
        self._debug_mode = bool(on)
        self._log(f"debug mode -> {self._debug_mode}")

# singleton helper
_ws_singleton = None
ws_client_singleton = None  # Alternative reference for compatibility

def get_ws_scanner(publish, notify):
    global _ws_singleton, ws_client_singleton
    if _ws_singleton is None:
        _ws_singleton = BirdeyeWS(publish=publish, notify=notify)
        ws_client_singleton = _ws_singleton  # Set alternative reference
    return _ws_singleton

def get_ws(publish=None, notify=None):
    """Enhanced WebSocket client accessor with debug capabilities"""
    global _ws_singleton, ws_client_singleton
    if _ws_singleton is None and publish and notify:
        _ws_singleton = BirdeyeWS(publish=publish, notify=notify)
        ws_client_singleton = _ws_singleton
    return _ws_singleton or ws_client_singleton
# --- END FILE: birdeye_ws.py ---