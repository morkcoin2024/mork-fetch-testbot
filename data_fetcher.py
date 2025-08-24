"""
Data fetcher for Pump.fun and other sources.
Provides real token data for F.E.T.C.H system.
Enhanced with comprehensive enrichment capabilities.
"""
import logging, time, random, httpx
import requests
from typing import List, Dict, Any, Optional

# Import event publishing for source-specific monitoring
try:
    from eventbus import publish
except ImportError:
    def publish(event_type, data):
        pass  # Fallback if eventbus not available

VERSION_DF = "df-6"
logging.info(f">>> data_fetcher LOADED {VERSION_DF} <<<")

LAST_JSON_URL = None
LAST_JSON_STATUS = None

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search"

# Environment-configurable Pump.fun endpoint
import os
PUMPFUN_BASE_URL = os.getenv("PUMPFUN_BASE_URL", "https://frontend-api.pump.fun")
PUMPFUN_ENDPOINTS = [f"{PUMPFUN_BASE_URL}/coins/created"]

# Import probe functionality
try:
    from probe_helpers import probe_pumpfun_sources
except ImportError:
    def probe_pumpfun_sources(limit=50):
        return {"error": "probe_helpers not available", "sources": [], "rpc": {}}

def _get_json_retry(url, params=None, headers=None, retries=3, backoff=1.5, timeout=10):
    """Enhanced JSON fetcher with intelligent retry logic and httpx with strict timeout protection."""
    global LAST_JSON_URL, LAST_JSON_STATUS
    ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
    if headers: ua.update(headers)
    last_exc = None
    # Enhanced timeout configuration for httpx
    if timeout is None:
        timeout = 10
    # Use httpx.Timeout for precise control: timeout(total, connect=3)
    httpx_timeout = httpx.Timeout(timeout, connect=3.05)
    
    for attempt in range(retries):
        try:
            LAST_JSON_URL = url
            r = httpx.get(url, params=params, headers=ua, timeout=httpx_timeout)
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
                # Publish fetch failure event
                publish("fetch.pumpfun.status", {"status": "fail", "code": "no_response"})
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
                # Publish successful fetch event with detailed metrics
                publish("fetch.pumpfun.status", {"status": "ok", "n": len(items), "source": base})
                publish("fetch.pumpfun.yield", {"tokens": len(items), "endpoint": base, "limit": limit, "offset": offset})
                return items
        except Exception as e:
            logging.warning("Pump.fun fetch/parsing failed for %s: %s", base, e)
            # Publish fetch failure event
            publish("fetch.pumpfun.status", {"status": "fail", "code": "exception", "error": str(e)})
    
    logging.error("[FETCH] All Pump.fun endpoints failed")
    # Publish overall failure event
    publish("fetch.pumpfun.status", {"status": "fail", "code": "all_endpoints_failed"})
    return []

def _fetch_pairs_from_dexscreener_search(query="solana", limit=300):
    """Enhanced DexScreener search using proper search endpoint."""
    logging.info("[FETCH] Dexscreener USING SEARCH endpoint (q=%s)", query)
    js = _get_json_retry(DEXSCREENER_SEARCH, params={"q": query})
    if not js:
        logging.warning("[FETCH] Dexscreener search returned no JSON")
        # Publish fetch failure event
        publish("fetch.dexscreener.status", {"status": "fail", "code": "no_response"})
        return []
    pairs = js.get("pairs") or []
    out = []
    for p in pairs[:limit]:
        try:
            base = p.get("baseToken") or {}
            sym = base.get("symbol") or p.get("baseSymbol") or "SOL"
            name = base.get("name") or sym
            mint = base.get("address") or p.get("pairAddress")
            liq  = (p.get("liquidity") or {}).get("usd")
            fdv  = p.get("fdv")
            out.append({
                "source": "dexscreener",
                "symbol": sym,
                "name": name,
                "mint": mint,
                "holders": None,
                "mcap_usd": fdv if isinstance(fdv,(int,float)) else None,
                "liquidity_usd": liq if isinstance(liq,(int,float)) else None,
                "age_min": None,
                "renounced_mint_auth": None,
                "renounced_freeze_auth": None,
            })
        except Exception as e:
            logging.warning("[FETCH] Error parsing Dexscreener pair: %s", e)
            continue
    logging.info("[FETCH] Dexscreener search yielded %d items", len(out))
    # Publish successful fetch event with granular search tracking
    publish("fetch.dexscreener.status", {"status": "ok", "n": len(out), "query": query})
    publish("fetch.dex.search", {"yielded": len(out), "query": query, "limit": limit})
    return out

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
            # Publish fetch failure event
            publish("fetch.dexscreener.status", {"status": "fail", "code": "no_data"})
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
        # Publish successful fetch event with detailed metrics
        publish("fetch.dexscreener.status", {"status": "ok", "n": len(tokens)})
        publish("fetch.dex.pairs", {"yielded": len(tokens), "limit": limit, "max_pairs": max_pairs})
        return tokens
        
    except Exception as e:
        logging.error(f"[FETCH] DexScreener fetch error: {e}")
        # Publish fetch failure event
        publish("fetch.dexscreener.status", {"status": "fail", "code": "exception", "error": str(e)})
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
            
            # Source priority: pumpfun-chain > pumpfun > others
            token_src = token.get("source", "")
            existing_src = existing.get("source", "")
            
            if token_src == "pumpfun-chain" and existing_src != "pumpfun-chain":
                seen_mints[mint] = token
            elif existing_src == "pumpfun-chain" and token_src != "pumpfun-chain":
                continue  # Keep existing on-chain token
            elif token_src == "pumpfun" and existing_src not in ("pumpfun-chain", "pumpfun"):
                seen_mints[mint] = token
            elif existing_src == "pumpfun" and token_src not in ("pumpfun-chain", "pumpfun"):
                continue  # Keep existing Pump.fun token
            else:
                # Same source priority, choose lower risk
                if token.get("risk", 100) < existing.get("risk", 100):
                    seen_mints[mint] = token
    
    return list(seen_mints.values())

def multi_source_fetch(limit=10, force=False):
    """
    Multi-source token fetch function used by /fetch and /fetch_now commands.
    Fetches tokens from multiple sources and returns a summary.
    """
    try:
        # Load rules
        try:
            from rules import load_rules
            rules = load_rules()
        except:
            # Fallback basic rules
            rules = {
                "scan": {
                    "max_age_minutes": 180,
                    "holders_min": 75,
                    "holders_max": 5000,
                    "mcap_min_usd": 50000,
                    "mcap_max_usd": 2000000,
                    "liquidity_min_usd": 10000
                },
                "risk": {
                    "weights": {"age": 0.2, "holders": 0.3, "liquidity": 0.3, "mcap": 0.2},
                    "max_score": 70
                }
            }

        all_tokens = []
        sources_used = []

        # 1. Pump.fun API
        try:
            pumpfun_tokens = fetch_candidates_from_pumpfun(limit=limit*2)
            if pumpfun_tokens:
                all_tokens.extend(pumpfun_tokens)
                sources_used.append("pumpfun")
                logging.info(f"[MULTI-FETCH] Got {len(pumpfun_tokens)} tokens from Pump.fun")
        except Exception as e:
            logging.warning(f"[MULTI-FETCH] Pump.fun failed: {e}")

        # 2. DexScreener  
        try:
            dex_tokens = _fetch_pairs_from_dexscreener_search(query="solana", limit=limit)
            if dex_tokens:
                all_tokens.extend(dex_tokens)
                sources_used.append("dexscreener")
                logging.info(f"[MULTI-FETCH] Got {len(dex_tokens)} tokens from DexScreener")
        except Exception as e:
            logging.warning(f"[MULTI-FETCH] DexScreener failed: {e}")

        # 3. On-chain (if available and force=True)
        if force:
            try:
                from pump_chain import fetch_recent_pumpfun_mints
                chain_tokens = fetch_recent_pumpfun_mints(max_minutes=15, limit=limit)
                if chain_tokens:
                    all_tokens.extend(chain_tokens)
                    sources_used.append("on-chain")
                    logging.info(f"[MULTI-FETCH] Got {len(chain_tokens)} tokens from on-chain")
            except Exception as e:
                logging.warning(f"[MULTI-FETCH] On-chain failed: {e}")

        # Filter and score
        filtered_tokens = []
        for token in all_tokens:
            if _passes_rules(token, rules):
                token["risk"] = _score_token(token, rules)
                filtered_tokens.append(token)

        # Deduplicate
        final_tokens = _dedupe_keep_best(filtered_tokens)

        # Sort by risk (lower = better)
        final_tokens.sort(key=lambda x: x.get("risk", 100))

        # Limit results
        final_tokens = final_tokens[:limit]

        result = {
            "total": len(final_tokens),
            "sources": sources_used,
            "tokens": final_tokens,
            "status": "success"
        }

        logging.info(f"[MULTI-FETCH] Complete: {len(final_tokens)} tokens from {len(sources_used)} sources")
        return result

    except Exception as e:
        logging.error(f"[MULTI-FETCH] Error: {e}")
        return {
            "total": 0,
            "sources": [],
            "tokens": [],
            "status": "error",
            "error": str(e)
        }

def fetch_and_rank(rules):
    """Enhanced tri-source integration: On-chain + Pump.fun + DexScreener search, filter, score, de-dupe, then order."""
    from eventbus import publish
    
    publish("fetch_started", {"sources": ["on-chain", "pumpfun", "dexscreener"]})
    all_items = []
    
    # Enhanced Pump.fun fetch with comprehensive enrichment
    try:
        enriched_pumpfun = fetch_source_pumpfun(limit=200)
        if enriched_pumpfun:
            # Add source tag for enriched data
            for token in enriched_pumpfun:
                token["source"] = "pumpfun-enriched"
            all_items.extend(enriched_pumpfun)
            logging.info("[FETCH] Pump.fun enriched: %d items", len(enriched_pumpfun))
            publish("source_complete", {"source": "pumpfun-enriched", "count": len(enriched_pumpfun), "status": "success"})
        else:
            publish("source_complete", {"source": "pumpfun-enriched", "count": 0, "status": "empty"})
    except Exception as e:
        logging.warning("Enriched Pump.fun fetch failed, falling back to standard: %s", e)
        publish("source_complete", {"source": "pumpfun-enriched", "count": 0, "status": "failed", "error": str(e)})
    
    # 1) On-chain watcher first (real-time blockchain monitoring for ultra-fresh tokens)
    try:
        from pump_chain import fetch_recent_pumpfun_mints
        chain_items = fetch_recent_pumpfun_mints(max_minutes=15, limit=25)
        all_items.extend(chain_items)
        logging.info("[FETCH] On-chain primary: %d ultra-fresh items", len(chain_items))
        # Publish early discovery event for on-chain finds
        if chain_items:
            publish("fetch.onchain.early", {"yielded": len(chain_items), "max_minutes": 15})
        publish("source_complete", {"source": "on-chain", "count": len(chain_items), "status": "success"})
    except Exception as e:
        logging.warning("On-chain primary source failed: %s", e)
    
    # 2) Pump.fun API with on-chain fallback (ultra-new launches)
    pumpfun_rows = []
    try:
        pumpfun_rows = fetch_candidates_from_pumpfun(limit=200, offset=0)
        logging.info("[FETCH] Pump.fun API: %d items", len(pumpfun_rows))
        # Publish early discovery event for Pump.fun finds
        if pumpfun_rows:
            publish("fetch.pumpfun.early", {"yielded": len(pumpfun_rows), "limit": 200})
        publish("source_complete", {"source": "pumpfun", "count": len(pumpfun_rows), "status": "success"})
    except Exception as e:
        logging.warning("Pump.fun API failed: %s", e)
        pumpfun_rows = []

    if not pumpfun_rows:
        # Use on-chain seeds when REST is down
        try:
            from pump_chain import fetch_recent_pumpfun_mints
            seeds = fetch_recent_pumpfun_mints(max_minutes=60, limit=50)
            pumpfun_rows.extend(seeds)
            logging.info("[FETCH] On-chain fallback: %d seed items", len(seeds))
            publish("fallback_activated", {"source": "on-chain", "count": len(seeds), "reason": "pumpfun_api_failed"})
        except Exception as e:
            logging.warning("On-chain fallback failed: %s", e)

    all_items.extend(pumpfun_rows)
        
    # 3) DexScreener search (established tokens)
    try: 
        dex_items = _fetch_pairs_from_dexscreener_search(query="solana", limit=300)
        all_items.extend(dex_items)
        logging.info("[FETCH] DexScreener: %d items", len(dex_items))
        publish("source_complete", {"source": "dexscreener", "count": len(dex_items), "status": "success"})
    except Exception as e: 
        logging.error("[FETCH] Dexscreener search error: %s", e)

    # Filter using YAML rules
    filtered = [t for t in all_items if _passes_rules(t, rules)]
    
    # Publish early discovery event for tokens that pass initial filtering
    publish("fetch.dex.early", {"yielded": len(filtered), "total_raw": len(all_items)})

    # Score + coerce types
    for t in filtered:
        t["risk"] = _score_token(t, rules)
        
    # SOLSCAN ENRICHMENT: Add Solscan trending data (with performance safeguard)
    skip_enrichment = os.getenv("SKIP_SOLSCAN_ENRICHMENT", "false").lower() == "true"
    if not skip_enrichment and os.getenv("FEATURE_SOLSCAN", "off").lower() == "on":
        try:
            from enrich_with_solscan import enrich_with_solscan
            filtered = enrich_with_solscan(filtered)
            enriched_count = sum(1 for t in filtered if t.get("solscan_trending"))
            publish("enrichment_complete", {"source": "solscan", "enriched_count": enriched_count})
            logging.info("[FETCH] Solscan enrichment complete: %d tokens enriched", enriched_count)
        except Exception as e:
            logging.warning("[FETCH] Solscan enrichment failed: %r", e)
            publish("enrichment_error", {"source": "solscan", "error": str(e)})
    else:
        logging.info("[FETCH] Solscan enrichment skipped (disabled or performance mode)")
        publish("enrichment_skipped", {"source": "solscan", "reason": "disabled_or_performance"})
        
    # Continue with original scoring
    for t in filtered:
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
    
    # Publish completion event with statistics
    sources = {}
    for token in filtered:
        src = token.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    
    publish("fetch_completed", {
        "total_tokens": len(filtered),
        "sources": sources,
        "top_tokens": [{"symbol": t.get("symbol"), "source": t.get("source"), "risk": t.get("risk")} 
                      for t in filtered[:5]]
    })
    
    return filtered

def fetch_source_pumpfun(limit=50):
    """Enhanced Pump.fun source fetcher with Solana RPC and DexScreener enrichment."""
    from pumpfun_enrich import pumpfun_full
    from eventbus import publish
    
    items = pumpfun_full(limit=limit)
    publish("fetch.pumpfun.final", {"n": len(items)})
    return items