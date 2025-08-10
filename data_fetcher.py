"""
Data fetcher for Pump.fun and other sources.
Provides real token data for F.E.T.C.H system.
"""
import logging
import requests
import time
from typing import List, Dict, Any, Optional

# Stable public endpoints for production use
PUMPFUN_ENDPOINTS = [
    # Primary stable endpoint (supports ?limit=&offset=)
    "https://frontend-api.pump.fun/coins/created",
]

def fetch_candidates_from_pumpfun(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Fetch real token candidates from Pump.fun API.
    Returns list of token data dictionaries.
    """
    try:
        # Use stable endpoint for production reliability
        url = PUMPFUN_ENDPOINTS[0]
        params = {
            "offset": offset,
            "limit": limit,
            "sort": "created_timestamp",
            "order": "DESC"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        tokens = []
        
        for coin in data:
            # Calculate age in minutes
            created_ts = coin.get("created_timestamp", 0) / 1000  # Convert to seconds
            age_min = int((time.time() - created_ts) / 60) if created_ts > 0 else None
            
            # Extract token data
            token_data = {
                "source": "pumpfun",
                "symbol": coin.get("symbol", ""),
                "name": coin.get("name", ""),
                "contract": coin.get("mint", ""),
                "holders": coin.get("holder_count", -1),
                "mcap_usd": coin.get("usd_market_cap"),
                "liquidity_usd": coin.get("virtual_sol_reserves", 0) * 200,  # Approximate SOL to USD
                "age_min": age_min,
                "creator": coin.get("creator", ""),
                "twitter": coin.get("twitter"),
                "telegram": coin.get("telegram"),
                "website": coin.get("website"),
                "description": coin.get("description", ""),
                "image_uri": coin.get("image_uri", ""),
                "risk": None  # Will be calculated by risk scoring system
            }
            
            tokens.append(token_data)
            
        logging.info(f"[FETCH] Retrieved {len(tokens)} tokens from Pump.fun")
        return tokens
        
    except requests.RequestException as e:
        logging.error(f"[FETCH] Pump.fun API error: {e}")
        return []
    except Exception as e:
        logging.error(f"[FETCH] Pump.fun fetch error: {e}")
        return []

def fetch_candidates_from_dexscreener(limit: int = 50) -> List[Dict[str, Any]]:
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
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        tokens = []
        
        for pair in data.get("pairs", [])[:limit]:
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
        
    except requests.RequestException as e:
        logging.error(f"[FETCH] DexScreener API error: {e}")
        return []
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