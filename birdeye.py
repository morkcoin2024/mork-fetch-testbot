# birdeye.py
import os, time, logging, httpx, threading, random
from collections import deque
from birdeye_ws import is_ws_connected

# --- config/env ---
BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SEC", "6"))  # default 6s to be gentler on rate limit
API = "https://public-api.birdeye.so"
HEADERS = {
    "X-API-KEY": BIRDEYE_KEY,
    "accept": "application/json",
}

# --- mode & de-dupe (global) ---
SCAN_MODE = "strict"   # "strict" | "all"
SEEN_MINTS = set()     # process_birdeye_items() de-dupe for current run

def set_scan_mode(mode: str):
    global SCAN_MODE, scanner_singleton
    SCAN_MODE = "all" if str(mode).lower() == "all" else "strict"
    logging.info("[SCAN] Scan mode set to %s", SCAN_MODE)
    from eventbus import publish
    publish("scan.mode", {"mode": SCAN_MODE})
    # propagate to live scanner if running
    if scanner_singleton:
        scanner_singleton.mode = SCAN_MODE
    try:
        from eventbus import publish
        publish("scan.mode", {"mode": SCAN_MODE})
    except Exception:
        pass

def _passes_filters(tok: dict) -> bool:
    """Return True if token should alert, based on current mode."""
    if SCAN_MODE == "all":
        return True  # promiscuous mode: alert on everything we see

    # STRICT MODE GATES (customize if needed)
    # examples (leave permissive for now while proving POC):
    # if tok.get("liquidity", 0) < 1000: return False
    # if not tok.get("is_pumpfun"): return False
    # if tok.get("mcap", 0) < 5_000: return False
    return True

def process_birdeye_items(items: list, notify):
    """Best-effort alert builder for items directly from Birdeye scanner."""
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
            try:
                notify(msg)
            except Exception as e:
                logging.warning("[SCAN] notify failed: %s", e)
    logging.info("[SCAN] birdeye processed: %s items, %s alerts", len(items), alerts)

# --- HTTP helpers ---

def _normalize_items(data: dict) -> list:
    """Birdeye responses vary by plan; normalize to a list of token dicts."""
    items = (
        (data or {}).get("data", {}).get("tokens")
        or (data or {}).get("data", [])
        or (data or {}).get("tokens", [])
        or []
    )
    out = []
    for it in items:
        mint = it.get("address") or it.get("mint") or it.get("tokenAddress")
        if not mint:
            continue
        out.append({
            "mint": mint,
            "symbol": it.get("symbol") or "?",
            "name": it.get("name") or "?",
            "price": it.get("priceUsd") or it.get("price") or None,
        })
    return out

def _get_tokenlist() -> list:
    """Clean HTTP GET to Birdeye tokenlist endpoint - NO sort_by parameters."""
    url = f"{API}/defi/tokenlist"
    params = {
        "chain": "solana", 
        "offset": 0,
        "limit": 20,
    }
    
    r = httpx.get(url, headers=HEADERS, params=params, timeout=12)
    if r.status_code == 429:
        delay = 0.8 + random.random() * 0.7  # 0.8-1.5s jitter
        logging.warning("[SCAN] Birdeye 429; backing off %.2fs", delay)
        time.sleep(delay)
        r = httpx.get(url, headers=HEADERS, params=params, timeout=12)
    
    r.raise_for_status()
    data = r.json() or {}
    return _normalize_items(data)

# --- scanner class ---

class BirdeyeScanner:
    def __init__(self, interval_sec=None, publish=None):
        self.interval = max(5, int(interval_sec or SCAN_INTERVAL))
        self.publish = publish or (lambda _t, _d: None)
        self.running = False
        self.seen = deque(maxlen=5000)  # recent mints memory
        self._seen_set = set()
        self._thread = None
        self._stop_event = threading.Event()
        # NEW: keep the latest normalized items so /scan_probe can show them
        self.last_items = deque(maxlen=200)
        self.mode = SCAN_MODE

    def _mark_seen(self, mint):
        if mint in self._seen_set:
            return False
        self.seen.append(mint)
        self._seen_set.add(mint)
        # keep set bounded
        if self.seen.maxlen and len(self._seen_set) > self.seen.maxlen:
            old = self.seen.popleft()
            self._seen_set.discard(old)
        return True

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        self.publish("scan.birdeye.start", {"interval": self.interval})
        logging.info("[SCAN] Birdeye scanner started (every %ss)", self.interval)

    def stop(self):
        if not self.running:
            return
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
        while self.running and not self._stop_event.is_set():
            try:
                self.tick()
                # wait with ability to break early
                self._stop_event.wait(self.interval)
            except Exception as e:
                logging.error("[SCAN] Background scan error: %s", e)
                try:
                    self.publish("scan.birdeye.error", {"err": f"background_scan: {e}"})
                except Exception:
                    pass
                self._stop_event.wait(self.interval)

    def _get_tokenlist(self, limit=20, offset=0):
        """
        Birdeye clean endpoint: NO sort_by. Keep this the single source of truth
        for the tokenlist call so legacy paths can't reintroduce params.
        """
        url = f"{API}/defi/tokenlist"
        params = {"chain": "solana", "offset": int(offset or 0), "limit": int(limit or 20)}
        return httpx.get(url, headers=HEADERS, params=params, timeout=12)

    def tick(self):
        if not self.running:
            return
        if not BIRDEYE_KEY:
            self.publish("scan.birdeye.error", {"err": "missing BIRDEYE_API_KEY"})
            return

        tries = 3
        backoff = 0.8 + random.random() * 0.7  # ~0.8–1.5s
        last_err = None

        while tries > 0:
            try:
                r = self._get_tokenlist(limit=20, offset=0)  # ✅ no sort_by ever
                if r.status_code == 429:
                    logging.warning("[SCAN] Birdeye 429; backing off %.2fs", backoff)
                    time.sleep(backoff)
                    backoff *= 1.6
                    tries -= 1
                    continue

                r.raise_for_status()
                data = r.json() or {}
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
                    self.publish("scan.birdeye.new", {
                        "count": len(new_tokens),
                        "items": new_tokens[:10]
                    })

                logging.info("[SCAN] Birdeye tick ok: %s items, %s new", len(items), len(new_tokens))
                return

            except httpx.HTTPStatusError as e:
                logging.warning(
                    "[SCAN] Birdeye status=%s url=%s body=%s",
                    e.response.status_code,
                    str(e.request.url),
                    e.response.text[:200]
                )
                last_err = e
                time.sleep(backoff)
                backoff *= 1.6
                tries -= 1

            except Exception as e:
                logging.warning("[SCAN] Birdeye tick error: %s", e)
                last_err = e
                time.sleep(backoff)
                backoff *= 1.6
                tries -= 1

        # Out of retries
        self.publish("scan.birdeye.error", {"err": str(last_err) if last_err else "unknown"})

    def run_forever(self):
        while True:
            try:
                self.tick()
                time.sleep(self.interval)
            except Exception as e:
                logging.error("[SCAN] Run forever error: %s", e)
                time.sleep(self.interval)

# --- singleton accessor ---
scanner_singleton = None
def get_scanner(publish):
    global scanner_singleton
    if scanner_singleton is None:
        scanner_singleton = BirdeyeScanner(interval_sec=SCAN_INTERVAL, publish=publish)
    return scanner_singleton

# convenience helpers for app.py commands
def peek_last(n: int = 10):
    sc = get_scanner(lambda *_: None)
    n = max(1, min(50, int(n or 10)))
    return list(sc.last_items)[-n:]

def current_mode():
    sc = scanner_singleton
    return sc.mode if sc else SCAN_MODE

# --- one-shot probe for Telegram (/birdeye_probe) ---
def birdeye_probe_once(limit=20):
    """
    One-shot fetch of newest tokens (best-effort).
    Returns: {"ok": True/False, "err": str|None, "items": [ {mint,symbol,name,price} ... ]}
    """
    if not BIRDEYE_KEY:
        return {"ok": False, "err": "missing BIRDEYE_API_KEY", "items": []}
    try:
        items = _get_tokenlist()  # Use clean helper - NO sort_by
        return {"ok": True, "err": None, "items": items[:5]}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return {"ok": False, "err": "429 Too Many Requests", "items": []}
        return {"ok": False, "err": f"{e.response.status_code} {e.response.text[:120]}", "items": []}
    except Exception as e:
        return {"ok": False, "err": str(e), "items": []}