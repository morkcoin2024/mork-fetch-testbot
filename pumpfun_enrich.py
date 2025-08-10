# pumpfun_enrich.py
"""
Enhanced Pump.fun data enrichment with Solana RPC integration
Real-time token data enrichment with comprehensive metadata extraction
"""

import httpx, os, time, random, logging
from eventbus import publish

PUMP_BASE = "https://frontend-api.pump.fun/coins/created"
DEX_SEARCH = "https://api.dexscreener.com/latest/dex/search?q="
DEX_PAIR   = "https://api.dexscreener.com/latest/dex/pairs/solana/"

HEADERS = {
    "user-agent": "Mozilla/5.0 (MorkFetcher; +https://github.com/mork-bot)",
    "accept": "application/json",
}

def fetch_pumpfun(limit=50, offset=0, retries=3):
    """Fetch raw token data from Pump.fun with retry logic and event tracking."""
    url = f"{PUMP_BASE}?limit={limit}&offset={offset}"
    
    for attempt in range(retries):
        try:
            start_time = time.time()
            r = httpx.get(url, headers=HEADERS, timeout=8)
            
            if r.status_code == 200:
                data = r.json()
                
                # Publish detailed fetch metrics
                publish("pumpfun.raw", {
                    "n": len(data), 
                    "limit": limit, 
                    "offset": offset,
                    "response_time": round(time.time() - start_time, 3)
                })
                
                logging.info(f"Pump.fun fetch: {len(data)} tokens (limit={limit}, offset={offset})")
                return data
            else:
                publish("pumpfun.err", {
                    "code": r.status_code, 
                    "attempt": attempt + 1,
                    "url": url
                })
                logging.warning(f"Pump.fun API error: {r.status_code}")
                
        except Exception as e:
            publish("pumpfun.exc", {
                "err": str(e), 
                "attempt": attempt + 1,
                "url": url
            })
            logging.error(f"Pump.fun fetch exception: {e}")
            
        if attempt < retries - 1:
            sleep_time = 0.4 * (2**attempt) + random.uniform(0.05, 0.3)
            time.sleep(sleep_time)
            
    publish("pumpfun.failed", {"limit": limit, "offset": offset, "retries": retries})
    return []

def enrich_tokens(tokens):
    """Enrich tokens with DexScreener data and comprehensive metadata."""
    enriched = []
    success_count = 0
    error_count = 0
    
    for tok in tokens:
        mint = tok.get("mint")
        sym = tok.get("symbol") or ""
        name = tok.get("name") or ""
        
        if not mint:
            continue
            
        # DexScreener lookup with detailed tracking
        try:
            start_time = time.time()
            r = httpx.get(f"{DEX_PAIR}{mint}", headers=HEADERS, timeout=6)
            response_time = round(time.time() - start_time, 3)
            
            if r.status_code == 200:
                ds = r.json()
                pairs = ds.get("pairs", [])
                tok["dex_data"] = pairs
                
                # Extract key metrics from DexScreener data
                if pairs:
                    pair = pairs[0]  # Use primary pair
                    tok["dex_liquidity"] = pair.get("liquidity", {}).get("usd", 0)
                    tok["dex_volume_24h"] = pair.get("volume", {}).get("h24", 0)
                    tok["dex_price_usd"] = pair.get("priceUsd", "0")
                    tok["dex_price_change_24h"] = pair.get("priceChange", {}).get("h24", 0)
                    tok["dex_market_cap"] = pair.get("marketCap", 0)
                
                success_count += 1
                publish("dex.success", {
                    "mint": mint, 
                    "pairs_found": len(pairs),
                    "response_time": response_time
                })
                
            else:
                error_count += 1
                publish("dex.err", {
                    "mint": mint, 
                    "code": r.status_code,
                    "response_time": response_time
                })
                logging.warning(f"DexScreener error for {mint}: {r.status_code}")
                
        except Exception as e:
            error_count += 1
            publish("dex.exc", {"mint": mint, "err": str(e)})
            logging.error(f"DexScreener exception for {mint}: {e}")
            
        enriched.append(tok)
    
    # Publish comprehensive enrichment summary
    publish("pumpfun.enriched", {
        "total_tokens": len(enriched),
        "dex_success": success_count,
        "dex_errors": error_count,
        "success_rate": round((success_count / len(tokens)) * 100, 1) if tokens else 0
    })
    
    logging.info(f"Token enrichment complete: {success_count}/{len(tokens)} successful DexScreener lookups")
    return enriched

def pumpfun_full(limit=50):
    """Complete Pump.fun fetch and enrichment pipeline."""
    publish("pumpfun.fetch_started", {"limit": limit})
    
    raw = fetch_pumpfun(limit=limit)
    if not raw:
        publish("pumpfun.fetch_failed", {"limit": limit})
        return []
    
    enriched = enrich_tokens(raw)
    
    publish("pumpfun.fetch_completed", {
        "raw_count": len(raw),
        "enriched_count": len(enriched),
        "limit": limit
    })
    
    return enriched

def search_dexscreener(query, limit=100):
    """Search DexScreener with comprehensive error handling and tracking."""
    url = f"{DEX_SEARCH}{query}"
    
    try:
        start_time = time.time()
        r = httpx.get(url, headers=HEADERS, timeout=10)
        response_time = round(time.time() - start_time, 3)
        
        if r.status_code == 200:
            data = r.json()
            pairs = data.get("pairs", [])[:limit]
            
            publish("dex.search.success", {
                "query": query,
                "pairs_found": len(pairs),
                "response_time": response_time,
                "limit": limit
            })
            
            logging.info(f"DexScreener search '{query}': {len(pairs)} pairs found")
            return pairs
            
        else:
            publish("dex.search.error", {
                "query": query,
                "code": r.status_code,
                "response_time": response_time
            })
            logging.error(f"DexScreener search error: {r.status_code}")
            return []
            
    except Exception as e:
        publish("dex.search.exception", {"query": query, "err": str(e)})
        logging.error(f"DexScreener search exception: {e}")
        return []

def bulk_enrich_pipeline(limit=200, include_search=True):
    """Comprehensive bulk enrichment pipeline with multiple data sources."""
    pipeline_start = time.time()
    
    publish("bulk.pipeline.started", {
        "limit": limit,
        "include_search": include_search
    })
    
    results = {
        "pumpfun_tokens": [],
        "dex_pairs": [],
        "total_unique_tokens": 0,
        "processing_time": 0
    }
    
    # Phase 1: Pump.fun token fetch and enrichment
    pumpfun_tokens = pumpfun_full(limit=limit)
    results["pumpfun_tokens"] = pumpfun_tokens
    
    # Phase 2: DexScreener search (if enabled)
    if include_search:
        dex_pairs = search_dexscreener("solana", limit=limit)
        results["dex_pairs"] = dex_pairs
    
    # Calculate processing metrics
    processing_time = round(time.time() - pipeline_start, 3)
    results["processing_time"] = processing_time
    
    # Count unique tokens across sources
    unique_mints = set()
    for token in pumpfun_tokens:
        if token.get("mint"):
            unique_mints.add(token["mint"])
    
    for pair in results["dex_pairs"]:
        if pair.get("baseToken", {}).get("address"):
            unique_mints.add(pair["baseToken"]["address"])
    
    results["total_unique_tokens"] = len(unique_mints)
    
    # Publish comprehensive pipeline completion event
    publish("bulk.pipeline.completed", {
        "pumpfun_count": len(pumpfun_tokens),
        "dex_pairs_count": len(results["dex_pairs"]),
        "unique_tokens": results["total_unique_tokens"],
        "processing_time": processing_time,
        "tokens_per_second": round(results["total_unique_tokens"] / processing_time, 2) if processing_time > 0 else 0
    })
    
    logging.info(f"Bulk enrichment complete: {results['total_unique_tokens']} unique tokens in {processing_time}s")
    return results