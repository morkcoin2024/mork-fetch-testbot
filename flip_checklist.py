# flip_checklist.py
# Token scoring system for the scanner
import random
from typing import Dict, Tuple

def score(token: Dict) -> Tuple[int, str, str]:
    """
    Score a token and return (score, verdict, details)
    
    Args:
        token: Token data dictionary
        
    Returns:
        Tuple of (score, verdict, details_string)
    """
    try:
        score_points = 0
        details = []
        
        # Age scoring (newer = higher score)
        age = token.get('age', token.get('age_seconds', 0))
        if age < 300:  # Less than 5 minutes
            score_points += 25
            details.append("🕐 Very fresh (<5min)")
        elif age < 1800:  # Less than 30 minutes
            score_points += 15
            details.append("🕑 Fresh (<30min)")
        elif age < 3600:  # Less than 1 hour
            score_points += 10
            details.append("🕒 Recent (<1hr)")
        else:
            score_points += 5
            details.append("🕓 Older token")
        
        # Holder count scoring
        holders = token.get('holders', token.get('holder_count', 0))
        if holders > 200:
            score_points += 20
            details.append(f"👥 High holders ({holders})")
        elif holders > 100:
            score_points += 15
            details.append(f"👥 Good holders ({holders})")
        elif holders > 50:
            score_points += 10
            details.append(f"👥 Moderate holders ({holders})")
        else:
            score_points += 5
            details.append(f"👥 Low holders ({holders})")
        
        # Liquidity scoring
        lp = token.get('lp', 0)
        if lp > 50000:
            score_points += 15
            details.append(f"💧 High liquidity (${lp:,})")
        elif lp > 20000:
            score_points += 10
            details.append(f"💧 Good liquidity (${lp:,})")
        elif lp > 10000:
            score_points += 5
            details.append(f"💧 Low liquidity (${lp:,})")
        else:
            details.append(f"💧 Very low liquidity (${lp:,})")
        
        # Volume scoring
        volume_24h = token.get('volume_24h', 0)
        if volume_24h > 100000:
            score_points += 15
            details.append(f"📈 High volume (${volume_24h:,})")
        elif volume_24h > 50000:
            score_points += 10
            details.append(f"📈 Good volume (${volume_24h:,})")
        elif volume_24h > 10000:
            score_points += 5
            details.append(f"📈 Moderate volume (${volume_24h:,})")
        
        # Price change scoring
        price_change = token.get('price_change_24h', 0)
        if price_change > 100:  # >100% gain
            score_points += 20
            details.append(f"🚀 Massive pump (+{price_change:.1f}%)")
        elif price_change > 50:  # >50% gain
            score_points += 15
            details.append(f"📈 Strong pump (+{price_change:.1f}%)")
        elif price_change > 20:  # >20% gain
            score_points += 10
            details.append(f"📈 Good pump (+{price_change:.1f}%)")
        elif price_change > 0:
            score_points += 5
            details.append(f"📈 Small gain (+{price_change:.1f}%)")
        else:
            details.append(f"📉 Down ({price_change:.1f}%)")
        
        # Security checks
        if token.get('renounced', False):
            score_points += 10
            details.append("🔒 Renounced")
        
        if token.get('mint_revoked', False):
            score_points += 10
            details.append("🔒 Mint revoked")
        
        if token.get('liquidity_locked', False):
            score_points += 5
            details.append("🔒 LP locked")
        
        # Tax checks
        buy_tax = token.get('buy_tax', 0)
        sell_tax = token.get('sell_tax', 0)
        if buy_tax == 0 and sell_tax == 0:
            score_points += 10
            details.append("💰 No taxes")
        elif buy_tax < 5 and sell_tax < 5:
            score_points += 5
            details.append(f"💰 Low taxes ({buy_tax}%/{sell_tax}%)")
        else:
            details.append(f"⚠️ High taxes ({buy_tax}%/{sell_tax}%)")
        
        # Social presence bonus
        socials = token.get('socials', {})
        social_count = sum(1 for v in socials.values() if v)
        if social_count >= 3:
            score_points += 10
            details.append("🌐 Full socials")
        elif social_count >= 2:
            score_points += 5
            details.append("🌐 Good socials")
        
        # Verification bonus
        if token.get('verified', False):
            score_points += 5
            details.append("✅ Verified")
        
        # Determine verdict based on score
        if score_points >= 90:
            verdict = "🔥 ULTRA BULLISH"
        elif score_points >= 75:
            verdict = "🚀 BULLISH"
        elif score_points >= 60:
            verdict = "📈 GOOD"
        elif score_points >= 45:
            verdict = "⚖️ NEUTRAL"
        elif score_points >= 30:
            verdict = "⚠️ RISKY"
        else:
            verdict = "🔴 AVOID"
        
        # Create details string
        details_str = " | ".join(details[:4])  # Limit to first 4 details
        if len(details) > 4:
            details_str += f" | +{len(details)-4} more"
        
        return score_points, verdict, details_str
        
    except Exception as e:
        return 0, "❌ ERROR", f"Scoring error: {e}"

def quick_score(token: Dict) -> int:
    """Quick scoring function that returns just the numeric score"""
    score_val, _, _ = score(token)
    return score_val

def is_bullish(token: Dict, threshold: int = 75) -> bool:
    """Check if token meets bullish criteria"""
    score_val, _, _ = score(token)
    return score_val >= threshold