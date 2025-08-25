# jupiter_scan.py
import logging
import os

import httpx

log = logging.getLogger(__name__)

JUP_ALL_URL = "https://token.jup.ag/all?includeCommunity=true"


class JupiterScan:
    """
    Keyless scanner. We treat a token as 'new' if its mint hasn't been seen
    by THIS process yet. We don't rely on timestamps since the endpoint
    doesn't publish one.
    """

    def __init__(self, notify_fn, cache_limit: int = 8000, interval_sec: int = 8):
        self.notify = notify_fn  # callable(list[dict]) -> None
        self.interval = int(os.getenv("SCAN_INTERVAL_SEC", str(interval_sec)))
        self.session = httpx.Client(timeout=15)
        self.enabled = os.getenv("FEATURE_JUPITER", "on").lower() == "on"
        self.seen: set[str] = set()
        self.cache_limit = cache_limit
        self.running = False

    def _maybe_trim_cache(self):
        # simple soft trim to avoid unbounded growth
        if len(self.seen) > self.cache_limit:
            # drop ~25% oldest by random sampling (cheap & good enough)
            drop = max(1000, self.cache_limit // 4)
            for _ in range(drop):
                self.seen.pop()

    def _fetch_all(self) -> list[dict]:
        r = self.session.get(JUP_ALL_URL, headers={"User-Agent": "mork-fetch/1.0"})
        r.raise_for_status()
        data = r.json()
        # Response is a list of token dicts. We'll normalize to {mint, name, symbol, decimals}
        out = []
        for t in data:
            mint = t.get("address") or t.get("mint")  # jup uses 'address'
            if not mint:
                continue
            out.append(
                {
                    "mint": mint,
                    "name": t.get("name") or "",
                    "symbol": t.get("symbol") or "",
                    "decimals": t.get("decimals", 0),
                    "source": "jupiter",
                }
            )
        return out

    def tick(self):
        if not self.enabled:
            return 0, 0
        try:
            all_tokens = self._fetch_all()
        except Exception as e:
            log.warning("[SCAN] Jupiter fetch error: %s", e)
            return 0, 0

        new_items = []
        for t in all_tokens[:2000]:  # safety cap
            mint = t["mint"]
            if mint not in self.seen:
                self.seen.add(mint)
                new_items.append(t)

                # Publish NEW_TOKEN event
                if hasattr(self, "publish") and callable(getattr(self, "publish", None)):
                    try:
                        from app import _normalize_token

                        ev = _normalize_token(t, "jupiter")
                        self.publish("NEW_TOKEN", ev)
                    except Exception as norm_e:
                        log.warning("[JUPITER] NEW_TOKEN publish failed: %s", norm_e)

        # heuristic: only announce the first handful per tick to avoid firehose
        announced = new_items[:10]
        if announced:
            self.notify(announced, title="New tokens (Jupiter)")

        self._maybe_trim_cache()
        return len(all_tokens), len(new_items)

    def start(self):
        self.running = True
        log.info("[SCAN] Jupiter scanner started (every %ss)", self.interval)

    def stop(self):
        self.running = False
        try:
            self.session.close()
        except:
            pass
        log.info("[SCAN] Jupiter scanner stopped")

    def status(self):
        return {"enabled": self.enabled, "running": self.running}


# Use a safer class name that matches the existing pattern
class JupiterScanner(JupiterScan):
    pass


# Global scanner instance
scanner = JupiterScanner(lambda *args, **kwargs: None)  # Default no-op notify function


def get_scanner():
    """Get the global Jupiter scanner instance"""
    return scanner


# Register scanner after imports to avoid circular import
def _register_scanner():
    try:
        from app import SCANNERS

        SCANNERS["jupiter"] = scanner
    except ImportError:
        pass  # SCANNERS not available yet, will be registered later


_register_scanner()
