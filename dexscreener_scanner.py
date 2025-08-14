# dexscreener_scanner.py
import os, time, logging, httpx, threading
from collections import deque
from datetime import datetime, timezone

# DexScreener API - Using a working endpoint for Solana token data
# Note: The old /latest/dex/pairs/solana endpoint is deprecated
DS_API = "https://api.dexscreener.com/latest/dex/search?q=sol"
SCAN_INTERVAL = int(os.getenv("DS_SCAN_INTERVAL_SEC", "15"))

UA = "Mozilla/5.0 (X11; Linux x86_64) MorkFetchBot/1.0"
HEADERS = {"accept": "application/json", "user-agent": UA}

def _now_ms() -> int:
    return int(time.time() * 1000)

class DexScreenerScanner:
    """
    Polls Dexscreener Solana pairs. We alert on pairs created in the last window
    (default 2 minutes) and dedupe by mint.
    """
    def __init__(self, interval_sec=None, publish=None, recent_window_sec=180):
        self.interval = max(10, int(interval_sec or SCAN_INTERVAL))
        self.publish = publish or (lambda *_: None)
        self.window_ms = int(recent_window_sec * 1000)
        self.running = False
        self._stop = threading.Event()
        self._thread = None
        self._seen = deque(maxlen=8000)
        self._seen_set = set()

    def _mark_seen(self, mint: str) -> bool:
        if mint in self._seen_set:
            return False
        self._seen.append(mint)
        self._seen_set.add(mint)
        if self._seen.maxlen and len(self._seen) >= self._seen.maxlen:
            old = self._seen.popleft()
            self._seen_set.discard(old)
        return True

    def start(self):
        if self.running: return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.publish("scan.dexscreener.start", {"interval": self.interval})
        logging.info("[DS] Dexscreener scanner started (every %ss)", self.interval)

    def stop(self):
        if not self.running: return
        self.running = False
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.publish("scan.dexscreener.stop", {})

    def status(self):
        return {
            "running": self.running,
            "interval": self.interval,
            "seencache": len(self._seen_set),
            "threadalive": self._thread.is_alive() if self._thread else False,
            "window_sec": self.window_ms // 1000,
        }

    def _loop(self):
        while self.running and not self._stop.is_set():
            try:
                self.tick()
            except Exception as e:
                logging.warning("[DS] tick error: %s", e)
                self.publish("scan.dexscreener.error", {"err": str(e)})
            self._stop.wait(self.interval)

    def tick(self):
        now = _now_ms()
        try:
            r = httpx.get(DS_API, headers=HEADERS, timeout=12)
            r.raise_for_status()
            data = r.json() or {}
            pairs = data.get("pairs", []) or []
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # DexScreener endpoint may be down, skip this tick gracefully
                logging.debug("[DS] API endpoint unavailable (404), skipping tick")
                return  # Exit early on 404
            raise

        new_items = []
        for p in pairs:
            # createdAt is milliseconds
            created = p.get("pairCreatedAt") or 0
            if not created or (now - created) > self.window_ms:
                continue

            base = (p.get("baseToken") or {})
            quote = (p.get("quoteToken") or {})
            base_mint = base.get("address") or ""
            # Prefer mint over pair address for dedupe
            key = base_mint or p.get("pairAddress") or p.get("url", "")
            if not key or not self._mark_seen(key):
                continue

            item = {
                "mint": base_mint,
                "symbol": base.get("symbol") or "?",
                "name": base.get("name") or "?",
                "price": (p.get("priceUsd") or p.get("priceNative")),
                "liq": (p.get("liquidity") or {}).get("usd"),
                "created_ms": created,
            }
            new_items.append(item)
            
            # Publish NEW_TOKEN event for each new item
            try:
                from app import _normalize_token
                ev = _normalize_token(p, "dexscreener")
                self.publish("NEW_TOKEN", ev)
            except Exception as norm_e:
                logging.warning("[DS] NEW_TOKEN publish failed: %s", norm_e)

        if new_items:
            self.publish("scan.dexscreener.new", {
                "count": len(new_items),
                "items": new_items[:10]
            })
            logging.info("[DS] new pairs: %d (window %ss)", len(new_items), self.window_ms//1000)
            
            # Send alerts for each new token
            for item in new_items:
                self._send_alert(item)
        else:
            logging.info("[DS] no new pairs in last %ss", self.window_ms//1000)

    def _send_alert(self, item):
        """Send Telegram alert for new DexScreener token"""
        mint = item.get("mint", "")
        name = item.get("name", "?")
        symbol = item.get("symbol", "?")
        price = item.get("price", 0)
        liq = item.get("liq", 0)
        
        # Format liquidity
        liq_str = f"${liq:,.0f}" if liq and liq > 0 else "N/A"
        price_str = f"${price:.8f}" if price and price > 0 else "N/A"
        
        text = (
            f"🔍 *DexScreener — New Pair*\n"
            f"*{name}* ({symbol})\n"
            f"Price: {price_str}\n"
            f"Liquidity: {liq_str}\n"
            f"`{mint}`\n"
            f"[DexScreener](https://dexscreener.com/solana/{mint}) • [Pump.fun](https://pump.fun/{mint})"
        )
        
        try:
            # Import and use the notification system
            from app import send_admin_md
            send_admin_md(text)
            logging.info("[DS] Alert sent: %s (%s) %s", name, symbol, mint)
        except Exception as e:
            logging.warning("[DS] Alert send failed: %s", e)

_scanner_singleton = None
def get_scanner(publish=None):
    global _scanner_singleton
    if _scanner_singleton is None:
        _scanner_singleton = DexScreenerScanner(publish=publish)
    return _scanner_singleton

# Direct singleton for immediate use
ds_client = None

def get_ds_client():
    global ds_client
    if ds_client is None:
        from eventbus import publish
        ds_client = DexScreenerScanner(publish=publish)
    return ds_client

# Initialize client
ds_client = get_ds_client()