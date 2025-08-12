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

# Scanner mode control
_SOLSCAN_MODE = os.getenv("SOLSCAN_MODE", "auto").lower()  # auto|new|trending

# New tokens endpoints to probe (ordered by preference)
_NEW_TOKEN_PATHS = [
    ("/v2/token/new", "data"),
    ("/v1/token/new", "data"), 
    ("/v1/market/new-tokens", "data"),
    ("/v1/market/tokens/new", "data"),
]

# Trending fallback endpoints
_TRENDING_PATHS = [
    ("/v2.0/token/trending", "data"),           # trending tokens with market activity - WORKS!
    ("/v1/market/token/trending", "data"),      # v1 trending fallback
]

# Legacy candidate paths (for compatibility)
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

def _build_headers_sequence(api_key: str) -> List[Dict[str, str]]:
    """Build sequence of auth headers to try in order until non-401/403"""
    base_headers = {
        "Accept": "application/json", 
        "User-Agent": "mork-fetch-bot/1.0"
    }
    
    return [
        {**base_headers, "token": api_key},
        {**base_headers, "X-API-KEY": api_key},
        {**base_headers, "Authorization": f"Bearer {api_key}"}
    ]

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
        # Trending cache for enrichment (cache for 30 seconds)
        self._trending_cache = []
        self._trending_cache_ts = 0
        self._trending_cache_ttl = 30  # seconds
        # Scanner mode management
        self._mode = _SOLSCAN_MODE
        self._last_successful_endpoint = None
        self._last_new_endpoint = None
        self._last_new_count = 0
        self._fallback_count = 0
        # New tokens cache (30 seconds TTL)
        self._new_tokens_cache = []
        self._new_tokens_cache_ts = 0
        self._new_tokens_cache_ttl = 30
        # Rate limiting and backoff
        self._last_request_ts = {}  # per endpoint
        self._backoff_delays = {}   # per endpoint
        self._last_rate_limit_log = 0  # for rate-limited logging
        # Use HTTP/2 if available, fallback to HTTP/1.1
        try:
            self._client = httpx.Client(timeout=_TIMEOUT, http2=True)
        except Exception:
            self._client = httpx.Client(timeout=_TIMEOUT, http2=False)

    # --- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        log.info("[SOLSCAN] start called; enabled=%s", self.enabled)
        self._running = True
        log.info("[SOLSCAN] started base=%s keylen=%d", self.base_url, len(self.key or ""))

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
        cache_age = time.time() - self._trending_cache_ts if self._trending_cache_ts else None
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
            "last_status": self._last_status_code,
            "trending_cache_size": len(self._trending_cache),
            "trending_cache_age": cache_age,
            "mode": self._mode,
            "last_successful_endpoint": self._last_successful_endpoint,
            "last_new_endpoint": self._last_new_endpoint,
            "last_new_count": self._last_new_count,
            "fallback_count": self._fallback_count,
            "new_tokens_cache_size": len(self._new_tokens_cache),
            "new_tokens_cache_age": time.time() - self._new_tokens_cache_ts if self._new_tokens_cache_ts else None
        }
    
    def tick(self) -> tuple[int, int]:
        """Scanner tick method for main scanning loop integration"""
        if not self._running:
            return 0, 0
        
        self._last_tick_ts = time.time()
        log.info("[SOLSCAN] tick")
        try:
            tokens = self.fetch_new_tokens()
            new_count = 0
            for token in tokens:
                addr = token.get('address', '')
                if addr and addr not in self.seen:
                    self.seen.add(addr)
                    new_count += 1
            log.info("[SOLSCAN] tick done ok=%s new=%d seen=%d", True, new_count, len(self.seen))
            return len(tokens), new_count
        except Exception as e:
            log.info("[SOLSCAN] tick done ok=%s new=%d seen=%d", False, 0, len(self.seen))
            log.warning("[SOLSCAN] tick error: %r", e)
            return 0, 0
    
    def ping(self) -> Dict[str, Any]:
        """Manual ping command - force immediate tick and return stats"""
        log.info("[SOLSCAN] ping -> tick start")
        
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
            
            log.info("[SOLSCAN] tick done ok=%s new=%d seen=%d", True, new_count, len(self.seen))
            
            return {
                "success": True,
                "new": new_count,
                "seen": len(self.seen),
                "total_fetched": len(tokens),
                "base_url": self.base_url
            }
        except Exception as e:
            log.info("[SOLSCAN] tick done ok=%s new=%d seen=%d", False, 0, len(self.seen))
            log.error("[SOLSCAN] ping error: %r", e)
            return {"error": str(e), "new": 0, "seen": len(self.seen)}

    # --- mode management -----------------------------------------------------
    def set_mode(self, mode: str) -> bool:
        """Set scanner mode: auto|new|trending"""
        mode = mode.lower()
        if mode in ("auto", "new", "trending"):
            self._mode = mode
            log.info("[SOLSCAN] mode set to: %s", mode)
            return True
        return False
    
    def get_mode(self) -> str:
        """Get current scanner mode"""
        return self._mode

    # --- core fetch ----------------------------------------------------------
    def fetch_new_tokens(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Returns a list of normalized token dicts based on scanner mode:
        - auto: try new token endpoints first, fallback to trending if all fail
        - new: only try new token endpoints
        - trending: only try trending endpoints
        """
        if not self._running:
            # still allow direct pulls for /fetch_now; we just don't run in a loop here
            pass

        n = count or self.limit
        
        if self._mode == "new":
            return self._fetch_with_endpoints(_NEW_TOKEN_PATHS, n)
        elif self._mode == "trending":
            return self._fetch_with_endpoints(_TRENDING_PATHS, n)
        elif self._mode == "auto":
            # Try new tokens first
            tokens = self._fetch_with_endpoints(_NEW_TOKEN_PATHS, n)
            if tokens:  # If we got results from new tokens, use them
                return tokens
            # Fallback to trending if new tokens failed
            self._fallback_count += 1
            log.info("[SOLSCAN] auto-fallback -> trending")
            return self._fetch_with_endpoints(_TRENDING_PATHS, n)
        else:
            # Fallback to legacy behavior
            return self._fetch_with_endpoints(_CANDIDATE_PATHS, n)
    
    def _fetch_with_endpoints(self, endpoints: List[tuple], count: int) -> List[Dict[str, Any]]:
        """Core fetch logic with endpoint probing and auth header rotation"""
        now = time.time()
        
        # Check cache for new tokens mode
        if endpoints == _NEW_TOKEN_PATHS and self._new_tokens_cache:
            cache_age = now - self._new_tokens_cache_ts
            if cache_age < self._new_tokens_cache_ttl:
                log.info("[SOLSCAN-NEW] cache hit: %d items (age: %.1fs)", len(self._new_tokens_cache), cache_age)
                return self._new_tokens_cache.copy()
        
        backoff = 0.8
        for attempt in range(3):
            for path, list_key in endpoints:
                # Rate limiting check
                last_req = self._last_request_ts.get(path, 0)
                required_delay = self._backoff_delays.get(path, 0)
                since_last = now - last_req
                
                if since_last < required_delay:
                    sleep_time = required_delay - since_last
                    log.debug("[SOLSCAN] rate limit delay %.1fs for %s", sleep_time, path)
                    time.sleep(sleep_time)
                
                # Build params based on endpoint requirements
                request_params = {}
                if "v1" in path:
                    request_params["chain"] = self.network
                    request_params["limit"] = count
                elif "trending" in path:
                    request_params["limit"] = count
                
                url = f"{self.base_url}{path}"
                self._last_request_ts[path] = time.time()
                
                # Try auth headers in sequence
                for auth_idx, headers in enumerate(_build_headers_sequence(self.api_key)):
                    auth_scheme = ["token", "X-API-KEY", "Authorization"][auth_idx]
                    
                    try:
                        r = self._client.get(url, headers=headers, params=request_params)
                        
                        # Handle rate limiting
                        if r.status_code == 429:
                            current_delay = self._backoff_delays.get(path, 0.8)
                            new_delay = min(current_delay * 1.6, 12.0)
                            self._backoff_delays[path] = new_delay
                            jitter = random.uniform(0.8, 1.4)
                            
                            # Rate-limited logging (once per minute)
                            if now - self._last_rate_limit_log > 60:
                                log.warning("[SOLSCAN] rate limited %s, backoff %.1fs", path, new_delay)
                                self._last_rate_limit_log = now
                            
                            time.sleep(new_delay * jitter)
                            continue
                        
                        # Log probe result
                        log.info("[SOLSCAN-NEW] probe %s -> %d (%s)", path, r.status_code, auth_scheme)
                        
                        if r.status_code == 200:
                            data = r.json()
                            items = data.get(list_key, []) if list_key else data
                            if isinstance(items, list) and items:
                                # Reset backoff on success
                                self._backoff_delays.pop(path, None)
                                
                                out = [self._normalize(tok) for tok in items]
                                self._last_ok = {"when": time.time(), "count": len(out), "path": path}
                                self._last_err = None
                                self._requests_ok += 1
                                self._last_status_code = 200
                                self._last_successful_endpoint = path
                                
                                # Update mode-specific tracking
                                if endpoints == _NEW_TOKEN_PATHS:
                                    self._last_new_endpoint = path
                                    self._last_new_count = len(out)
                                    # Cache new tokens result
                                    self._new_tokens_cache = out.copy()
                                    self._new_tokens_cache_ts = time.time()
                                    log.info("[SOLSCAN-NEW] ok: %d items from %s", len(out), path)
                                else:
                                    log.info("[SOLSCAN] %s ok: %d items", path, len(out))
                                
                                return out
                            else:
                                log.warning("[SOLSCAN] %s empty or unexpected payload shape", path)
                        
                        elif r.status_code in (401, 403):
                            # Try next auth scheme
                            log.warning("[SOLSCAN] %s auth failed (%s): %d", path, auth_scheme, r.status_code)
                            continue
                        else:
                            self._requests_err += 1
                            self._last_status_code = r.status_code
                            safe_body = r.text[:240] if r.text else ""
                            log.warning("[SOLSCAN] %s status=%s body=%s", path, r.status_code, safe_body)
                            break  # Try next endpoint
                            
                    except Exception as e:
                        self._requests_err += 1
                        log.warning("[SOLSCAN] %s error (%s): %r", path, auth_scheme, e)
                        continue
                
                # If all auth schemes failed for this endpoint, try next endpoint
                
            # Small jittered backoff between attempts
            sleep = backoff + random.random() * 0.4
            time.sleep(sleep)
            backoff *= 1.6

        self._last_err = {"when": time.time(), "code": "exhausted"}
        return []

    # --- enrichment methods --------------------------------------------------
    def get_trending_cache(self) -> List[Dict[str, Any]]:
        """Get cached trending tokens for enrichment (refreshes if stale)"""
        now = time.time()
        if (now - self._trending_cache_ts) > self._trending_cache_ttl:
            # Cache is stale, refresh it
            try:
                self._trending_cache = self.fetch_new_tokens()
                self._trending_cache_ts = now
                log.info("[SOLSCAN] trending cache refreshed: %d items", len(self._trending_cache))
            except Exception as e:
                log.warning("[SOLSCAN] trending cache refresh failed: %r", e)
                # Keep old cache if refresh fails
        
        return self._trending_cache

    def enrich_token(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Enrich a token with Solscan trending data"""
        if not token_address:
            return None
            
        trending_tokens = self.get_trending_cache()
        
        # Look for this token in trending list
        for rank, trending_token in enumerate(trending_tokens, 1):
            trending_addr = trending_token.get("address") or ""
            if trending_addr.lower() == token_address.lower():
                return {
                    "solscan_trending_rank": rank,
                    "solscan_trending_total": len(trending_tokens),
                    "solscan_score": 0.15 - (rank * 0.005),  # Higher rank = higher score, diminishing
                    "solscan_trending": True
                }
        
        return None

    def get_enrichment_badge(self, enrichment: Dict[str, Any]) -> str:
        """Generate a badge string for Solscan trending enrichment"""
        if not enrichment:
            return ""
        
        rank = enrichment.get("solscan_trending_rank")
        if rank:
            return f"Solscan: trending #{rank}"
        
        return ""

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
            "createdAt": item.get("created_at") or item.get("createdAt"),
            "source": "solscan",
            "links": links,
            "raw": item,
        }
    
    def get_new_tokens_cache(self) -> List[Dict[str, Any]]:
        """Get cached new tokens for enrichment"""
        now = time.time()
        if (now - self._new_tokens_cache_ts) > self._new_tokens_cache_ttl:
            return []  # Cache expired
        return self._new_tokens_cache.copy()
    
    def enrich_token(self, address: str) -> Dict[str, Any]:
        """Enhanced enrichment with new tokens detection"""
        enrichment = {}
        
        # Check if in new tokens cache
        new_tokens = self.get_new_tokens_cache()
        new_addresses = {t.get('address') for t in new_tokens if t.get('address')}
        if address in new_addresses:
            enrichment['solscan_new_seen'] = True
            enrichment['solscan_score'] = enrichment.get('solscan_score', 0) + 0.10
        
        # Check trending cache
        trending = self.get_trending_cache()
        for idx, token in enumerate(trending):
            if token.get('address') == address:
                rank = idx + 1
                enrichment['solscan_trending_rank'] = rank
                enrichment['solscan_trending_total'] = len(trending)
                enrichment['solscan_trending'] = True
                
                # Scoring bonus for trending rank
                if rank <= 20:
                    enrichment['solscan_score'] = enrichment.get('solscan_score', 0) + 0.05
                    # Higher rank = higher bonus (rank 1 gets 0.15, rank 20 gets 0.02)
                    rank_bonus = max(0.15 - (rank - 1) * 0.007, 0.02)
                    enrichment['solscan_score'] = enrichment.get('solscan_score', 0) + rank_bonus
                break
        
        return enrichment
    
    def get_enrichment_badge(self, address: str) -> str:
        """Generate badge string for Telegram output"""
        enrichment = self.enrich_token(address)
        
        if enrichment.get('solscan_new_seen'):
            return "Solscan: NEW"
        
        rank = enrichment.get('solscan_trending_rank')
        if rank:
            return f"Solscan: trending #{rank}"
        
        return ""

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