# solscan.py
# Minimal, production-safe Solscan Pro scanner for the Mork F.E.T.C.H bot.
# - Pulls "new tokens / recently listed" from Solscan Pro.
# - Safe header handling (supports both 'token' and 'X-API-KEY' styles).
# - Retries + jitter. Returns normalized token dicts the rest of the bot expects.

from __future__ import annotations
import os, time, random, logging
from typing import List, Dict, Any, Optional

import httpx

# Use root logger to ensure logs appear in /a_logs_tail ring buffer
log = logging.getLogger()
# Also ensure any named logger propagates to root
_named_log = logging.getLogger("solscan")
_named_log.propagate = True
_named_log.setLevel(logging.INFO)

_DEFAULT_BASE = os.getenv("SOLSCAN_BASE_URL", "https://pro-api.solscan.io")
_TIMEOUT = 12.0

# Candidate endpoints to try (Solscan Pro has a few surfaces that expose new listings).
# We try them in order until we get a 200 with a list-shaped payload.
# Updated for Solscan Pro API v2.0 (2025)
_CANDIDATE_PATHS = [
    # v2.0 endpoints (primary) - some don't accept limit param
    ("/v2.0/token/trending", "data"),           # trending tokens with market activity - WORKS!
    ("/v2.0/token/latest", None),               # newest tokens created on Solana - no limit param
    ("/v2.0/token/list", None),                 # token list sortable by creation date - no limit param  
    # v1 fallbacks with chain param
    ("/v1/token/list", "data"),                 # v1 token list
    ("/v1/token/meta", "data"),                 # token metadata
    ("/v1/market/token/trending", "data"),      # v1 trending
]

def _build_headers(api_key: str) -> Dict[str, str]:
    # Solscan Pro usually accepts header "token: <API_KEY>".
    # Some gateways also accept "X-API-KEY" or "Authorization: Bearer <key>".
    return {
        "token": api_key,
        "X-API-KEY": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "mork-fetch-bot/1.0",
    }

class SolscanScanner:
    def __init__(self,
                 api_key: str,
                 base_url: str = _DEFAULT_BASE,
                 network: str = "solana",
                 limit: int = 20) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.network = network
        self.limit = max(1, min(limit, 100))
        self._running = False
        self._last_ok = None
        self._last_err = None
        # Cache for deduplication
        self.seen = set()
        self.interval = 10  # Default scan interval in seconds
        # Enhanced tracking for /solscanstats
        self._last_tick_ts = None
        self._requests_ok = 0
        self._requests_err = 0
        self._last_status_code = None
        # Use HTTP/2 if available, fallback to HTTP/1.1
        try:
            self._client = httpx.Client(timeout=_TIMEOUT, http2=True)
        except Exception:
            self._client = httpx.Client(timeout=_TIMEOUT, http2=False)

    # --- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        log.info("[SOLSCAN] start called; enabled=%s", self.enabled)
        self._running = True
        log.info("[SOLSCAN] started base=%s keylen=%d", self.base_url, len(self.api_key or ""))

    def stop(self) -> None:
        self._running = False
        try:
            self._client.close()
        except Exception:
            pass
        log.info("[SOLSCAN] scanner stopped")

    @property
    def running(self) -> bool:
        return self._running
    
    @property
    def enabled(self) -> bool:
        """Check if scanner is enabled (has valid API key)"""
        return bool(self.api_key and self.api_key.strip())
    
    @property
    def key(self) -> str:
        """Return API key (for status checking)"""
        return self.api_key
    
    def status(self) -> Dict[str, Any]:
        """Return current scanner status"""
        return {
            "running": self._running,
            "enabled": self.enabled,
            "api_key": bool(self.api_key),
            "seen_cache": len(self.seen),
            "interval": self.interval,
            "last_ok": self._last_ok,
            "last_err": self._last_err,
            "base_url": self.base_url,
            "last_tick_ts": self._last_tick_ts,
            "requests_ok": self._requests_ok,
            "requests_err": self._requests_err,
            "last_status": self._last_status_code
        }
    
    def tick(self) -> tuple[int, int]:
        """Scanner tick method for main scanning loop integration"""
        if not self._running:
            return 0, 0
        
        self._last_tick_ts = time.time()
        log.info("[SOLSCAN] tick base=%s seen=%d", self.base_url, len(self.seen))
        try:
            tokens = self.fetch_new_tokens()
            new_count = 0
            for token in tokens:
                addr = token.get('address', '')
                if addr and addr not in self.seen:
                    self.seen.add(addr)
                    new_count += 1
            return len(tokens), new_count
        except Exception as e:
            log.warning("[SOLSCAN] tick error: %r", e)
            return 0, 0
    
    def ping(self) -> Dict[str, Any]:
        """Manual ping command - force immediate tick and return stats"""
        log.info("[SOLSCAN] ping forced-tick at %s", time.time())
        
        if not self._running:
            return {"error": "Scanner not running", "new": 0, "seen": len(self.seen)}
        
        try:
            tokens = self.fetch_new_tokens()
            new_count = 0
            
            for token in tokens:
                addr = token.get('address')
                if addr and addr not in self.seen:
                    self.seen.add(addr)
                    new_count += 1
            
            return {
                "success": True,
                "new": new_count,
                "seen": len(self.seen),
                "total_fetched": len(tokens),
                "base_url": self.base_url
            }
        except Exception as e:
            log.error("[SOLSCAN] ping error: %r", e)
            return {"error": str(e), "new": 0, "seen": len(self.seen)}

    # --- core fetch ----------------------------------------------------------
    def fetch_new_tokens(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Returns a list of normalized token dicts:
          { 'name', 'symbol', 'address', 'price_usd', 'source', 'links': {...} }
        """
        if not self._running:
            # still allow direct pulls for /fetch_now; we just don't run in a loop here
            pass

        n = count or self.limit
        headers = _build_headers(self.api_key)
        
        backoff = 0.8
        for attempt in range(3):
            for path, list_key in _CANDIDATE_PATHS:
                # Build params based on endpoint requirements
                request_params = {}
                
                # v1 endpoints need chain param
                if "v1" in path:
                    request_params["chain"] = self.network
                    request_params["limit"] = n
                # v2.0/token/trending accepts limit
                elif "trending" in path:
                    request_params["limit"] = n
                # Other v2.0 endpoints don't accept limit param
                
                url = f"{self.base_url}{path}"
                try:
                    r = self._client.get(url, headers=headers, params=request_params)
                    if r.status_code == 200:
                        data = r.json()
                        items = data.get(list_key, [])
                        if isinstance(items, list):
                            out = [self._normalize(tok) for tok in items]
                            self._last_ok = {"when": time.time(), "count": len(out), "path": path}
                            self._last_err = None
                            self._requests_ok += 1
                            self._last_status_code = 200
                            log.info("[SOLSCAN] %s ok: %d items", path, len(out))
                            return out
                        else:
                            log.warning("[SOLSCAN] %s unexpected payload shape", path)
                    else:
                        self._requests_err += 1
                        self._last_status_code = r.status_code
                        log.warning("[SOLSCAN] %s status=%s body=%s", path, r.status_code, r.text[:240])
                        if r.status_code == 401 or r.status_code == 403:
                            self._last_err = {"when": time.time(), "code": r.status_code, "path": path}
                            # auth issues won't improve by trying other paths — bail fast
                            return []
                except Exception as e:
                    self._requests_err += 1
                    log.warning("[SOLSCAN] %s error: %r", path, e)

            # small jittered backoff between attempts
            sleep = backoff + random.random() * 0.4
            time.sleep(sleep)
            backoff *= 1.6

        self._last_err = {"when": time.time(), "code": "exhausted"}
        return []

    # --- helpers -------------------------------------------------------------
    @staticmethod
    def _normalize(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map Solscan fields to our common token schema.
        We handle a few likely field names defensively.
        """
        addr = item.get("mintAddress") or item.get("address") or item.get("mint") or ""
        sym = item.get("symbol") or item.get("tokenSymbol") or ""
        name = item.get("name") or item.get("tokenName") or sym or addr[:6]
        price = (
            item.get("price") or
            item.get("priceUsd") or
            (item.get("market", {}) or {}).get("price")
        )

        links = {
            "solscan": f"https://solscan.io/token/{addr}" if addr else None,
            "birdeye": f"https://birdeye.so/token/{addr}?chain=solana" if addr else None,
            "pumpfun": f"https://pump.fun/{addr}" if addr else None,
        }

        return {
            "name": name,
            "symbol": sym,
            "address": addr,
            "price_usd": price,
            "source": "solscan",
            "links": links,
            "raw": item,
        }

# --- factory function for easy integration ----------------------------------
def get_solscan_scanner(api_key: str) -> Optional[SolscanScanner]:
    """Factory function to create a Solscan Pro scanner instance"""
    if not api_key or not api_key.strip():
        return None
    
    try:
        return SolscanScanner(api_key)
    except Exception as e:
        log.error("[SOLSCAN] Failed to create scanner: %r", e)
        return None