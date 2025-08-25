# birdeye_ws_enhanced.py
import json
import logging
import os
import threading
import time

import websocket  # pip install websocket-client

BIRDEYE_WS_URL = os.getenv("BIRDEYE_WS_URL", "wss://public-api.birdeye.so/socket")
BIRDEYE_WS_KEY = os.getenv("BIRDEYE_WS_KEY", "")
CHAIN = "solana"

# Target Launchpad stream first; keep token.created as fallback
# If the Launchpad topic isn't supported in your account/tier,
# server will ignore it—token.created keeps us alive.
PREFERRED_TOPICS = [
    "launchpad.created",  # target for Launchpad new token events
    "token.created",  # fallback: generic new token events
]


class BirdeyeWS:
    def __init__(self, publish=None, notify=None):
        self.publish = publish or (lambda _t, _d: None)
        self.notify = notify or (lambda _m: None)
        self.ws = None
        self.thread = None
        self.stop_flag = threading.Event()
        self.connected = False
        self.subscriptions = set(PREFERRED_TOPICS[:])  # default subs

    # --- public API ---
    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logging.info("[WS] Birdeye WS started")

    def stop(self):
        self.stop_flag.set()
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        logging.info("[WS] Birdeye WS stopped")

    def status(self):
        return {
            "connected": self.connected,
            "subs": list(self.subscriptions),
            "url": BIRDEYE_WS_URL,
            "key_set": bool(BIRDEYE_WS_KEY),
        }

    def set_subscriptions(self, topics):
        # live-resubscribe on next reconnect
        self.subscriptions = set(t.strip() for t in topics if t.strip())
        logging.info("[WS] subscriptions set -> %s", self.subscriptions)
        # If connected, send subscribe messages now
        if self.connected:
            for t in self.subscriptions:
                self._send_subscribe(t)

    # --- internal ---
    def _run(self):
        while not self.stop_flag.is_set():
            try:
                self._connect_and_loop()
            except Exception as e:
                logging.warning("[WS] loop error: %s", e)
            # backoff a little on reconnect
            for _ in range(5):
                if self.stop_flag.is_set():
                    break
                time.sleep(0.5)

    def _connect_and_loop(self):
        headers = []
        if BIRDEYE_WS_KEY:
            headers.append(f"X-API-KEY: {BIRDEYE_WS_KEY}")

        self.ws = websocket.WebSocketApp(
            BIRDEYE_WS_URL,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self.ws.run_forever(ping_interval=20, ping_timeout=10)

    def _on_open(self, _):
        self.connected = True
        logging.info("[WS] Connected to Birdeye feed")
        # try to subscribe launchpad first, then token.created
        for topic in PREFERRED_TOPICS:
            if topic in self.subscriptions:
                self._send_subscribe(topic)
        self.publish("scan.ws.open", {"ok": True, "subs": list(self.subscriptions)})

    def _on_close(self, *_a, **_kw):
        self.connected = False
        logging.info("[WS] Connection closed")
        self.publish("scan.ws.close", {"ok": True})

    def _on_error(self, _w, err):
        logging.warning("[WS] error: %s", err)
        self.publish("scan.ws.error", {"err": str(err)})

    def _send(self, obj):
        try:
            self.ws.send(json.dumps(obj))
        except Exception as e:
            logging.warning("[WS] send failed: %s", e)

    def _send_subscribe(self, topic):
        # Birdeye common pattern: {"type":"subscribe","topic": "...", "chain":"solana"}
        msg = {"type": "subscribe", "topic": topic, "chain": CHAIN}
        self._send(msg)
        logging.info("[WS] sent subscribe %s", topic)

    def _on_message(self, _w, msg):
        try:
            data = json.loads(msg)
        except Exception:
            logging.debug("[WS] non-JSON message: %s", msg[:200])
            return

        # Optional: server acks / heartbeats
        t = data.get("type") or data.get("event") or ""
        if t in ("pong", "ping", "ack", "hello", "welcome"):
            return

        # Normalize possible payload shapes; we care about newly created tokens
        # Expect fields like: {type: "launchpad.created" | "token.created", data:{ mint, symbol, name, ...}}
        topic = data.get("type") or data.get("topic") or ""
        payload = data.get("data") or data

        if topic in ("launchpad.created", "token.created"):
            item = self._normalize(payload)
            if item and item.get("mint"):
                self.publish("scan.ws.token", {"topic": topic, "item": item})
                # Alert immediately (PoC). You can enrich later.
                self._alert(item, topic)
        elif topic:
            logging.debug("[WS] topic=%s payload=%s", topic, str(payload)[:300])

    def _normalize(self, p):
        # Try common field names; keep it minimal for PoC
        mint = p.get("mint") or p.get("address") or p.get("tokenAddress")
        sym = p.get("symbol") or "?"
        name = p.get("name") or "?"
        price = p.get("priceUsd") or p.get("price") or None
        return {"mint": mint, "symbol": sym, "name": name, "price": price}

    def _alert(self, it, topic):
        mint = it["mint"]
        link_be = f"https://birdeye.so/token/{mint}?chain=solana"
        link_pf = f"https://pump.fun/{mint}"
        msg = (
            f"🚀 *New Launchpad token*  _(via {topic})_\n"
            f"*{it.get('name', '?')}* ({it.get('symbol', '?')})\n"
            f"`{mint}`\n"
            f"[Birdeye]({link_be}) • [Pump.fun]({link_pf})"
        )
        self.notify(msg)


# --- singleton helpers ---
_ws_singleton = None


def get_ws(publish=None, notify=None):
    global _ws_singleton
    if _ws_singleton is None:
        _ws_singleton = BirdeyeWS(publish=publish, notify=notify)
    return _ws_singleton
