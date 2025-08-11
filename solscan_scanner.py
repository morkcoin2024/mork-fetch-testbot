# solscan_scanner.py
import os, time, logging
from typing import List, Dict
import httpx

log = logging.getLogger(__name__)

class SolscanScanner:
    """
    Optional Solscan scanner - only runs if SOLSCAN_API_KEY is provided.
    Kept dormant by default as requested.
    """
    def __init__(self, notify_fn, cache_limit:int=8000, interval_sec:int=10):
        self.notify = notify_fn
        self.interval = int(os.getenv("SCAN_INTERVAL_SEC", str(interval_sec)))
        self.session = httpx.Client(timeout=15)
        self.api_key = os.getenv("SOLSCAN_API_KEY")
        self.enabled = bool(self.api_key)  # Only enabled if API key provided
        self.seen: set[str] = set()
        self.cache_limit = cache_limit
        self.running = False

    def _maybe_trim_cache(self):
        if len(self.seen) > self.cache_limit:
            drop = max(1000, self.cache_limit // 4)
            for _ in range(drop):
                self.seen.pop()

    def _fetch_tokens(self) -> List[Dict]:
        if not self.api_key:
            return []
        
        # Placeholder for Solscan API integration
        # This would be implemented when SOLSCAN_API_KEY is provided
        headers = {
            "token": self.api_key,
            "User-Agent": "mork-fetch/1.0"
        }
        
        # Example endpoint - would need actual Solscan API documentation
        # url = "https://public-api.solscan.io/tokens/latest"
        # r = self.session.get(url, headers=headers)
        # r.raise_for_status()
        # data = r.json()
        
        # For now, return empty until API key is provided and endpoint is configured
        return []

    def tick(self):
        if not self.enabled:
            return 0, 0
            
        try:
            all_tokens = self._fetch_tokens()
        except Exception as e:
            log.warning("[SCAN] Solscan fetch error: %s", e)
            return 0, 0

        new_items = []
        for t in all_tokens[:1000]:  # safety cap
            mint = t.get("mint", t.get("address", ""))
            if mint and mint not in self.seen:
                self.seen.add(mint)
                new_items.append({
                    "mint": mint,
                    "name": t.get("name", ""),
                    "symbol": t.get("symbol", ""),
                    "decimals": t.get("decimals", 9),
                    "source": "solscan",
                })

        if new_items:
            announced = new_items[:10]
            self.notify(announced, title="New tokens (Solscan)")

        self._maybe_trim_cache()
        return len(all_tokens), len(new_items)

    def start(self):
        if not self.enabled:
            log.info("[SCAN] Solscan scanner dormant (no SOLSCAN_API_KEY)")
            return
        self.running = True
        log.info("[SCAN] Solscan scanner started (every %ss)", self.interval)

    def stop(self):
        self.running = False
        try: self.session.close()
        except: pass
        log.info("[SCAN] Solscan scanner stopped")