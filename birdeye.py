# birdeye.py
import os, time, logging, httpx, threading
from collections import deque

BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SEC", "5"))

# --- BEGIN PATCH ---
# top-level globals (near other config)
SCAN_MODE = "strict"   # "strict" | "all"
SEEN_MINTS = set()     # in-memory de-dupe for this run

def set_scan_mode(mode: str):
    global SCAN_MODE
    SCAN_MODE = "all" if str(mode).lower() == "all" else "strict"
    logging.info("[SCAN] Scan mode set to %s", SCAN_MODE)
    from eventbus import publish
    publish("scan.mode", {"mode": SCAN_MODE})

def _passes_filters(tok: dict) -> bool:
    """Return True if token should alert, based on current mode."""
    if SCAN_MODE == "all":
        return True  # no gates in promiscuous mode

    # ---- existing strict filters stay here ----
    # examples (keep your current logic):
    # if tok.get("liquidity", 0) < 1000: return False
    # if not tok.get("is_pumpfun"): return False
    # if tok.get("mcap", 0) < 5_000: return False
    return True

def process_birdeye_items(items: list, notify):
    """items: list of tokens from Birdeye. notify(m) sends a telegram message."""
    alerts = 0
    for it in items:
        mint = it.get("mint") or it.get("address") or it.get("tokenAddress")
        if not mint:
            continue
        if mint in SEEN_MINTS:
            continue
        SEEN_MINTS.add(mint)

        if _passes_filters(it):
            alerts += 1
            # Build a simple alert (adjust fields to your payload)
            name = it.get("name") or "?"
            sym  = it.get("symbol") or "?"
            link_be = f"https://birdeye.so/token/{mint}?chain=solana"
            link_pf = f"https://pump.fun/{mint}"
            msg = (
                f"🔔 *New token detected*\n"
                f"*{name}* ({sym})\n"
                f"`{mint}`\n"
                f"[Birdeye]({link_be}) • [Pump.fun]({link_pf})"
            )
            notify(msg)
    logging.info("[SCAN] birdeye processed: %s items, %s alerts", len(items), alerts)
# --- END PATCH ---

API = "https://public-api.birdeye.so"
HEADERS = {"X-API-KEY": BIRDEYE_KEY, "accept":"application/json"}

class BirdeyeScanner:
    def __init__(self, interval_sec=None, publish=None):
        self.interval = max(5, int(interval_sec or SCAN_INTERVAL))
        self.publish = publish or (lambda _t, _d: None)
        self.running = False
        self.seen = deque(maxlen=5000)      # recent mints memory
        self._seen_set = set()
        self._thread = None
        self._stop_event = threading.Event()

    def _mark_seen(self, mint):
        if mint in self._seen_set: return False
        self.seen.append(mint); self._seen_set.add(mint)
        if self.seen.maxlen and len(self._seen_set) > self.seen.maxlen:
            # keep set bounded
            old = self.seen.popleft(); self._seen_set.discard(old)
        return True

    def start(self):
        if self.running: return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        self.publish("scan.birdeye.start", {"interval": self.interval})
        logging.info("[SCAN] Birdeye scanner started (every %ss)", self.interval)

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
            "interval": self.interval,
            "seen_cache": len(self._seen_set),
            "thread_alive": self._thread.is_alive() if self._thread else False,
        }

    def _scan_loop(self):
        """Background scanning loop"""
        while self.running and not self._stop_event.is_set():
            try:
                self.tick()
                self._stop_event.wait(self.interval)
            except Exception as e:
                logging.error("[SCAN] Background scan error: %s", e)
                self.publish("scan.birdeye.error", {"err": f"background_scan: {e}"})
                self._stop_event.wait(self.interval)

    def tick(self):
        if not self.running:
            return
        if not BIRDEYE_KEY:
            self.publish("scan.birdeye.error", {"err": "missing BIRDEYE_API_KEY"})
            return

        url = f"{API}/defi/tokenlist"

        def _fetch(params):
            r = httpx.get(url, headers=HEADERS, params=params, timeout=12)
            r.raise_for_status()
            return r.json() or {}

        try:
            # Primary attempt (Birdeye expects createdAt; include chain=solana)
            params = {
                "chain": "solana",
                "sort_by": "createdAt",
                "sort_type": "desc",
                "offset": 0,
                "limit": 50,
            }
            try:
                data = _fetch(params)
            except httpx.HTTPStatusError as e:
                # Fallback if Birdeye tweaks the field name again
                if e.response.status_code == 400 and "sort_by" in e.response.text:
                    logging.warning("[SCAN] Birdeye 400 on sort_by=%s, retrying with created_at", params["sort_by"])
                    params["sort_by"] = "created_at"
                    data = _fetch(params)
                else:
                    raise

            # Normalize payload across variants
            items = (
                data.get("data", {}).get("tokens")
                or data.get("data", [])
                or data.get("tokens", [])
                or []
            )

            new_tokens = []
            for it in items:
                mint = it.get("address") or it.get("mint") or it.get("tokenAddress")
                if not mint:
                    continue
                if self._mark_seen(mint):
                    new_tokens.append({
                        "mint": mint,
                        "symbol": it.get("symbol") or "?",
                        "name": it.get("name") or "?",
                        "price": it.get("priceUsd") or it.get("price") or None,
                    })

            if new_tokens:
                self.publish("scan.birdeye.new", {"count": len(new_tokens), "items": new_tokens[:10]})
            logging.info("[SCAN] Birdeye tick ok: %s items, %s new", len(items), len(new_tokens))

        except httpx.HTTPStatusError as e:
            logging.warning(
                "[SCAN] Birdeye status=%s url=%s body=%s",
                e.response.status_code, str(e.request.url), e.response.text[:200]
            )
            self.publish("scan.birdeye.error", {"err": f"HTTP {e.response.status_code}"})
        except Exception as e:
            logging.warning("[SCAN] Birdeye tick error: %s", e)
            self.publish("scan.birdeye.error", {"err": str(e)})

    def run_forever(self):
        """Run scanner forever in current thread (for manual threading)"""
        while True:
            try:
                self.tick()
                time.sleep(self.interval)
            except Exception as e:
                logging.error("[SCAN] Run forever error: %s", e)
                time.sleep(self.interval)

scanner_singleton = None
def get_scanner(publish):
    global scanner_singleton
    if scanner_singleton is None:
        scanner_singleton = BirdeyeScanner(interval_sec=SCAN_INTERVAL, publish=publish)
    return scanner_singleton