"""
Token Fetcher for Mork F.E.T.C.H Bot
Handles token discovery and metadata retrieval
"""

import requests
import json
import time
from typing import List, Dict, Optional

class TokenFetcher:
    """Token discovery and metadata fetching"""
    
    def __init__(self):
        self.pump_api = "https://api.pump.fun"
        self.birdeye_api = "https://public-api.birdeye.so"
        
    def fetch_tokens(self, limit: int = 10) -> List[Dict]:
        """Fetch trending tokens from Pump.fun"""
        try:
            url = f"{self.pump_api}/tokens/trending"
            params = {"limit": limit, "sort": "volume_24h"}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                tokens = data.get("tokens", [])
                
                # Add metadata for each token
                enriched_tokens = []
                for token in tokens:
                    metadata = self._get_token_metadata(token["mint"])
                    token.update(metadata)
                    enriched_tokens.append(token)
                
                return enriched_tokens
            else:
                return []
                
        except Exception as e:
            print(f"Error fetching tokens: {e}")
            return []
    
    def _get_token_metadata(self, mint: str) -> Dict:
        """Get additional token metadata"""
        try:
            url = f"{self.birdeye_api}/defi/token_overview"
            params = {"address": mint}
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "market_cap": data.get("data", {}).get("mc", 0),
                    "volume_24h": data.get("data", {}).get("v24hUSD", 0),
                    "price_change_24h": data.get("data", {}).get("priceChange24hPercent", 0)
                }
        except:
            pass
        
        return {"market_cap": 0, "volume_24h": 0, "price_change_24h": 0}

# Global instance
token_fetcher = TokenFetcher()