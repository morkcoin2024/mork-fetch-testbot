#!/usr/bin/env python3
"""
Advanced Pump.fun Trading Rules Implementation
Phase 1: Discovery Rules, Phase 2: Risk Management, Phase 3: Scaling
"""
import re
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class TokenAnalysis:
    """Comprehensive token analysis result"""
    mint: str
    name: str
    symbol: str
    meme_score: int  # 0-100
    social_signals: Dict
    bonding_momentum: Dict
    dev_credibility: int  # 0-100
    migration_signals: bool
    wallet_health: int  # 0-100
    overall_score: int  # 0-100
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    recommendation: str  # "BUY", "WATCH", "AVOID"

class AdvancedPumpRules:
    """Implementation of sophisticated pump.fun trading rules"""
    
    def __init__(self):
        self.meme_keywords = [
            'zucked', 'simp', 'backdoor', 'elon', 'trump', 'pepe', 'wojak',
            'chad', 'gigachad', 'based', 'cringe', 'moon', 'diamond', 'hands',
            'ape', 'degen', 'wagmi', 'ngmi', 'rekt', 'pump', 'lambo', 'rocket'
        ]
        
        self.high_value_patterns = [
            r'bill\s+gates', r'mark\s+zuckerberg', r'steve\s+jobs',
            r'donald\s+trump', r'elon\s+musk', r'ai\s+companion',
            r'dog\s+coin', r'cat\s+coin', r'frog\s+coin'
        ]
        
        self.migration_keywords = [
            'raydium', 'jupiter', 'dex', 'lp', 'liquidity', 'pool',
            'migration', 'listing', 'mainnet', 'launch'
        ]

    def analyze_meme_power(self, token_data: Dict) -> Tuple[int, List[str]]:
        """Analyze meme potential and viral capacity"""
        name = token_data.get('name', '').lower()
        symbol = token_data.get('symbol', '').lower()
        description = token_data.get('description', '').lower()
        
        score = 0
        signals = []
        
        # Check for high-value patterns (50 points each)
        for pattern in self.high_value_patterns:
            if re.search(pattern, name + ' ' + description):
                score += 50
                signals.append(f"High-value pattern: {pattern}")
        
        # Check for meme keywords (10 points each, max 40)
        keyword_hits = 0
        for keyword in self.meme_keywords:
            if keyword in name or keyword in symbol or keyword in description:
                keyword_hits += 1
                signals.append(f"Meme keyword: {keyword}")
        
        score += min(keyword_hits * 10, 40)
        
        # Name length scoring (shorter = more memeable)
        name_len = len(token_data.get('name', ''))
        if name_len <= 8:
            score += 20
            signals.append("Short, catchy name")
        elif name_len <= 15:
            score += 10
            signals.append("Medium length name")
        
        # Symbol scoring
        symbol_len = len(token_data.get('symbol', ''))
        if 3 <= symbol_len <= 6:
            score += 15
            signals.append("Good symbol length")
        
        # Pop culture tie-ins
        if any(word in name for word in ['2024', '2025', 'ai', 'bot', 'gpt']):
            score += 15
            signals.append("Current trends reference")
        
        return min(score, 100), signals

    def analyze_bonding_momentum(self, token_data: Dict) -> Tuple[Dict, int]:
        """Analyze initial bonding and momentum signals"""
        momentum_data = {
            'sol_bonded': 0,
            'unique_buyers': 0,
            'age_minutes': 0,
            'instant_sell_detected': False
        }
        
        score = 0
        
        # Calculate age
        created_timestamp = token_data.get('created_timestamp', 0)
        if created_timestamp:
            age_seconds = datetime.now().timestamp() - created_timestamp
            age_minutes = age_seconds / 60
            momentum_data['age_minutes'] = age_minutes
            
            # Age scoring (fresher = better, but not too fresh)
            if 3 <= age_minutes <= 30:
                score += 30
            elif 30 < age_minutes <= 60:
                score += 20
            elif age_minutes > 180:
                score -= 20  # Too old
        
        # Estimate SOL bonded from market cap
        market_cap = token_data.get('market_cap', 0)
        if market_cap:
            # Rough estimation: market cap to SOL bonded
            estimated_sol = market_cap / 15000  # Approximate conversion
            momentum_data['sol_bonded'] = estimated_sol
            
            if estimated_sol >= 0.3:
                score += 25
            if estimated_sol >= 0.8:
                score += 15
            if estimated_sol >= 2.0:
                score += 10
        
        # Virtual reserves analysis
        virtual_sol = token_data.get('virtual_sol_reserves', 30)
        if virtual_sol > 30:
            score += 15  # More than initial reserves = activity
            momentum_data['sol_bonded'] = max(momentum_data['sol_bonded'], virtual_sol - 30)
        
        return momentum_data, min(score, 100)

    def analyze_dev_credibility(self, token_data: Dict) -> Tuple[int, List[str]]:
        """Analyze developer credibility signals"""
        score = 0
        signals = []
        
        creator = token_data.get('creator', '')
        
        # Creator wallet analysis
        if creator and len(creator) == 44:  # Valid Solana address
            score += 20
            signals.append("Valid creator address")
            
            # Check if wallet looks established (heuristic)
            if not creator.startswith('11111') and not creator.endswith('11111'):
                score += 10
                signals.append("Non-obvious wallet pattern")
        
        # Renounced ownership
        if token_data.get('is_renounced', False):
            score += 25
            signals.append("Ownership renounced")
        
        # Burnt liquidity
        if token_data.get('is_burnt', False):
            score += 25
            signals.append("Liquidity burnt")
        
        # Description quality
        description = token_data.get('description', '')
        if len(description) > 50:
            score += 15
            signals.append("Detailed description")
        
        return min(score, 100), signals

    def analyze_migration_signals(self, token_data: Dict) -> bool:
        """Check for DEX migration planning signals"""
        description = token_data.get('description', '').lower()
        name = token_data.get('name', '').lower()
        
        # Look for migration keywords
        for keyword in self.migration_keywords:
            if keyword in description or keyword in name:
                return True
        
        # Look for specific migration phrases
        migration_phrases = [
            'dex at', 'lp at', 'raydium at', 'jupiter at',
            'will launch', 'migration plan', 'dex launch'
        ]
        
        for phrase in migration_phrases:
            if phrase in description:
                return True
        
        return False

    def calculate_risk_level(self, analysis: TokenAnalysis) -> str:
        """Calculate overall risk level"""
        if analysis.overall_score >= 75:
            return "LOW"
        elif analysis.overall_score >= 50:
            return "MEDIUM"
        else:
            return "HIGH"

    def generate_recommendation(self, analysis: TokenAnalysis) -> str:
        """Generate trading recommendation"""
        if analysis.overall_score >= 75 and analysis.risk_level == "LOW":
            return "BUY"
        elif analysis.overall_score >= 60:
            return "WATCH"
        else:
            return "AVOID"

    async def analyze_token(self, token_data: Dict) -> TokenAnalysis:
        """Comprehensive token analysis using all rules"""
        try:
            # Phase 1: Meme Power Analysis
            meme_score, meme_signals = self.analyze_meme_power(token_data)
            
            # Phase 1: Bonding Momentum Analysis  
            momentum_data, momentum_score = self.analyze_bonding_momentum(token_data)
            
            # Phase 1: Dev Credibility Analysis
            dev_score, dev_signals = self.analyze_dev_credibility(token_data)
            
            # Phase 1: Migration Signals
            has_migration = self.analyze_migration_signals(token_data)
            migration_score = 30 if has_migration else 0
            
            # Calculate overall score (weighted)
            overall_score = int(
                (meme_score * 0.3) +          # 30% meme power
                (momentum_score * 0.25) +     # 25% momentum  
                (dev_score * 0.25) +          # 25% dev credibility
                (migration_score * 0.2)       # 20% migration signals
            )
            
            # Create analysis result
            analysis = TokenAnalysis(
                mint=token_data.get('mint', ''),
                name=token_data.get('name', ''),
                symbol=token_data.get('symbol', ''),
                meme_score=meme_score,
                social_signals={'meme_signals': meme_signals},
                bonding_momentum=momentum_data,
                dev_credibility=dev_score,
                migration_signals=has_migration,
                wallet_health=dev_score,  # Using dev score as proxy
                overall_score=overall_score,
                risk_level=self.calculate_risk_level(
                    type('temp', (), {'overall_score': overall_score})()
                ),
                recommendation=""
            )
            
            # Generate recommendation
            analysis.recommendation = self.generate_recommendation(analysis)
            
            logger.info(f"Token analysis complete for {analysis.name}: {analysis.overall_score}/100, {analysis.recommendation}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Token analysis failed: {e}")
            # Return minimal analysis on error
            return TokenAnalysis(
                mint=token_data.get('mint', ''),
                name=token_data.get('name', 'Unknown'),
                symbol=token_data.get('symbol', 'UNK'),
                meme_score=0,
                social_signals={},
                bonding_momentum={},
                dev_credibility=0,
                migration_signals=False,
                wallet_health=0,
                overall_score=0,
                risk_level="HIGH",
                recommendation="AVOID"
            )

    async def select_top_3_tokens(self, token_list: List[Dict]) -> List[TokenAnalysis]:
        """Apply discovery rules to select top 3 tokens from batch"""
        logger.info(f"Analyzing {len(token_list)} tokens with advanced rules...")
        
        analyses = []
        for token_data in token_list:
            analysis = await self.analyze_token(token_data)
            analyses.append(analysis)
        
        # Sort by overall score (highest first)
        top_analyses = sorted(analyses, key=lambda x: x.overall_score, reverse=True)
        
        # Filter to only BUY and WATCH recommendations
        quality_tokens = [a for a in top_analyses if a.recommendation in ["BUY", "WATCH"]]
        
        # Return top 3
        selected = quality_tokens[:3]
        
        if selected:
            logger.info(f"Selected {len(selected)} top tokens:")
            for i, analysis in enumerate(selected, 1):
                logger.info(f"  #{i}: {analysis.name} ({analysis.symbol}) - Score: {analysis.overall_score}/100, Risk: {analysis.risk_level}")
        
        return selected

# Risk management parameters
RISK_MANAGEMENT_RULES = {
    'min_sol_bonded': 0.3,           # Never enter before 0.3 SOL bonded
    'ideal_sol_range': (0.8, 2.0),  # Ideal entry range
    'max_position_size': 0.1,       # Max 0.1 SOL per trade
    'stop_loss_percent': 40,         # Auto-sell at -40%
    'take_profit_first': 30,         # Take 30% at 2x
    'trailing_margin': 100,          # 100% trailing stop
    'max_daily_exposure': 0.1,       # 10% of bankroll per day
    'position_spread': 3             # Use 3 separate wallets
}

if __name__ == "__main__":
    # Test the rules system
    async def test_rules():
        rules = AdvancedPumpRules()
        
        test_token = {
            'mint': 'TestMint123pump',
            'name': 'ELON MOON DOG',
            'symbol': 'EDOG',
            'description': 'The ultimate meme coin with Raydium migration planned at 5 SOL',
            'created_timestamp': datetime.now().timestamp() - 600,  # 10 minutes old
            'market_cap': 25000,
            'virtual_sol_reserves': 35,
            'is_renounced': True,
            'is_burnt': False,
            'creator': '9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM'
        }
        
        analysis = await rules.analyze_token(test_token)
        print(f"Test Analysis: {analysis.name} - {analysis.overall_score}/100 - {analysis.recommendation}")
    
    asyncio.run(test_rules())