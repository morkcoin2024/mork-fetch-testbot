#!/usr/bin/env python3
"""
Enhanced Solscan enrichment integration example for the Mork F.E.T.C.H Bot.

This demonstrates how the new Solscan "new tokens" support integrates with
the existing pipeline for scoring and badge display.

Implemented features:
- Auth header rotation (token → X-API-KEY → Authorization Bearer)
- Rate-limited new token discovery with 30s cache
- Auto mode fallback (new → trending)
- Enhanced enrichment with scoring bonuses
- Badge display for Telegram output
"""

import time
from typing import Dict, List, Any, Optional
from solscan import SolscanScanner

def example_enrichment_pipeline():
    """Example of how the enrichment pipeline works with new tokens support"""
    
    # Initialize scanner (would be done in app.py)
    api_key = "your_solscan_api_key"  # From environment
    scanner = SolscanScanner(api_key)
    
    # Example token addresses (would come from Birdeye, Jupiter, etc.)
    candidate_tokens = [
        "So11111111111111111111111111111111111111112",  # Example SOL
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # Example USDC
        "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",   # Example mSOL
    ]
    
    print("🔍 Solscan Enrichment Pipeline Example")
    print("=" * 50)
    
    # Demonstrate enrichment for each token
    for token_address in candidate_tokens:
        print(f"\n📍 Token: {token_address[:8]}...")
        
        # Get enrichment data
        enrichment = scanner.enrich_token(token_address)
        
        if not enrichment:
            print("   No Solscan data available")
            continue
        
        # Show enrichment details
        print(f"   Solscan Score: +{enrichment.get('solscan_score', 0):.3f}")
        
        if enrichment.get('solscan_new_seen'):
            print("   🆕 Found in new tokens cache")
        
        if enrichment.get('solscan_trending'):
            rank = enrichment['solscan_trending_rank']
            total = enrichment['solscan_trending_total']
            print(f"   📈 Trending rank: #{rank}/{total}")
        
        # Generate badge for Telegram
        badge = scanner.get_enrichment_badge(token_address)
        if badge:
            print(f"   🏷️  Badge: {badge}")

def example_scoring_integration():
    """Example of how scoring bonuses are applied"""
    
    print("\n💯 Scoring Integration Example")
    print("=" * 40)
    
    base_scores = [
        {"token": "ABC123...", "base_score": 0.65, "source": "birdeye"},
        {"token": "DEF456...", "base_score": 0.72, "source": "jupiter"},
        {"token": "GHI789...", "base_score": 0.58, "source": "pumpfun"},
    ]
    
    # Simulate enrichment data
    enrichments = {
        "ABC123...": {"solscan_new_seen": True, "solscan_score": 0.10},
        "DEF456...": {"solscan_trending_rank": 5, "solscan_score": 0.15},
        "GHI789...": {"solscan_trending_rank": 15, "solscan_score": 0.08},
    }
    
    print("Before Solscan enrichment:")
    for item in base_scores:
        print(f"  {item['token']}: {item['base_score']:.3f} ({item['source']})")
    
    print("\nAfter Solscan enrichment:")
    for item in base_scores:
        token = item['token']
        base = item['base_score']
        bonus = enrichments.get(token, {}).get('solscan_score', 0)
        final = base + bonus
        
        bonus_info = ""
        enrich = enrichments.get(token, {})
        if enrich.get('solscan_new_seen'):
            bonus_info = " [NEW]"
        elif enrich.get('solscan_trending_rank'):
            rank = enrich['solscan_trending_rank']
            bonus_info = f" [TRENDING #{rank}]"
            
        print(f"  {token}: {final:.3f} (+{bonus:.3f}){bonus_info}")

def example_cache_behavior():
    """Example of cache behavior and rate limiting"""
    
    print("\n⚡ Cache & Rate Limiting Example")
    print("=" * 40)
    
    scanner = SolscanScanner("demo_key")
    
    print("📊 Cache Status:")
    print(f"  New tokens cache: {len(scanner.get_new_tokens_cache())} items")
    print(f"  Trending cache: {len(scanner.get_trending_cache())} items")
    
    # Simulate cache aging
    print("\n⏰ Cache TTL Behavior:")
    print("  - New tokens cache: 30 seconds TTL")
    print("  - Trending cache: 30 seconds TTL") 
    print("  - Rate limiting: 0.8-1.4s base + jitter")
    print("  - 429 backoff: 1.6x multiplier, 12s cap")

def example_telegram_output():
    """Example of how badges appear in Telegram messages"""
    
    print("\n💬 Telegram Badge Examples")
    print("=" * 40)
    
    examples = [
        {
            "token": "MEME Token",
            "badge": "Solscan: NEW",
            "score": 0.75,
            "description": "Recently launched, high potential"
        },
        {
            "token": "DEGEN Coin", 
            "badge": "Solscan: trending #3",
            "score": 0.82,
            "description": "Top trending, strong momentum"
        },
        {
            "token": "MOON Token",
            "badge": "Solscan: trending #18",
            "score": 0.68,
            "description": "Popular but lower ranked"
        },
        {
            "token": "SAFE Token",
            "badge": "",
            "score": 0.55,
            "description": "Stable but not trending"
        }
    ]
    
    for example in examples:
        badge_text = f" | {example['badge']}" if example['badge'] else ""
        print(f"🎯 {example['token']} (Score: {example['score']:.2f}){badge_text}")
        print(f"   {example['description']}")

if __name__ == "__main__":
    print("🤖 Mork F.E.T.C.H Bot - Enhanced Solscan Integration")
    print("🔥 Auth rotation, rate limiting, caching, and enrichment")
    print("=" * 60)
    
    try:
        example_enrichment_pipeline()
        example_scoring_integration()
        example_cache_behavior()
        example_telegram_output()
        
        print("\n✅ Enhanced Solscan integration ready for production!")
        print("\nKey features implemented:")
        print("  ✓ Auth header rotation (3 schemes)")
        print("  ✓ Rate-limited new token discovery")
        print("  ✓ 30-second caching system")
        print("  ✓ Auto mode with trending fallback")
        print("  ✓ Enhanced enrichment scoring")
        print("  ✓ Telegram badge display")
        print("  ✓ Comprehensive admin commands")
        
    except Exception as e:
        print(f"❌ Example error: {e}")
        print("Note: This is a demonstration script - actual implementation in solscan.py")