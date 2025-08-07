"""
Pump.fun Token Profile Picture (PFP) Fetcher
Fetches and integrates token images from pump.fun for enhanced token display
"""

import requests
import logging
import asyncio
import aiohttp
from typing import Optional, Dict
import json
import base64
import re
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class PumpFunPFPFetcher:
    def __init__(self):
        self.session = None
        self.base_url = "https://pump.fun"
        self.api_url = "https://frontend-api.pump.fun"
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def get_token_pfp(self, mint_address: str) -> Optional[str]:
        """Fetch token PFP URL from pump.fun"""
        try:
            # Try multiple methods to get the token image
            pfp_url = await self._fetch_from_api(mint_address)
            if not pfp_url:
                pfp_url = await self._fetch_from_page(mint_address)
            if not pfp_url:
                pfp_url = await self._fetch_from_metadata(mint_address)
                
            logger.info(f"Found PFP for {mint_address}: {pfp_url}")
            return pfp_url
            
        except Exception as e:
            logger.debug(f"Failed to fetch PFP for {mint_address}: {e}")
            return None
            
    async def _fetch_from_api(self, mint_address: str) -> Optional[str]:
        """Fetch PFP from pump.fun API"""
        try:
            api_url = f"{self.api_url}/coins/{mint_address}"
            
            async with self.session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract image URL from API response
                    image_url = data.get('image_uri') or data.get('image') or data.get('icon')
                    if image_url:
                        return self._normalize_image_url(image_url)
                        
        except Exception as e:
            logger.debug(f"API fetch failed for {mint_address}: {e}")
            
        return None
        
    async def _fetch_from_page(self, mint_address: str) -> Optional[str]:
        """Fetch PFP by scraping token page"""
        try:
            page_url = f"{self.base_url}/coin/{mint_address}"
            
            async with self.session.get(page_url) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for image URLs in the HTML
                    image_patterns = [
                        r'<img[^>]+src=[\'"](https://[^"\']*\.(?:jpg|jpeg|png|gif|webp))[\'"][^>]*>',
                        r'<meta[^>]+property=["\']og:image["\'][^>]+content=[\'"](https://[^"\']+)[\'"]',
                        r'background-image:\s*url\([\'"]?(https://[^"\']*\.(?:jpg|jpeg|png|gif|webp))[\'"]?\)',
                    ]
                    
                    for pattern in image_patterns:
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        for match in matches:
                            if 'pump.fun' in match or 'ipfs' in match:
                                return self._normalize_image_url(match)
                                
        except Exception as e:
            logger.debug(f"Page scraping failed for {mint_address}: {e}")
            
        return None
        
    async def _fetch_from_metadata(self, mint_address: str) -> Optional[str]:
        """Fetch PFP from token metadata"""
        try:
            # Try to get metadata URI from Solana
            from wallet_integration import SolanaWalletIntegrator
            integrator = SolanaWalletIntegrator()
            
            # This would typically involve calling Solana RPC to get token metadata
            # For now, construct likely IPFS/Arweave URLs
            possible_metadata_urls = [
                f"https://cf-ipfs.com/ipfs/{mint_address}",
                f"https://arweave.net/{mint_address}",
                f"https://ipfs.io/ipfs/{mint_address}"
            ]
            
            for url in possible_metadata_urls:
                try:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            metadata = await response.json()
                            image_url = metadata.get('image')
                            if image_url:
                                return self._normalize_image_url(image_url)
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Metadata fetch failed for {mint_address}: {e}")
            
        return None
        
    def _normalize_image_url(self, url: str) -> str:
        """Normalize and validate image URL"""
        if not url:
            return None
            
        # Handle IPFS URLs
        if url.startswith('ipfs://'):
            return f"https://cf-ipfs.com/ipfs/{url[7:]}"
        elif url.startswith('ar://'):
            return f"https://arweave.net/{url[5:]}"
            
        # Ensure HTTPS
        if url.startswith('http://'):
            url = url.replace('http://', 'https://')
            
        return url
        
    async def get_token_info_with_pfp(self, mint_address: str, token_data: Dict) -> Dict:
        """Enhance token data with PFP information"""
        try:
            pfp_url = await self.get_token_pfp(mint_address)
            
            enhanced_data = token_data.copy()
            enhanced_data.update({
                'pfp_url': pfp_url,
                'pump_fun_page': f"https://pump.fun/coin/{mint_address}",
                'has_image': pfp_url is not None
            })
            
            return enhanced_data
            
        except Exception as e:
            logger.debug(f"Failed to enhance token data with PFP: {e}")
            return token_data

# Standalone function for easy integration
async def fetch_pump_fun_pfp(mint_address: str) -> Optional[str]:
    """Standalone function to fetch a pump.fun token PFP"""
    async with PumpFunPFPFetcher() as fetcher:
        return await fetcher.get_token_pfp(mint_address)

# Batch fetching for multiple tokens
async def fetch_multiple_pfps(mint_addresses: list) -> Dict[str, Optional[str]]:
    """Fetch PFPs for multiple tokens efficiently"""
    results = {}
    
    async with PumpFunPFPFetcher() as fetcher:
        tasks = []
        for mint in mint_addresses:
            task = fetcher.get_token_pfp(mint)
            tasks.append((mint, task))
            
        # Process in batches to avoid overwhelming the server
        batch_size = 5
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[task for _, task in batch], 
                return_exceptions=True
            )
            
            for (mint, _), result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results[mint] = None
                else:
                    results[mint] = result
                    
            # Small delay between batches
            if i + batch_size < len(tasks):
                await asyncio.sleep(1)
                
    return results

if __name__ == "__main__":
    # Test the PFP fetcher
    async def test_pfp_fetcher():
        test_mint = "4vqZXnzJG2VZsKNy9AswAzjLYp64SvRjN3EDur56pump"  # Example pump.fun token
        
        print(f"Testing PFP fetcher for: {test_mint}")
        
        async with PumpFunPFPFetcher() as fetcher:
            pfp_url = await fetcher.get_token_pfp(test_mint)
            
            if pfp_url:
                print(f"✅ Found PFP: {pfp_url}")
            else:
                print("❌ No PFP found")
                
    asyncio.run(test_pfp_fetcher())