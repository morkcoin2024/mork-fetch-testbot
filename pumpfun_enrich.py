# pumpfun_enrich.py
"""
Enhanced Pump.fun data enrichment with Solana RPC integration
Real-time token data enrichment with comprehensive metadata extraction
"""

import httpx, os, time, random, logging
from eventbus import publish

# --- Pump.fun config (dual endpoint + headers) ---
PUMPFUN_ENDPOINTS = [
    # primary
    "https://frontend-api.pump.fun/coins/created",
    # backup (community mirror; schema-compatible for very new launches)
    "https://pumpportal.fun/api/coins/created",
]
PUMPFUN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://pump.fun/",
    "Origin": "https://pump.fun",
}
PUMPFUN_TIMEOUT = 6.0

DEX_SEARCH = "https://api.dexscreener.com/latest/dex/search?q="
DEX_PAIR   = "https://api.dexscreener.com/latest/dex/pairs/solana/"
SOLANA_RPC_HTTP = os.environ.get("SOLANA_RPC_HTTP", "").strip()

HEADERS = {
    "user-agent": "Mozilla/5.0 (MorkFetcher; +https://github.com/mork-bot)",
    "accept": "application/json",
}

def fetch_pumpfun(limit=50, offset=0, retries=3):
    """Fetch raw token data from Pump.fun with dual endpoint fallback and enhanced headers."""
    last_status = None
    last_error = None
    
    for endpoint_idx, base_url in enumerate(PUMPFUN_ENDPOINTS):
        url = f"{base_url}?limit={limit}&offset={offset}"
        endpoint_name = "primary" if endpoint_idx == 0 else "backup"
        
        for attempt in range(retries):
            try:
                r = httpx.get(url, headers=PUMPFUN_HEADERS, timeout=PUMPFUN_TIMEOUT)
                last_status = r.status_code
                
                if r.status_code == 200:
                    data = r.json()
                    # Expect either list or {"coins":[...]}
                    if isinstance(data, dict) and "coins" in data:
                        data = data["coins"]
                    
                    publish("pumpfun.raw", {
                        "n": len(data), 
                        "endpoint": endpoint_name,
                        "url": base_url
                    })
                    return data
                else:
                    publish("pumpfun.err", {
                        "code": r.status_code, 
                        "endpoint": endpoint_name,
                        "attempt": attempt + 1
                    })
                    
            except Exception as e:
                last_error = str(e)
                publish("pumpfun.exc", {
                    "err": str(e), 
                    "endpoint": endpoint_name,
                    "attempt": attempt + 1
                })
                
            if attempt < retries - 1:
                time.sleep(0.4 * (2**attempt) + random.uniform(0.05, 0.3))
    
    publish("pumpfun.empty", {
        "note": "all endpoints failed", 
        "last_status": last_status,
        "last_error": last_error,
        "endpoints_tried": len(PUMPFUN_ENDPOINTS)
    })
    return []

def enrich_with_dex(tokens):
    """Enrich tokens with DexScreener data."""
    out = []
    for tok in tokens:
        mint = tok.get("mint")
        if not mint:
            out.append(tok)
            continue
        try:
            r = httpx.get(f"{DEX_PAIR}{mint}", headers=HEADERS, timeout=6)
            if r.status_code == 200:
                ds = r.json()
                tok["dex_data"] = ds.get("pairs", [])
            else:
                publish("dex.err", {"mint": mint, "code": r.status_code})
        except Exception as e:
            publish("dex.exc", {"mint": mint, "err": str(e)})
        out.append(tok)
    publish("pumpfun.enriched.dex", {"n": len(out)})
    return out

def _rpc_batch_token_supply(mints, batch_size=25, timeout=12):
    """
    Batch JSON-RPC: getTokenSupply for each mint.
    Returns dict[mint] -> {"decimals": int, "amount": str, "uiAmount": float}
    """
    if not SOLANA_RPC_HTTP:
        publish("rpc.disabled", {"reason": "no SOLANA_RPC_HTTP"})
        return {}

    results = {}
    try:
        with httpx.Client(timeout=timeout, headers={"content-type":"application/json"}) as c:
            for i in range(0, len(mints), batch_size):
                chunk = mints[i:i+batch_size]
                calls = []
                for idx, mint in enumerate(chunk):
                    calls.append({
                        "jsonrpc":"2.0","id":idx,
                        "method":"getTokenSupply","params":[mint]
                    })
                r = c.post(SOLANA_RPC_HTTP, json=calls)
                if r.status_code != 200:
                    publish("rpc.batch.err", {"code": r.status_code})
                    continue
                arr = r.json()
                # JSON-RPC batch is a list of responses
                for resp in arr:
                    rid = resp.get("id")
                    val = (resp.get("result") or {}).get("value") or {}
                    # Need to map back to mint by position
                    try:
                        mint = chunk[rid]
                    except Exception:
                        continue
                    if isinstance(val, dict):
                        results[mint] = {
                            "decimals": val.get("decimals"),
                            "amount": val.get("amount"),
                            "uiAmount": val.get("uiAmount"),
                        }
                publish("rpc.supply.batch", {"n": len(chunk)})
    except Exception as e:
        publish("rpc.batch.exc", {"err": str(e)})
    return results

def enrich_with_solana_rpc(tokens):
    """
    Add rpc.{decimals, supply} to tokens that have 'mint'.
    """
    mints = [t.get("mint") for t in tokens if t.get("mint")]
    mints = [m for m in mints if isinstance(m, str)]
    if not mints:
        publish("rpc.supply.skip", {"reason": "no mints"})
        return tokens

    sup = _rpc_batch_token_supply(mints)
    out = []
    for t in tokens:
        m = t.get("mint")
        if m and m in sup:
            t.setdefault("rpc", {})
            t["rpc"]["decimals"] = sup[m].get("decimals")
            t["rpc"]["supply"]   = sup[m].get("amount")
            t["rpc"]["supply_ui"]= sup[m].get("uiAmount")
        out.append(t)
    publish("pumpfun.rpc_enriched", {"n": len(out), "matched": len(sup)})
    return out

def pumpfun_full(limit=50):
    """Complete Pump.fun fetch and enrichment pipeline with Solana RPC integration."""
    raw = fetch_pumpfun(limit=limit)
    if not raw:
        return []
    
    # Normalize: ensure minimal shape + source
    norm = []
    for c in raw:
        norm.append({
            "source": "pumpfun",
            "symbol": c.get("symbol") or c.get("ticker") or None,
            "name": c.get("name") or None,
            "mint": c.get("mint") or c.get("mintAddress") or c.get("tokenAddress"),
            "holders": c.get("holders") or None,
            "mcap_usd": c.get("market_cap") or c.get("mcap") or None,
            "liquidity_usd": c.get("liquidity_usd") or c.get("liquidity") or None,
            "age_min": None,  # can compute if you have createdAt; left None if missing
        })
    
    # RPC enrichment (decimals/supply), then Dex data
    step1 = enrich_with_solana_rpc(norm)
    step2 = enrich_with_dex(step1)
    publish("pumpfun.full.done", {"n": len(step2)})
    return step2

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