# birdeye.py
import os, time, logging, httpx, threading
from collections import deque

BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SEC", "5"))

API = "https://public-api.birdeye.so"
HEADERS = {"X-API-KEY": BIRDEYE_KEY, "accept":"application/json"}

class BirdeyeScanner:
    def __init__(self, publish):
        self.publish = publish
        self.running = False
        self.seen = deque(maxlen=5000)      # recent mints memory
        self._seen_set = set()
        self._thread = None
        self._stop_event = threading.Event()

    def _mark_seen(self, mint):
        if mint in self._seen_set: return False
        self.seen.append(mint); self._seen_set.add(mint)
        if len(self._seen_set) > self.seen.maxlen:
            # keep set bounded
            old = self.seen.popleft(); self._seen_set.discard(old)
        return True

    def start(self):
        if self.running: return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        self.publish("scan.birdeye.start", {"interval": SCAN_INTERVAL})
        logging.info("[SCAN] Birdeye scanner started (every %ss)", SCAN_INTERVAL)

    def stop(self):
        if not self.running: return
        self.running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.publish("scan.birdeye.stop", {})

    def status(self):
        return {
            "running": self.running,
            "interval": SCAN_INTERVAL,
            "seen_cache": len(self._seen_set),
            "thread_alive": self._thread.is_alive() if self._thread else False,
        }

    def _scan_loop(self):
        """Background scanning loop"""
        while self.running and not self._stop_event.is_set():
            try:
                self.tick()
                self._stop_event.wait(SCAN_INTERVAL)
            except Exception as e:
                logging.error("[SCAN] Background scan error: %s", e)
                self.publish("scan.birdeye.error", {"err": f"background_scan: {e}"})
                self._stop_event.wait(SCAN_INTERVAL)

    def tick(self):
        if not self.running: return
        if not BIRDEYE_KEY:
            self.publish("scan.birdeye.error", {"err":"missing BIRDEYE_API_KEY"})
            return
        try:
            # recent tokens (Birdeye)
            url = f"{API}/public/token/solana/recent"
            r = httpx.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            data = r.json() or {}
            items = data.get("data", []) or data.get("tokens", []) or []
            new_tokens = []
            for it in items:
                mint = it.get("address") or it.get("mint")
                if not mint: continue
                if self._mark_seen(mint):
                    new_tokens.append({
                        "mint": mint,
                        "symbol": it.get("symbol") or "?",
                        "name": it.get("name") or "?",
                        "price": it.get("priceUsd") or it.get("price") or None,
                    })
            if new_tokens:
                self.publish("scan.birdeye.new", {"count": len(new_tokens), "items": new_tokens[:10]})
        except Exception as e:
            logging.warning("[SCAN] Birdeye tick error: %s", e)
            self.publish("scan.birdeye.error", {"err": str(e)})

scanner_singleton = None
def get_scanner(publish):
    global scanner_singleton
    if scanner_singleton is None:
        scanner_singleton = BirdeyeScanner(publish)
    return scanner_singleton