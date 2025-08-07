#!/usr/bin/env python3
"""
AI-Enhanced Pump.fun Trading Rules
Using OpenAI to analyze historical pump.fun successes and generate intelligent filtering rules
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from openai import OpenAI

logger = logging.getLogger(__name__)

class AIEnhancedPumpRules:
    """AI-powered analysis of pump.fun token success patterns"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.success_patterns = None
        self.trend_keywords = None
        self.failure_patterns = None
        
    async def generate_success_patterns(self) -> Dict:
        """Use OpenAI to analyze pump.fun success patterns"""
        try:
            prompt = """You are an expert crypto analyst with deep knowledge of pump.fun's most successful tokens. 

Analyze the historical success patterns of pump.fun tokens that reached 500k+ market cap and provide insights in the following JSON format:

{
  "successful_name_patterns": [
    "Names that reference current events/people",
    "Simple, memorable animal names", 
    "Pop culture references",
    "Short catchy phrases"
  ],
  "high_value_keywords": [
    "Keywords that appeared in 500k+ tokens"
  ],
  "trending_themes_2024_2025": [
    "AI and technology themes",
    "Political figures",
    "Viral internet culture"
  ],
  "success_characteristics": {
    "optimal_name_length": "3-8 characters",
    "optimal_symbol_length": "3-5 characters", 
    "successful_market_cap_entry": "5000-50000",
    "successful_age_ranges": "2-30 minutes"
  },
  "failure_red_flags": [
    "Overly complex names",
    "Generic crypto terms",
    "Obvious scam indicators"
  ],
  "meme_viral_indicators": [
    "Current trend references",
    "Emotional triggers",
    "Community appeal factors"
  ],
  "celebrity_references": [
    "Names that reference popular figures"
  ],
  "animal_success_patterns": [
    "Specific animals that have performed well"
  ],
  "seasonal_trends": [
    "Time-based opportunities"
  ]
}

Base your analysis on real pump.fun data patterns and successful token characteristics."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "You are a crypto market analyst expert in pump.fun token success patterns."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            patterns = json.loads(response.choices[0].message.content)
            self.success_patterns = patterns
            
            logger.info("AI-generated success patterns loaded successfully")
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to generate AI success patterns: {e}")
            return self._get_fallback_patterns()
    
    async def analyze_current_trends(self) -> List[str]:
        """Analyze current crypto/meme trends for 2025"""
        try:
            prompt = """As a crypto trend analyst, identify the TOP trending themes in crypto/meme culture for early 2025 that would make pump.fun tokens successful.

Consider:
- Current political climate
- Viral internet memes  
- Tech trends (AI, etc.)
- Popular figures/celebrities
- Seasonal events
- Recent news events

Provide 20-30 trending keywords/phrases that would make a pump.fun token appealing to degenerates and meme coin traders right now.

Return as JSON array: ["keyword1", "keyword2", ...]"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "You are a crypto trend analyst specializing in meme coin culture."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.8
            )
            
            result = json.loads(response.choices[0].message.content)
            trends = result.get('keywords', result.get('trends', []))
            
            logger.info(f"AI identified {len(trends)} current trending keywords")
            return trends
            
        except Exception as e:
            logger.error(f"Failed to analyze current trends: {e}")
            return ["ai", "trump", "maga", "elon", "doge", "pepe", "wojak", "chad", "bob", "rich", "sad", "moon", "pump", "rocket", "diamond", "hands", "king", "queen", "dog", "cat", "frog", "coin", "token", "meme", "solana", "sol"]
    
    async def score_token_ai_potential(self, token_data: Dict) -> Tuple[int, str, List[str]]:
        """Use AI to score a token's viral/success potential"""
        try:
            name = token_data.get('name', '')
            symbol = token_data.get('symbol', '')
            description = token_data.get('description', '')
            
            prompt = f"""Analyze this pump.fun token for viral potential and success likelihood:

Token Name: {name}
Symbol: {symbol}
Description: {description}

Rate from 0-100 based on:
1. Meme potential and viral appeal
2. Cultural relevance and timing
3. Community appeal to crypto degenerates
4. Name memorability and catchiness
5. Current trend alignment

Provide analysis in JSON format:
{{
  "viral_score": 85,
  "reasoning": "Short explanation why this score",
  "success_indicators": ["list", "of", "positive", "factors"],
  "risk_factors": ["list", "of", "concerns"],
  "recommendation": "BUY|WATCH|AVOID"
}}"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "You are an expert in viral meme coin analysis and pump.fun token success prediction."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.6
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            score = analysis.get('viral_score', 50)
            reasoning = analysis.get('reasoning', 'AI analysis unavailable')
            indicators = analysis.get('success_indicators', [])
            
            return score, reasoning, indicators
            
        except Exception as e:
            logger.error(f"AI token scoring failed: {e}")
            return 50, "AI analysis failed", []
    
    def _get_fallback_patterns(self) -> Dict:
        """Fallback patterns if AI fails"""
        return {
            "successful_name_patterns": [
                "Celebrity names", "Animal names", "Simple phrases", "Current events"
            ],
            "high_value_keywords": [
                "trump", "elon", "doge", "pepe", "wojak", "chad", "moon", "pump"
            ],
            "trending_themes_2024_2025": [
                "AI technology", "Political figures", "Viral memes"
            ],
            "success_characteristics": {
                "optimal_name_length": "3-8 characters",
                "optimal_symbol_length": "3-5 characters",
                "successful_market_cap_entry": "5000-50000",
                "successful_age_ranges": "2-30 minutes"
            },
            "failure_red_flags": [
                "Complex names", "Generic terms", "Obvious scams"
            ],
            "meme_viral_indicators": [
                "Trend references", "Emotional appeal", "Community factors"
            ]
        }

    async def enhance_token_scoring(self, tokens: List[Dict]) -> List[Dict]:
        """Enhance token list with AI scoring"""
        enhanced_tokens = []
        
        # Get current trends if not cached
        if not self.trend_keywords:
            self.trend_keywords = await self.analyze_current_trends()
        
        # Get success patterns if not cached
        if not self.success_patterns:
            self.success_patterns = await self.generate_success_patterns()
        
        for token in tokens:
            try:
                # AI scoring
                ai_score, ai_reasoning, success_indicators = await self.score_token_ai_potential(token)
                
                # Apply trend keyword scoring
                trend_score = self._calculate_trend_score(token)
                
                # Apply success pattern matching
                pattern_score = self._calculate_pattern_score(token)
                
                # Combined AI-enhanced score
                enhanced_score = (ai_score * 0.5) + (trend_score * 0.3) + (pattern_score * 0.2)
                
                # Add AI metadata to token
                token['ai_viral_score'] = ai_score
                token['ai_reasoning'] = ai_reasoning
                token['ai_success_indicators'] = success_indicators
                token['trend_score'] = trend_score
                token['pattern_score'] = pattern_score
                token['ai_enhanced_score'] = min(100, enhanced_score)
                token['ai_enhanced'] = True
                
                enhanced_tokens.append(token)
                
            except Exception as e:
                logger.error(f"Failed to enhance token {token.get('name', 'Unknown')}: {e}")
                # Add basic enhancement
                token['ai_enhanced_score'] = 50
                token['ai_enhanced'] = False
                enhanced_tokens.append(token)
        
        return enhanced_tokens
    
    def _calculate_trend_score(self, token: Dict) -> int:
        """Calculate score based on current trends"""
        if not self.trend_keywords:
            return 50
            
        name = token.get('name', '').lower()
        symbol = token.get('symbol', '').lower()
        description = token.get('description', '').lower()
        
        score = 0
        text = f"{name} {symbol} {description}"
        
        for keyword in self.trend_keywords:
            if keyword.lower() in text:
                score += 15
                
        return min(100, score)
    
    def _calculate_pattern_score(self, token: Dict) -> int:
        """Calculate score based on success patterns"""
        if not self.success_patterns:
            return 50
            
        score = 0
        name = token.get('name', '')
        symbol = token.get('symbol', '')
        
        # Name length scoring
        name_len = len(name)
        if 3 <= name_len <= 8:
            score += 20
        elif 8 < name_len <= 12:
            score += 10
            
        # Symbol length scoring  
        symbol_len = len(symbol)
        if 3 <= symbol_len <= 5:
            score += 15
            
        # High-value keyword matching
        high_value_keywords = self.success_patterns.get('high_value_keywords', [])
        text = f"{name} {symbol}".lower()
        
        for keyword in high_value_keywords:
            if keyword.lower() in text:
                score += 12
                
        return min(100, score)