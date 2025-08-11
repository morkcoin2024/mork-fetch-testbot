# birdeye.py
import os, time, logging, httpx, threading, random
from collections import deque

BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SEC", "5"))

# --- BEGIN HOTFIX: Birdeye sort_by + pacing ---
_last_birdeye_call_ts = 0.0
# 1) make the global pace a bit gentler
_BIRDEYE_BASE_SPACING = int(os.getenv("BIRDEYE_MIN_SPACING_SEC", "15"))  # was 8
_MAX_RETRIES = 5

def _sleep_until_allowed():
    import time as _t
    global _last_birdeye_call_ts
    now = _t.time()
    delta = now - _last_birdeye_call_ts
    if delta < _BIRDEYE_BASE_SPACING:
        _t.sleep(_BIRDEYE_BASE_SPACING - delta)

def _birdeye_get(url, params, headers, max_retries=_MAX_RETRIES):
    import time as _t
    import random
    global _last_birdeye_call_ts
    attempt = 0
    while True:
        _sleep_until_allowed()
        r = httpx.get(url, headers=headers, params=params, timeout=12)
        _last_birdeye_call_ts = _t.time()

        # Respect 429 with exponential backoff + jitter
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            if ra:
                try:
                    wait = float(ra)
                except:
                    wait = 4.0
            else:
                wait = min(60.0, (2 ** max(1, attempt)) * 2.0) + random.uniform(0.2, 0.8)
            logging.warning("[SCAN] Birdeye 429; backing off %.2fs", wait)
            _t.sleep(wait)
            attempt += 1
            if attempt >= max_retries:
                raise httpx.HTTPStatusError("429 Too Many Requests", request=r.request, response=r)
            continue

        # Non-429 errors bubble up to caller
        r.raise_for_status()
        return r.json() or {}

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
            self.publish("scan.birdeye.error", {"err":"missing BIRDEYE_API_KEY"})
            return

        url = f"{API}/defi/tokenlist"

        # Try minimal params first (most compatible), then fallbacks
        param_variants = [
            {"chain": "solana", "offset": 0, "limit": 20},                                 # 1) no sort_by at all
            {"chain": "solana", "sort_type": "desc", "offset": 0, "limit": 20},            # 2) only sort_type
            {"chain": "solana", "sort_by": "createdTime", "sort_type": "desc", "offset": 0, "limit": 20},  # 3) camel
            {"chain": "solana", "sort_by": "created_at", "sort_type": "desc", "offset": 0, "limit": 20},   # 4) snake
        ]

        last_err = None
        data = None

        for i, params in enumerate(param_variants, start=1):
            try:
                data = _birdeye_get(url, params, HEADERS, max_retries=_MAX_RETRIES)
                break  # success
            except httpx.HTTPStatusError as e:
                sc = e.response.status_code
                body = e.response.text[:200] if e.response is not None else ""
                logging.warning(
                    "[SCAN] Birdeye status=%s (try %d/%d) url=%s params=%s body=%s",
                    sc, i, len(param_variants), str(getattr(e.request, "url", url)), params, body
                )
                last_err = f"HTTP {sc}"
                # 429 handling happens inside _birdeye_get, so we just move on to next variant for 400s, etc.
                continue
            except Exception as e:
                logging.warning("[SCAN] Birdeye tick error (try %d/%d): %s", i, len(param_variants), e)
                last_err = str(e)
                continue

        if data is None:
            # All variants failed
            self.publish("scan.birdeye.error", {"err": last_err or "unknown"})
            return

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