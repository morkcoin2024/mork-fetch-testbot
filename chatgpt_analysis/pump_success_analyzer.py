#!/usr/bin/env python3
"""
Comprehensive Pump.fun Success Pattern Analyzer
Using OpenAI to analyze historical data and create the most sophisticated filtering rules
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from openai import OpenAI

logger = logging.getLogger(__name__)

class PumpSuccessAnalyzer:
    """Advanced analyzer for pump.fun success patterns using OpenAI intelligence"""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
    async def generate_comprehensive_rules(self) -> Dict:
        """Generate comprehensive filtering rules based on pump.fun historical analysis"""
        
        prompt = """You are the world's leading expert on pump.fun token analysis with access to comprehensive historical data. 

Analyze pump.fun tokens that achieved 500k+ market cap and provide the most sophisticated filtering rules possible.

Based on your analysis of successful pump.fun tokens, provide detailed insights in this JSON format:

{
  "historical_winners": {
    "successful_name_categories": [
      {
        "category": "Celebrity/Political",
        "examples": ["Token names referencing famous people"],
        "success_rate": "High/Medium/Low",
        "keywords": ["specific", "keywords", "that", "worked"]
      },
      {
        "category": "Animals/Pets", 
        "examples": ["Successful animal token names"],
        "success_rate": "High/Medium/Low",
        "keywords": ["dog", "cat", "frog", "etc"]
      },
      {
        "category": "Meme Culture",
        "examples": ["Viral meme references that succeeded"],
        "success_rate": "High/Medium/Low", 
        "keywords": ["pepe", "wojak", "chad", "etc"]
      },
      {
        "category": "Current Events",
        "examples": ["News/trend based tokens that succeeded"],
        "success_rate": "High/Medium/Low",
        "keywords": ["ai", "space", "tech", "etc"]
      }
    ]
  },
  "timing_patterns": {
    "optimal_entry_times": "When to enter tokens for max success",
    "market_cap_sweet_spots": "Best market cap ranges for entry",
    "age_ranges": "Optimal token age for maximum potential"
  },
  "linguistic_patterns": {
    "successful_name_lengths": [3, 4, 5],
    "successful_symbol_patterns": ["3-letter patterns", "4-letter patterns"],
    "viral_name_structures": ["How successful names are structured"],
    "emotional_triggers": ["Words that trigger emotional responses"]
  },
  "failure_patterns": {
    "red_flag_names": ["Patterns that typically fail"],
    "oversaturated_themes": ["Themes that are overused"],
    "timing_mistakes": ["When not to enter tokens"]
  },
  "2025_prediction_factors": {
    "trending_personalities": ["People likely to trend in 2025"],
    "emerging_themes": ["New themes gaining momentum"],
    "seasonal_opportunities": ["Time-based opportunities"],
    "tech_trends": ["Technology trends to watch"]
  },
  "advanced_scoring_weights": {
    "celebrity_reference": 25,
    "viral_meme_potential": 20,
    "current_events": 15,
    "name_memorability": 10,
    "community_appeal": 10,
    "timing_score": 10,
    "uniqueness": 10
  },
  "market_psychology": {
    "degen_appeal_factors": ["What appeals to crypto degenerates"],
    "fomo_triggers": ["What creates fear of missing out"],
    "community_building_factors": ["What builds strong communities"]
  }
}

Be extremely specific and data-driven. Include actual successful token patterns you've observed."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "You are a pump.fun data scientist with comprehensive knowledge of token success patterns."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for more factual analysis
            )
            
            analysis = json.loads(response.choices[0].message.content)
            logger.info("Comprehensive pump.fun success analysis completed")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to generate comprehensive rules: {e}")
            return {}
    
    async def generate_dynamic_keyword_list(self) -> List[str]:
        """Generate a dynamic list of high-value keywords based on current market conditions"""
        
        prompt = """Based on current crypto market conditions, viral internet culture, and recent pump.fun successes, generate a comprehensive list of 100+ keywords that would make a token likely to succeed.

Include:
1. Celebrity names (politicians, tech leaders, influencers)
2. Viral memes and internet culture
3. Current events and trending topics
4. Animal names that have historically performed well
5. Emotional triggers and psychological appeals
6. Technology and innovation terms
7. Pop culture references
8. Seasonal/timely opportunities

Return as a simple JSON array of keywords: ["keyword1", "keyword2", ...]

Focus on keywords that would appeal to crypto degenerates and meme coin traders in early 2025."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "You are a crypto market analyst specializing in viral token keywords."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            keywords = result.get('keywords', [])
            
            logger.info(f"Generated {len(keywords)} dynamic keywords for token filtering")
            return keywords
            
        except Exception as e:
            logger.error(f"Failed to generate dynamic keywords: {e}")
            return []

    async def analyze_token_with_historical_context(self, token_data: Dict) -> Dict:
        """Analyze a token against historical success patterns"""
        
        name = token_data.get('name', '')
        symbol = token_data.get('symbol', '')
        description = token_data.get('description', '')
        
        prompt = f"""Analyze this pump.fun token against historical success patterns:

Token: {name} ({symbol})
Description: {description}

Compare this token to historical pump.fun winners and provide:

1. Success probability (0-100%)
2. Similar successful tokens from history
3. Key success factors this token has
4. Potential weaknesses or concerns
5. Recommended entry strategy
6. Expected timeline for movement
7. Community appeal rating
8. Viral potential assessment

Provide detailed analysis in JSON format:
{{
  "success_probability": 85,
  "historical_comparisons": ["Similar successful tokens"],
  "strength_factors": ["Why this could succeed"],
  "weakness_factors": ["Potential concerns"],
  "entry_strategy": "When/how to enter",
  "timeline_prediction": "Expected movement timeline",
  "community_appeal": 90,
  "viral_potential": 85,
  "detailed_reasoning": "Comprehensive analysis"
}}"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {"role": "system", "content": "You are a pump.fun historian with detailed knowledge of token success patterns."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.4
            )
            
            analysis = json.loads(response.choices[0].message.content)
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze token with historical context: {e}")
            return {"success_probability": 50, "detailed_reasoning": "Analysis failed"}

async def main():
    """Test the comprehensive analysis system"""
    analyzer = PumpSuccessAnalyzer()
    
    print("🔬 COMPREHENSIVE PUMP.FUN SUCCESS ANALYSIS")
    print("=" * 70)
    
    # Generate comprehensive rules
    print("Generating comprehensive success rules...")
    rules = await analyzer.generate_comprehensive_rules()
    
    if rules:
        print("✅ Comprehensive rules generated!")
        
        # Display key insights
        historical_winners = rules.get('historical_winners', {})
        successful_categories = historical_winners.get('successful_name_categories', [])
        
        print(f"\n📊 SUCCESSFUL TOKEN CATEGORIES:")
        for category in successful_categories[:3]:
            print(f"• {category.get('category', 'Unknown')}: {category.get('success_rate', 'Unknown')} success rate")
            print(f"  Keywords: {category.get('keywords', [])[:5]}")
        
        # Display scoring weights
        scoring_weights = rules.get('advanced_scoring_weights', {})
        print(f"\n⚖️ ADVANCED SCORING WEIGHTS:")
        for factor, weight in scoring_weights.items():
            print(f"• {factor}: {weight} points")
    
    # Generate dynamic keywords
    print(f"\nGenerating dynamic keyword list...")
    keywords = await analyzer.generate_dynamic_keyword_list()
    print(f"✅ Generated {len(keywords)} dynamic keywords!")
    print(f"Sample keywords: {keywords[:15]}")
    
    # Test on sample tokens
    print(f"\n🧪 TESTING ON RECENT DETECTIONS:")
    test_tokens = [
        {"name": "Bob", "symbol": "BOB", "description": "Simple Bob token"},
        {"name": "Le Sad Turd", "symbol": "TURD", "description": "Sad meme token"},
        {"name": "i am rich", "symbol": "♦️", "description": "Diamond hands token"}
    ]
    
    for token in test_tokens:
        analysis = await analyzer.analyze_token_with_historical_context(token)
        print(f"\n📈 {token['name']} ({token['symbol']}):")
        print(f"   Success Probability: {analysis.get('success_probability', 0)}%")
        print(f"   Community Appeal: {analysis.get('community_appeal', 0)}/100")
        print(f"   Viral Potential: {analysis.get('viral_potential', 0)}/100")
        print(f"   Strategy: {analysis.get('entry_strategy', 'Unknown')}")

if __name__ == "__main__":
    asyncio.run(main())