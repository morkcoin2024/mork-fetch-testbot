# birdeye.py
import os, time, logging, httpx, threading, random
from collections import deque

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
    """Switch between 'strict' and 'all' scanning."""
    global SCAN_MODE
    SCAN_MODE = "all" if str(mode).lower() == "all" else "strict"
    logging.info("[SCAN] Scan mode set to %s", SCAN_MODE)
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

def _request_newest(limit: int, sort_by: str) -> list:
    """Perform a single HTTP request with the given sort_by."""
    url = f"{API}/defi/tokenlist"
    params = {
        "chain": "solana",
        "sort_by": sort_by,
        "sort_type": "desc",
        "offset": 0,
        "limit": max(1, min(50, int(limit))),
    }
    r = httpx.get(url, headers=HEADERS, params=params, timeout=12)
    r.raise_for_status()
    return _normalize_items(r.json())

def _request_with_fallbacks(limit: int) -> list:
    """
    Try likely sort_by keys with helpful logging:
    createdTime -> createdAt -> created_at
    """
    order = ["createdTime", "createdAt", "created_at"]
    last_err = None

    for idx, key in enumerate(order):
        try:
            return _request_newest(limit, key)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            body = e.response.text[:200]
            logging.warning("[SCAN] Birdeye status=%s sort_by=%s body=%s", code, key, body)
            if code == 429:
                # back off briefly; keep it tiny to avoid blocking loop
                delay = 0.8 + random.uniform(0.0, 0.4)
                logging.warning("[SCAN] Birdeye 429; backing off %.2fs", delay)
                time.sleep(delay)
                last_err = e
                continue
            if code == 400 and idx < len(order) - 1:
                # try next variant
                logging.warning("[SCAN] 400 on sort_by=%s, retrying with %s", key, order[idx + 1])
                last_err = e
                continue
            # other codes: bail
            raise
        except Exception as e:
            last_err = e
            logging.warning("[SCAN] Birdeye tick error: %s", e)

    # if we get here, nothing worked
    if last_err:
        raise last_err
    return []

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

    def tick(self):
        if not self.running: return
        if not BIRDEYE_KEY:
            self.publish("scan.birdeye.error", {"err":"missing BIRDEYE_API_KEY"})
            return

        # we'll try without sort_by first (Birdeye sometimes rejects formats on free tier)
        def _do_req(params):
            url = f"{API}/defi/tokenlist"
            r = httpx.get(url, headers=HEADERS, params=params, timeout=12)
            r.raise_for_status()
            return r.json() or {}

        try:
            # primary attempt: NO sort_by (default order is recent enough)
            params = {
                "chain": "solana",
                "offset": 0,
                "limit": 20,
                # no sort_by at all (server sorts by recency)
            }
            data = _do_req(params)

        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            body = (e.response.text or "")[:200]
            logging.warning("[SCAN] Birdeye status=%s url=%s body=%s",
                            code, str(e.request.url), body)

            # 429 – rate limit: back off and bail this tick
            if code == 429:
                backoff = 1.0
                logging.warning("[SCAN] Birdeye 429; backing off %.2fs", backoff)
                time.sleep(backoff)
                self.publish("scan.birdeye.error", {"err": "HTTP 429"})
                return

            # 400 – retry once with a guessy sort_by, then give up
            if code == 400:
                try:
                    logging.warning("[SCAN] 400 without sort_by, retrying with sort_by=createdAt")
                    params = {
                        "chain": "solana",
                        "sort_by": "createdAt",
                        "sort_type": "desc",
                        "offset": 0,
                        "limit": 20,
                    }
                    data = _do_req(params)
                except httpx.HTTPStatusError as e2:
                    code2 = e2.response.status_code
                    body2 = (e2.response.text or "")[:200]
                    logging.warning("[SCAN] Birdeye status=%s sort_by=createdAt body=%s", code2, body2)
                    self.publish("scan.birdeye.error", {"err": f"HTTP {code2}"})
                    return
            else:
                self.publish("scan.birdeye.error", {"err": f"HTTP {code}"})
                return
        except Exception as e:
            logging.warning("[SCAN] Birdeye tick error: %s", e)
            self.publish("scan.birdeye.error", {"err": str(e)})
            return

        # ---- normalize + local sort (by any created_* field if present) ----
        items = (
            data.get("data", {}).get("tokens")
            or data.get("data", [])
            or data.get("tokens", [])
            or []
        )

        # locally sort by createdAt/created_at/createdTime desc if field exists, else leave order
        def key_created(x):
            return x.get("createdAt") or x.get("created_at") or x.get("createdTime") or 0
        try:
            items = sorted(items, key=key_created, reverse=True)
        except Exception:
            pass  # if fields are heterogeneous, keep server order

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

# --- one-shot probe for Telegram (/birdeye_probe) ---
def birdeye_probe_once(limit=20):
    """
    One-shot fetch of newest tokens (best-effort).
    Returns: {"ok": True/False, "err": str|None, "items": [ {mint,symbol,name,price} ... ]}
    """
    if not BIRDEYE_KEY:
        return {"ok": False, "err": "missing BIRDEYE_API_KEY", "items": []}
    try:
        items = _request_with_fallbacks(limit=max(1, min(50, int(limit))))
        return {"ok": True, "err": None, "items": items[:5]}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return {"ok": False, "err": "429 Too Many Requests", "items": []}
        return {"ok": False, "err": f"{e.response.status_code} {e.response.text[:120]}", "items": []}
    except Exception as e:
        return {"ok": False, "err": str(e), "items": []}