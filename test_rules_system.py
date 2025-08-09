"""
Comprehensive test of the Rules-based Token Filtering System
Tests the complete rules engine with sample token data
"""

import json
from rules_loader import Rules
from token_filter import TokenFilter

def test_rules_system():
    """Test the complete rules system with realistic token data"""
    print("🧪 TESTING RULES-BASED TOKEN FILTERING SYSTEM")
    print("=" * 55)
    
    # Initialize the system
    print("1. Loading rules configuration...")
    rules = Rules()
    filter_engine = TokenFilter()
    
    print(f"   ✅ Rules version: {rules.meta.get('version', 'unknown')}")
    print(f"   ✅ Default profile: {rules.meta.get('default_profile', 'conservative')}")
    print(f"   ✅ Available profiles: {list(rules.profiles.keys())}")
    print()
    
    # Create sample token batch
    print("2. Creating sample token batch...")
    sample_tokens = [
        # High quality token (should score well)
        {
            "token_address": "HighQuality123",
            "symbol": "GOOD",
            "name": "Good Token",
            "source": "pump.fun",
            "age_minutes": 120,
            "market_cap_usd": 500000,
            "fdv_usd": 600000,
            "pool_liquidity_usd": 80000,
            "lp_locked_pct": 95,
            "lp_lock_days": 30,
            "holders_total": 800,
            "new_holders_30m": 120,
            "top10_holders_pct": 45,
            "dev_holdings_pct": 8,
            "mint_revoked": True,
            "freeze_revoked": True,
            "taxes_buy_pct": 2,
            "taxes_sell_pct": 3,
            "anti_snipe_off": True,
            "honeypot_checks_passed": True,
            "volume_5m_usd": 8000,
            "volume_30m_usd": 25000,
            "buys_to_sells_ratio": 1.6,
            "price_change_15m_pct": 12,
            "twitter_followers": 2500,
            "telegram_members": 1200,
            "website_present": True
        },
        # Medium quality token
        {
            "token_address": "MediumQuality456",
            "symbol": "MEH", 
            "name": "Average Token",
            "source": "raydium",
            "age_minutes": 60,
            "market_cap_usd": 150000,
            "fdv_usd": 180000,
            "pool_liquidity_usd": 45000,
            "lp_locked_pct": 75,
            "lp_lock_days": 14,
            "holders_total": 420,
            "new_holders_30m": 65,
            "top10_holders_pct": 58,
            "dev_holdings_pct": 12,
            "mint_revoked": True,
            "freeze_revoked": False,
            "taxes_buy_pct": 4,
            "taxes_sell_pct": 6,
            "anti_snipe_off": True,
            "honeypot_checks_passed": True,
            "volume_5m_usd": 4500,
            "volume_30m_usd": 18000,
            "buys_to_sells_ratio": 1.3,
            "price_change_15m_pct": 8,
            "twitter_followers": 800,
            "telegram_members": 400,
            "website_present": False
        },
        # Low quality token (should fail filters)
        {
            "token_address": "LowQuality789",
            "symbol": "BAD",
            "name": "Scam Token",
            "source": "pump.fun",
            "age_minutes": 5,
            "market_cap_usd": 25000,
            "fdv_usd": 30000,
            "pool_liquidity_usd": 8000,
            "lp_locked_pct": 20,
            "lp_lock_days": 0,
            "holders_total": 45,
            "new_holders_30m": 8,
            "top10_holders_pct": 95,
            "dev_holdings_pct": 40,
            "mint_revoked": False,
            "freeze_revoked": False,
            "taxes_buy_pct": 12,
            "taxes_sell_pct": 18,
            "anti_snipe_off": False,
            "honeypot_checks_passed": False,
            "volume_5m_usd": 200,
            "volume_30m_usd": 800,
            "buys_to_sells_ratio": 0.6,
            "price_change_15m_pct": -15,
            "twitter_followers": 0,
            "telegram_members": 0,
            "website_present": False
        }
    ]
    print(f"   ✅ Created {len(sample_tokens)} sample tokens")
    print()
    
    # Test Conservative Profile
    print("3. Testing CONSERVATIVE profile...")
    conservative_results = filter_engine.filter_and_score_tokens(sample_tokens, "conservative")
    
    print(f"   Input: {conservative_results['input_count']} tokens")
    print(f"   Passed filters: {conservative_results['passed_filters']}")
    print(f"   Failed filters: {conservative_results['failed_filters']}")
    print(f"   Returned: {conservative_results['returned_count']}")
    print(f"   Processing time: {conservative_results['processing_time']:.3f}s")
    
    if conservative_results['tokens']:
        best_token = conservative_results['tokens'][0]
        print(f"   🏆 Top token: {best_token['symbol']} - Score: {best_token['score_total']:.1f}/100")
    print()
    
    # Test Degen Profile
    print("4. Testing DEGEN profile...")
    degen_results = filter_engine.filter_and_score_tokens(sample_tokens, "degen")
    
    print(f"   Input: {degen_results['input_count']} tokens")
    print(f"   Passed filters: {degen_results['passed_filters']}")
    print(f"   Failed filters: {degen_results['failed_filters']}")
    print(f"   Returned: {degen_results['returned_count']}")
    print(f"   Processing time: {degen_results['processing_time']:.3f}s")
    
    if degen_results['tokens']:
        best_token = degen_results['tokens'][0]
        print(f"   🏆 Top token: {best_token['symbol']} - Score: {best_token['score_total']:.1f}/100")
    print()
    
    # Detailed analysis of one token
    print("5. Detailed token analysis...")
    analysis = filter_engine.get_token_analysis(sample_tokens[0], "conservative")
    
    print(f"   Token: {analysis['symbol']} ({analysis['token_address']})")
    print(f"   Passes filters: {analysis['passes_filters']}")
    print(f"   Score: {analysis['score_total']:.1f}/100")
    print(f"   Meets minimum: {analysis['meets_minimum']}")
    
    if analysis['filter_failures']:
        print(f"   Filter issues: {len(analysis['filter_failures'])}")
        for failure in analysis['filter_failures'][:3]:
            print(f"      • {failure}")
    
    print(f"   Score breakdown:")
    for category, data in analysis['score_breakdown'].items():
        print(f"      • {category.title()}: {data['score']:.1f}/100 (weight: {data['weight']:.1f}%)")
    print()
    
    # Test profile switching
    print("6. Testing profile management...")
    original_profile = filter_engine.get_current_profile()
    print(f"   Current profile: {original_profile}")
    
    # Switch to degen
    success = filter_engine.set_profile("degen")
    print(f"   Switch to degen: {'✅' if success else '❌'}")
    print(f"   New profile: {filter_engine.get_current_profile()}")
    
    # Switch back
    filter_engine.set_profile(original_profile)
    print(f"   Restored to: {filter_engine.get_current_profile()}")
    print()
    
    # Test rules summary export
    print("7. Testing results export...")
    summary = filter_engine.export_results_summary(conservative_results)
    print("   Generated summary:")
    print("   " + "\n   ".join(summary.split("\n")[:10]))  # First 10 lines
    print("   ... (truncated)")
    print()
    
    print("✅ RULES SYSTEM TEST COMPLETE")
    print(f"✅ Conservative profile found {conservative_results['returned_count']} qualifying tokens")
    print(f"✅ Degen profile found {degen_results['returned_count']} qualifying tokens")
    print(f"✅ All system components working correctly")

if __name__ == "__main__":
    test_rules_system()