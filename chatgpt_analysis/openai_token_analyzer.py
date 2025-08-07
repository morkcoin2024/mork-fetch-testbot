import os
import logging
from typing import Dict, List, Optional, Tuple
import json
import asyncio
from openai import OpenAI

logger = logging.getLogger(__name__)

class OpenAITokenAnalyzer:
    """OpenAI-powered intelligent token analysis for Pump.fun tokens"""
    
    def __init__(self):
        self.client = None
        self.model = "gpt-3.5-turbo"
        self._initialize_client()
        
    def _initialize_client(self):
        """Initialize OpenAI client with API key"""
        try:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not found in environment")
                return
                
            self.client = OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            
    async def analyze_token_potential(self, token_data: Dict) -> Dict:
        """Analyze token potential using OpenAI"""
        if not self.client:
            return self._fallback_analysis(token_data)
            
        try:
            # Prepare token information for analysis
            analysis_prompt = self._build_analysis_prompt(token_data)
            
            # Get AI analysis
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert cryptocurrency analyst specializing in meme tokens and Pump.fun launches. Analyze tokens for potential, risks, and trading opportunities. Respond with structured JSON."
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            # Parse AI response
            ai_response = response.choices[0].message.content
            analysis = self._parse_ai_response(ai_response, token_data)
            
            logger.info(f"OpenAI analysis completed for {token_data.get('name', 'Unknown')}")
            return analysis
            
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            return self._fallback_analysis(token_data)
            
    def _build_analysis_prompt(self, token_data: Dict) -> str:
        """Build analysis prompt for OpenAI"""
        prompt = f"""
Analyze this Pump.fun token for trading potential:

TOKEN DETAILS:
- Name: {token_data.get('name', 'Unknown')}
- Symbol: {token_data.get('symbol', 'TOKEN')}
- Description: {token_data.get('description', 'No description')}
- Market Cap: ${token_data.get('usd_market_cap', 0):,.0f}
- Price: ${token_data.get('price', 0):.8f}
- Age: {self._calculate_age_description(token_data)}
- Holder Count: {token_data.get('holder_count', 0)}
- Creator: {token_data.get('creator', 'Unknown')}
- Is Renounced: {token_data.get('is_renounced', False)}
- Is Burnt: {token_data.get('is_burnt', False)}

ANALYSIS REQUIREMENTS:
1. Assess meme/narrative potential (0-100)
2. Identify risk factors
3. Evaluate market timing
4. Recommend trading strategy
5. Assign overall score (0-100)

Respond in JSON format:
{{
    "potential_score": 0-100,
    "risk_level": "low/medium/high",
    "narrative_strength": 0-100,
    "key_risks": ["risk1", "risk2"],
    "key_opportunities": ["opp1", "opp2"],
    "trading_recommendation": "buy/hold/avoid",
    "confidence": 0-100,
    "reasoning": "Brief explanation"
}}
"""
        return prompt
        
    def _calculate_age_description(self, token_data: Dict) -> str:
        """Calculate human-readable age description"""
        try:
            import time
            created_timestamp = token_data.get('created_timestamp', time.time())
            age_minutes = (time.time() - created_timestamp) / 60
            
            if age_minutes < 5:
                return f"{age_minutes:.1f} minutes (very fresh)"
            elif age_minutes < 60:
                return f"{age_minutes:.0f} minutes"
            elif age_minutes < 1440:  # 24 hours
                hours = age_minutes / 60
                return f"{hours:.1f} hours"
            else:
                days = age_minutes / 1440
                return f"{days:.1f} days"
                
        except Exception:
            return "Unknown age"
            
    def _parse_ai_response(self, ai_response: str, token_data: Dict) -> Dict:
        """Parse and validate AI response"""
        try:
            # Try to extract JSON from response
            start = ai_response.find('{')
            end = ai_response.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = ai_response[start:end]
                parsed = json.loads(json_str)
                
                # Validate required fields and add metadata
                analysis = {
                    'ai_potential_score': parsed.get('potential_score', 50),
                    'ai_risk_level': parsed.get('risk_level', 'medium'),
                    'ai_narrative_strength': parsed.get('narrative_strength', 50),
                    'ai_key_risks': parsed.get('key_risks', ['Unknown risks']),
                    'ai_key_opportunities': parsed.get('key_opportunities', ['Potential upside']),
                    'ai_trading_recommendation': parsed.get('trading_recommendation', 'hold'),
                    'ai_confidence': parsed.get('confidence', 50),
                    'ai_reasoning': parsed.get('reasoning', 'Standard meme token analysis'),
                    'ai_analysis_timestamp': int(time.time()),
                    'ai_enhanced': True
                }
                
                return analysis
                
        except Exception as e:
            logger.debug(f"Failed to parse AI response: {e}")
            
        return self._fallback_analysis(token_data)
        
    def _fallback_analysis(self, token_data: Dict) -> Dict:
        """Fallback analysis when OpenAI is unavailable"""
        import time
        
        # Basic heuristic analysis
        market_cap = token_data.get('usd_market_cap', 0)
        holder_count = token_data.get('holder_count', 0)
        age_minutes = (time.time() - token_data.get('created_timestamp', time.time())) / 60
        
        # Simple scoring logic
        potential_score = 50  # Base score
        
        # Market cap scoring
        if 10000 <= market_cap <= 50000:
            potential_score += 20
        elif market_cap > 100000:
            potential_score -= 15
            
        # Holder count scoring
        if 100 <= holder_count <= 200:
            potential_score += 15
            
        # Age scoring (newer is better for memes)
        if age_minutes < 30:
            potential_score += 10
            
        # Token quality checks
        name = token_data.get('name', '').lower()
        if any(word in name for word in ['moon', 'doge', 'pepe', 'shib']):
            potential_score += 5
            
        potential_score = max(0, min(100, potential_score))
        
        return {
            'ai_potential_score': potential_score,
            'ai_risk_level': 'medium',
            'ai_narrative_strength': potential_score,
            'ai_key_risks': ['Limited AI analysis available'],
            'ai_key_opportunities': ['Meme token potential'],
            'ai_trading_recommendation': 'hold' if potential_score >= 60 else 'avoid',
            'ai_confidence': 30,  # Low confidence for fallback
            'ai_reasoning': 'Basic heuristic analysis (OpenAI unavailable)',
            'ai_analysis_timestamp': int(time.time()),
            'ai_enhanced': False
        }
        
    async def batch_analyze_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """Analyze multiple tokens efficiently"""
        if not tokens:
            return []
            
        analyzed_tokens = []
        
        for token in tokens:
            try:
                # Add AI analysis to token data
                ai_analysis = await self.analyze_token_potential(token)
                
                # Merge AI analysis with token data
                enhanced_token = {**token, **ai_analysis}
                analyzed_tokens.append(enhanced_token)
                
                # Brief delay to respect rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to analyze token {token.get('name', 'Unknown')}: {e}")
                # Add fallback analysis
                fallback_analysis = self._fallback_analysis(token)
                enhanced_token = {**token, **fallback_analysis}
                analyzed_tokens.append(enhanced_token)
                
        logger.info(f"Completed AI analysis for {len(analyzed_tokens)} tokens")
        return analyzed_tokens
        
    def get_top_ai_picks(self, analyzed_tokens: List[Dict], limit: int = 3) -> List[Dict]:
        """Get top AI-recommended tokens"""
        if not analyzed_tokens:
            return []
            
        # Sort by AI potential score and confidence
        def scoring_key(token):
            potential = token.get('ai_potential_score', 0)
            confidence = token.get('ai_confidence', 0)
            narrative = token.get('ai_narrative_strength', 0)
            
            # Weighted scoring: potential (50%) + confidence (25%) + narrative (25%)
            return (potential * 0.5) + (confidence * 0.25) + (narrative * 0.25)
            
        top_tokens = sorted(analyzed_tokens, key=scoring_key, reverse=True)
        
        # Filter out high-risk tokens
        safe_tokens = [
            token for token in top_tokens 
            if token.get('ai_risk_level', 'high') != 'high' and
               token.get('ai_trading_recommendation', 'avoid') != 'avoid'
        ]
        
        return safe_tokens[:limit]

# Integration with pump scanner
async def enhance_tokens_with_ai(tokens: List[Dict]) -> List[Dict]:
    """Enhance tokens with OpenAI analysis"""
    try:
        analyzer = OpenAITokenAnalyzer()
        enhanced_tokens = await analyzer.batch_analyze_tokens(tokens)
        
        # Get AI top picks
        top_picks = analyzer.get_top_ai_picks(enhanced_tokens, 5)
        
        if top_picks:
            logger.info(f"AI recommends {len(top_picks)} tokens for trading")
            
        return enhanced_tokens
        
    except Exception as e:
        logger.error(f"AI enhancement failed: {e}")
        return tokens  # Return original tokens if AI fails

if __name__ == "__main__":
    # Test the AI analyzer
    import asyncio
    
    async def test_ai_analyzer():
        test_token = {
            'mint': 'TestToken123456789',
            'name': 'MoonPepe',
            'symbol': 'MPEPE',
            'description': 'The next big meme coin on Solana',
            'usd_market_cap': 25000,
            'price': 0.000001,
            'holder_count': 150,
            'created_timestamp': int(time.time()) - 600,  # 10 minutes ago
            'creator': 'TestCreator',
            'is_renounced': True,
            'is_burnt': True
        }
        
        analyzer = OpenAITokenAnalyzer()
        analysis = await analyzer.analyze_token_potential(test_token)
        
        print("AI Analysis Results:")
        print(json.dumps(analysis, indent=2))
        
    import time
    asyncio.run(test_ai_analyzer())