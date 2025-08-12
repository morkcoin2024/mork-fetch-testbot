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
        # Use synchronous websocket-client library (stable with Gunicorn/threading)
        import websocket  # from websocket-client
        websocket_available = True
        logging.info("[WS] websocket-client library imported successfully")
    except ImportError as e:
        websocket = None
        websocket_available = False
        logging.error("[WS] websocket-client library not available: %s", e)

    # --- Birdeye WS required headers & subprotocols ---
    WS_HEADERS = [
        "Origin: ws://public-api.birdeye.so",
        "Sec-WebSocket-Origin: ws://public-api.birdeye.so",
        # NOTE: Sec-WebSocket-Protocol is negotiated via the 'subprotocols' arg below
    ]

    WS_SUBPROTOCOLS = ["echo-protocol"]

    BIRDEYE_KEY   = os.getenv("BIRDEYE_API_KEY", "")
    BIRDEYE_WS_URL = os.getenv("BIRDEYE_WS_URL", "wss://public-api.birdeye.so/socket")

    # Auto-configure authenticated WebSocket URL 
    if BIRDEYE_WS_URL == "wss://public-api.birdeye.so/socket" and BIRDEYE_KEY:
        # Use authenticated WebSocket endpoint with API key in URL (Birdeye WebSocket auth pattern)
        BIRDEYE_WS_URL = f"wss://public-api.birdeye.so/socket?x-api-key={BIRDEYE_KEY}"
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

    # Import the clean synchronous implementation
    from birdeye_ws_sync import BirdeyeWS as SyncBirdeyeWS
    
    # Use the synchronous implementation directly
    class BirdeyeWS(SyncBirdeyeWS):
        def __init__(self, publish=None, notify=None):
            # Initialize with the correct parameters for the sync implementation
            super().__init__(api_key=BIRDEYE_KEY, publish=publish)
            self.notify = notify or (lambda _m: None)
            
            # Legacy compatibility attributes
            self.running = False  # legacy compatibility
            self.seen = deque(maxlen=8000)
            self._seen_set = set()
            
            # --- Enhanced Debug Support ---
            self.ws_debug = False                 # on/off toggle
            self._debug_cache = deque(maxlen=100) # store recent WS messages/events
            self._debug_mode = False
            self._debug_rate = {"last_ts": 0.0, "count_min": 0, "window_start": 0.0}

        def _log(self, msg, level="info"):
            line = f"[WS] {msg}"
            if level == "error":
                logging.error(line)
            elif level == "warning":
                logging.warning(line)
            else:
                logging.info(line)
            if self._debug_mode:
                # keep a lightweight trail for /ws_dump
                self._debug_cache.append(f"{int(time.time())} {msg}")

        def _mark_seen(self, mint):
            if mint in self._seen_set: return False
            self.seen.append(mint); self._seen_set.add(mint)
            if self.seen.maxlen and len(self._seen_set) > self.seen.maxlen:
                old = self.seen.popleft(); self._seen_set.discard(old)
            return True

        def start(self):
            if self.running: 
                return True
            if not websocket_available:
                self._log("websocket-client lib missing", level="error")
                self.publish("scan.birdeye.ws.error", {"err":"lib_missing"})
                return False
            if not BIRDEYE_KEY or not BIRDEYE_WS_URL:
                self._log("missing BIRDEYE_API_KEY or BIRDEYE_WS_URL", level="error")
                self.publish("scan.birdeye.ws.error", {"err":"missing_env"})
                return False

            self.running = True
            self._running = True
            self._th = threading.Thread(target=self._run_loop, name="BirdeyeWS", daemon=True)
            self._th.start()
            self.publish("scan.birdeye.ws.start", {})
            self._log("Birdeye WS started (sync client)")
            return True
            
        def _run_loop(self):
            """Synchronous WebSocket run loop using websocket-client"""
            backoff = 2
            while self._running:
                try:
                    self._run_once()
                    backoff = 2  # reset after successful run
                except Exception as e:
                    self._log(f"run error: {type(e).__name__}: {e}", level="warning")
                    time.sleep(backoff + random.random())
                    backoff = min(backoff * 1.6, 30)

        def _run_once(self):
            """Single WebSocket connection attempt"""
            global WS_CONNECTED
            WS_CONNECTED = False
            self._connected = False
            
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
            
            # Run WebSocket with ping to keep connection alive
            self._log("Starting WebSocket run_forever...")
            self._ws.run_forever(ping_interval=20, ping_timeout=10)

        def _on_open(self, ws):
            """WebSocket connection opened"""
            global WS_CONNECTED
            WS_CONNECTED = True
            self._connected = True
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
            """WebSocket message received"""
            self.recv_count += 1
            
            if self._debug:
                self._log(f"📨 Message received (len={len(message) if hasattr(message, '__len__') else 'unknown'})")
            
            # Process message for new tokens
            try:
                data = json.loads(message) if isinstance(message, str) else message
                if isinstance(data, dict) and "address" in data:
                    token_addr = data["address"]
                    if self._mark_seen(token_addr):
                        self.new_count += 1
                        
                        # Publish new token event
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
            """WebSocket error occurred"""
            global WS_CONNECTED
            WS_CONNECTED = False
            self._connected = False
            self._log(f"❌ WebSocket error: {type(error).__name__}: {error}", level="error")

        def _on_close(self, ws, close_status_code, close_msg):
            """WebSocket connection closed"""
            global WS_CONNECTED
            WS_CONNECTED = False
            self._connected = False
            self._log(f"🔌 Disconnected - code={close_status_code} reason={close_msg}")

        def stop(self):
            """Stop the WebSocket connection"""
            self._running = False
            self.running = False
            try:
                if self._ws:
                    self._ws.close(timeout=2)
            except Exception:
                pass
            self._log("Birdeye WS stopped")
            self.publish("scan.birdeye.ws.stop", {})

        def status(self):
            """Get WebSocket status"""
            return {
                "running": self._running,
                "connected": self._connected,
                "recv": self.recv_count,
                "new": self.new_count,
                "seen_cache": len(getattr(self, 'seen_tokens', set())),
                "thread_alive": bool(self._th and self._th.is_alive()),
                "mode": "strict",
                "tap_enabled": time.time() < self._tap_until,
            }

        def set_debug(self, on: bool):
            """Set debug mode"""
            self._debug = bool(on)
            return self._debug

        def injectdebugevent(self, payload: dict):
            """Inject a debug event"""
            self.recv_count += 1
            if self._debug:
                self._log(f"injected debug event: {payload}")
            return True

        def getdebugcache(self):
            """Get debug cache"""
            return {"recv": self.recv_count, "new": self.new_count}

        def enable_tap(self, seconds: int):
            """Enable message tapping for debugging"""
            self._tap_until = time.time() + max(1, seconds)
            self._log(f"TAP enabled for {seconds} seconds")
                "tap_enabled": WS_TAP_ENABLED or os.getenv("WS_TAP") == "1",
            }

        def _on_open(self, ws):
            """Birdeye Business plan usually authenticates via header "X-API-KEY"."""
            global WS_CONNECTED
            WS_CONNECTED = True
            self.connected = True
            self._log("open")
            self._log("Connected to Birdeye feed")
            self.publish("scan.birdeye.ws.open", {})
            
            # Send subscriptions async (ensure we're in async context)
            if hasattr(asyncio, '_get_running_loop') and asyncio._get_running_loop():
                asyncio.create_task(self._send_subscriptions(ws))
            else:
                # Fallback for sync context - schedule for later
                self._log("Scheduling subscriptions for async context")

        async def _send_subscriptions(self, ws):
            """Send subscription messages asynchronously"""
            try:
                # Enhanced subscription with Launchpad priority
                sub = os.getenv("BIRDEYE_WS_SUB", "")
                if sub:
                    try:
                        payload = json.loads(sub)
                        await ws.send(json.dumps(payload))
                        self._log("sent custom subscription payload")
                    except Exception as e:
                        self._log(f"bad BIRDEYE_WS_SUB: {e}", level="warning")
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
                            await ws.send(json.dumps(topic_sub))
                            self._log(f"sent {topic} subscription")
                        except Exception as e:
                            self._log(f"{topic} subscription failed: {e}", level="warning")
                    
                    # Fallback: original channel-based format
                    try:
                        default_sub = {
                            "type": "subscribe", 
                            "channels": [{"name": "token.created"}]
                        }
                        await ws.send(json.dumps(default_sub))
                        self._log("sent fallback channel subscription")
                    except Exception as e:
                        self._log(f"fallback subscription failed: {e}", level="warning")
            except Exception as e:
                self._log(f"Subscription error: {e}", level="error")

        def _on_message(self, ws, msg):
            self.recv_count += 1
            self._log(f"msg len={len(msg)}")
            self._log(f"Message received ({len(msg)} bytes)")
            
            # Debug tap: log raw messages when enabled
            if WS_TAP_ENABLED or os.getenv("WS_TAP") == "1":
                self._log(f"[TAP] Raw message: {msg[:200] + '...' if len(msg) > 200 else msg}")
                
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
                        self._log(f"debug echo sent ({event})")
                    except Exception as e:
                        self._log(f"debug echo error: {e}", level="warning")

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
                    self._log(f"Alert sent: {name} ({sym}) {mint}")
                except Exception:
                    pass

        def _on_error(self, ws, err):
            global WS_CONNECTED
            WS_CONNECTED = False
            self._log(f"error: {err}", level="error")
            self._log(f"WebSocket error occurred: {err}", level="error")
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
                self._log(f"HANDSHAKE ERROR: {err}", level="error")
                self._log(f"Full error details: {error_details}", level="error")
                # Send detailed error to admin for debugging
                try:
                    if hasattr(self, 'notify') and self.notify:
                        self.notify(f"🚨 *WebSocket Handshake Error*\n```\n{err}\n```\nURL: `{BIRDEYE_WS_URL}`\nHeaders: {WS_HEADERS}\nSubprotocols: {WS_SUBPROTOCOLS}")
                except:
                    pass
            else:
                self._log(f"error: {err}", level="warning")
            
            self.publish("scan.birdeye.ws.error", error_details)

        def _on_close(self, ws, code, reason):
            global WS_CONNECTED
            WS_CONNECTED = False
            self._log("close")
            self._log(f"Disconnected - code={code} reason={reason}")
            self.publish("scan.birdeye.ws.close", {"code": code, "reason": str(reason)})

        # add the three helpers expected by the /ws_* commands
        def getdebugcache(self):
            """Used by /ws_dump to read recent debug lines."""
            return list(self._debug_cache)

        def set_debug(self, on: bool):
            self._debug_mode = bool(on)
            self._log(f"debug mode -> {self._debug_mode}")

        def injectdebugevent(self, payload: dict):
            """Allow /ws_probe to inject a synthetic event into the debug cache."""
            try:
                self._log(f"probe inject: {payload}")
                self._debug_cache.append(f"inject {payload}")
                return True
            except Exception as e:
                self._log(f"probe inject failed: {e}", level="error")
                return False

    # ===== Debug helpers (called from app.py) =====
    def set_debug_legacy(self, on: bool):
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