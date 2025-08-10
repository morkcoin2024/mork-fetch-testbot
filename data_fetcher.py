"""
Data fetcher for Pump.fun and other sources.
Provides real token data for F.E.T.C.H system.
"""
import logging, time, random, httpx
import requests
from typing import List, Dict, Any, Optional

VERSION_DF = "df-4"
logging.info(f">>> data_fetcher LOADED {VERSION_DF} <<<")

LAST_JSON_URL = None
LAST_JSON_STATUS = None

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"
PUMPFUN_ENDPOINTS = ["https://frontend-api.pump.fun/coins/created"]

def _get_json_retry(url, params=None, headers=None, retries=3, backoff=1.5, timeout=10):
    """Enhanced JSON fetcher with intelligent retry logic and httpx."""
    global LAST_JSON_URL, LAST_JSON_STATUS
    ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
    if headers: ua.update(headers)
    last_exc = None
    for attempt in range(retries):
        try:
            LAST_JSON_URL = url
            r = httpx.get(url, params=params, headers=ua, timeout=timeout)
            LAST_JSON_STATUS = r.status_code
            if r.status_code in (429,500,502,503,504):
                raise httpx.HTTPStatusError("transient", request=r.request, response=r)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_exc = e
            time.sleep((backoff * (attempt+1)) + random.uniform(0,0.6))
    logging.warning("JSON fetch failed for %s: %s", url, last_exc)
    return None

def _get_json(url: str, params: Optional[Dict] = None, timeout: int = 10) -> Optional[Dict]:
    """Legacy helper for backward compatibility."""
    return _get_json_retry(url, params=params, timeout=timeout)

def _minutes_since_ms(timestamp_ms: Optional[int]) -> Optional[int]:
    """Calculate minutes since timestamp in milliseconds."""
    if not timestamp_ms:
        return None
    try:
        timestamp_s = timestamp_ms / 1000
        return int((time.time() - timestamp_s) / 60)
    except:
        return None

def fetch_candidates_from_pumpfun(limit=200, offset=0):
    """
    Pull newest Pump.fun launches. Best-effort; returns [] on any failure.
    Normalizes to our internal token dict with a 'source' tag.
    """
    for base in PUMPFUN_ENDPOINTS:
        try:
            params = {"limit": limit, "offset": offset}
            js = _get_json_retry(base, params=params, retries=2, timeout=8)
            if not js:
                continue

            rows = js if isinstance(js, list) else js.get("coins") or js.get("data") or []
            items = []
            for c in rows:
                mint = c.get("mint") or c.get("mintAddress") or c.get("address")
                if not mint:
                    continue

                name = c.get("name") or c.get("tokenName") or "Pump"
                sym  = c.get("symbol") or c.get("ticker") or (name[:4].upper() if name else "PUMP")

                ts = c.get("created_timestamp") or c.get("createdAt") or c.get("timestamp")
                # seconds → ms if needed
                if ts is not None and ts < 10_000_000_000:
                    ts *= 1000
                age_min = _minutes_since_ms(ts) if ts else None

                mcap = c.get("usd_market_cap") or c.get("market_cap") or c.get("fdv_usd")
                liq  = c.get("liquidity_usd") or c.get("liquidity")

                items.append({
                    "source": "pumpfun",
                    "symbol": sym or "?",
                    "name": name or sym or "Pump",
                    "mint": mint,
                    "contract": mint,  # Keep both for compatibility
                    "holders": c.get("holders") or c.get("holder_count") or None,
                    "mcap_usd": mcap if isinstance(mcap, (int, float)) else None,
                    "liquidity_usd": liq if isinstance(liq, (int, float)) else None,
                    "age_min": age_min,
                    "renounced_mint_auth": c.get("renounced_mint_auth"),
                    "renounced_freeze_auth": c.get("renounced_freeze_auth"),
                    "creator": c.get("creator", ""),
                    "twitter": c.get("twitter"),
                    "telegram": c.get("telegram"),
                    "website": c.get("website"),
                    "description": c.get("description", ""),
                    "image_uri": c.get("image_uri", ""),
                    "risk": None  # Will be calculated by risk scoring system
                })
            if items:
                logging.info(f"[FETCH] Retrieved {len(items)} tokens from Pump.fun via {base}")
                return items
        except Exception as e:
            logging.warning("Pump.fun fetch/parsing failed for %s: %s", base, e)
    
    logging.error("[FETCH] All Pump.fun endpoints failed")
    return []

def _fetch_pairs_from_dexscreener_search(query: str = "solana", limit: int = 200) -> List[Dict[str, Any]]:
    """
    Internal alias for DexScreener search testing.
    Used by diagnostic commands for debugging purposes.
    """
    return fetch_candidates_from_dexscreener(limit=limit, max_pairs=limit*2)

def fetch_candidates_from_dexscreener(limit: int = 50, max_pairs: int = 500) -> List[Dict[str, Any]]:
    """
    Fetch token candidates from DexScreener API.
    Returns list of token data dictionaries.
    """
    try:
        # DexScreener API for Solana new pairs
        url = "https://api.dexscreener.com/latest/dex/pairs/solana"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        data = _get_json_retry(url, headers=headers, retries=2, timeout=10)
        if not data:
            return []
        
        tokens = []
        
        for pair in data.get("pairs", [])[:max_pairs][:limit]:
            # Calculate age in minutes
            created_at = pair.get("pairCreatedAt")
            age_min = None
            if created_at:
                try:
                    created_ts = int(created_at) / 1000
                    age_min = int((time.time() - created_ts) / 60)
                except:
                    pass
            
            # Extract token data
            base_token = pair.get("baseToken", {})
            token_data = {
                "source": "dexscreener",
                "symbol": base_token.get("symbol", ""),
                "name": base_token.get("name", ""),
                "contract": base_token.get("address", ""),
                "mint": base_token.get("address", ""),  # Keep both for compatibility
                "holders": None,  # Not available in DexScreener API
                "mcap_usd": pair.get("marketCap"),
                "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                "age_min": age_min,
                "price_usd": pair.get("priceUsd"),
                "volume_24h": pair.get("volume", {}).get("h24"),
                "price_change_24h": pair.get("priceChange", {}).get("h24"),
                "dex": pair.get("dexId", ""),
                "risk": None  # Will be calculated by risk scoring system
            }
            
            tokens.append(token_data)
            
        logging.info(f"[FETCH] Retrieved {len(tokens)} tokens from DexScreener")
        return tokens
        
    except Exception as e:
        logging.error(f"[FETCH] DexScreener fetch error: {e}")
        return []

def apply_risk_scoring(tokens: List[Dict[str, Any]], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply risk scoring to token list based on rules configuration.
    """
    risk_config = rules.get("risk", {})
    weights = risk_config.get("weights", {})
    max_score = risk_config.get("max_score", 70)
    
    for token in tokens:
        risk_score = 0
        
        # Age scoring (newer = riskier)
        age_min = token.get("age_min")
        if age_min is not None and weights.get("age", 0) > 0:
            age_risk = min(100, (180 - age_min) / 180 * 100)  # 0-100 scale
            risk_score += age_risk * weights["age"]
        
        # Holders scoring (fewer = riskier)
        holders = token.get("holders")
        if holders is not None and holders > 0 and weights.get("holders", 0) > 0:
            holder_risk = max(0, (5000 - holders) / 5000 * 100)  # 0-100 scale
            risk_score += holder_risk * weights["holders"]
        
        # Liquidity scoring (lower = riskier)
        liquidity = token.get("liquidity_usd")
        if liquidity is not None and weights.get("liquidity", 0) > 0:
            liq_risk = max(0, (100000 - liquidity) / 100000 * 100)  # 0-100 scale
            risk_score += liq_risk * weights["liquidity"]
        
        # Market cap scoring (lower = riskier)
        mcap = token.get("mcap_usd")
        if mcap is not None and weights.get("mcap", 0) > 0:
            mcap_risk = max(0, (2000000 - mcap) / 2000000 * 100)  # 0-100 scale
            risk_score += mcap_risk * weights["mcap"]
        
        token["risk"] = round(risk_score, 1)
    
    # Filter by max risk score
    filtered_tokens = [t for t in tokens if t.get("risk", 0) <= max_score]
    
    return filtered_tokens

def _passes_rules(token: Dict[str, Any], rules: Dict[str, Any]) -> bool:
    """Check if token passes YAML rules filtering."""
    scan = rules.get("scan", {})
    
    # Age filter
    max_age = scan.get("max_age_minutes", 180)
    if token.get("age_min") is not None and token["age_min"] > max_age:
        return False
    
    # Holders filter
    holders = token.get("holders")
    if holders is not None and holders != -1:
        min_holders = scan.get("holders_min", 75)
        max_holders = scan.get("holders_max", 5000)
        if not (min_holders <= holders <= max_holders):
            return False
    
    # Market cap filter
    mcap = token.get("mcap_usd")
    if mcap is not None:
        min_mcap = scan.get("mcap_min_usd", 50000)
        max_mcap = scan.get("mcap_max_usd", 2000000)
        if not (min_mcap <= mcap <= max_mcap):
            return False
    
    # Liquidity filter
    liquidity = token.get("liquidity_usd")
    if liquidity is not None:
        min_liq = scan.get("liquidity_min_usd", 10000)
        if liquidity < min_liq:
            return False
    
    return True

def _score_token(token: Dict[str, Any], rules: Dict[str, Any]) -> float:
    """Calculate risk score for a token based on rules."""
    risk_config = rules.get("risk", {})
    weights = risk_config.get("weights", {})
    risk_score = 0
    
    # Age scoring (newer = riskier)
    age_min = token.get("age_min")
    if age_min is not None and weights.get("age", 0) > 0:
        age_risk = min(100, (180 - age_min) / 180 * 100)
        risk_score += age_risk * weights["age"]
    
    # Holders scoring (fewer = riskier)
    holders = token.get("holders")
    if holders is not None and holders > 0 and weights.get("holders", 0) > 0:
        holder_risk = max(0, (5000 - holders) / 5000 * 100)
        risk_score += holder_risk * weights["holders"]
    
    # Liquidity scoring (lower = riskier)
    liquidity = token.get("liquidity_usd")
    if liquidity is not None and weights.get("liquidity", 0) > 0:
        liq_risk = max(0, (100000 - liquidity) / 100000 * 100)
        risk_score += liq_risk * weights["liquidity"]
    
    # Market cap scoring (lower = riskier)
    mcap = token.get("mcap_usd")
    if mcap is not None and weights.get("mcap", 0) > 0:
        mcap_risk = max(0, (2000000 - mcap) / 2000000 * 100)
        risk_score += mcap_risk * weights["mcap"]
    
    # Renounced authority bonus (lower risk)
    renounce_weight = weights.get("renounce", 0)
    if renounce_weight > 0:
        mint_renounced = token.get("renounced_mint_auth")
        freeze_renounced = token.get("renounced_freeze_auth")
        if mint_renounced or freeze_renounced:
            risk_score -= 10 * renounce_weight  # Reduce risk for renounced
    
    return round(max(0, risk_score), 1)

def _dedupe_keep_best(tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate tokens by mint address, keeping the best one (Pump.fun preferred, then lowest risk)."""
    seen_mints = {}
    
    for token in tokens:
        mint = token.get("mint") or token.get("contract")
        if not mint:
            continue
            
        if mint not in seen_mints:
            seen_mints[mint] = token
        else:
            existing = seen_mints[mint]
            
            # Prefer Pump.fun source
            if token.get("source") == "pumpfun" and existing.get("source") != "pumpfun":
                seen_mints[mint] = token
            elif existing.get("source") == "pumpfun" and token.get("source") != "pumpfun":
                continue  # Keep existing Pump.fun token
            else:
                # Same source priority, choose lower risk
                if token.get("risk", 100) < existing.get("risk", 100):
                    seen_mints[mint] = token
    
    return list(seen_mints.values())

def fetch_and_rank(rules):
    """Merge Pump.fun + Dexscreener, filter, score, de-dupe, then order with Pump.fun first."""
    all_items = []

    # 1) Pump.fun first (ultra-new)
    try:
        all_items.extend(fetch_candidates_from_pumpfun(limit=200, offset=0))
    except Exception as e:
        logging.warning("Pump.fun source failed: %s", e)

    # 2) Dexscreener
    try:
        all_items.extend(fetch_candidates_from_dexscreener(max_pairs=500))
    except Exception as e:
        logging.warning("Dexscreener source failed: %s", e)

    # Filter using YAML rules
    filtered = [t for t in all_items if _passes_rules(t, rules)]

    # Score + coerce types
    for t in filtered:
        t["risk"] = _score_token(t, rules)
        if t.get("mcap_usd") is not None:
            t["mcap_usd"] = int(t["mcap_usd"])
        if t.get("liquidity_usd") is not None:
            t["liquidity_usd"] = int(t["liquidity_usd"])
        if t.get("age_min") is not None:
            t["age_min"] = int(t["age_min"])
        if t.get("holders") is None:
            t["holders"] = -1

    # De-dupe by mint (keep Pump.fun/newest or lowest risk)
    filtered = _dedupe_keep_best(filtered)

    # Order: Pump.fun first, then lowest risk, then higher liquidity
    def _src_priority(src): 
        return 0 if src == "pumpfun" else 1
    
    filtered.sort(key=lambda x: (
        _src_priority(x.get("source")), 
        x["risk"], 
        -(x.get("liquidity_usd") or 0)
    ))
    
    logging.info(f"[FETCH] Merged and ranked {len(filtered)} tokens from {len(all_items)} total")
    return filtered