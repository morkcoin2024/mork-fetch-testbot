"""
Integration module for AI Risk Assessment in Mork F.E.T.C.H Bot
Provides easy integration with the trading bot for real-time risk analysis
"""

import logging
from smart_risk_advisor import risk_advisor
import asyncio
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

async def get_ai_trade_recommendation(token_data: Dict) -> str:
    """Get AI-powered trade recommendation with risk assessment"""
    try:
        # Analyze the trade with AI
        analysis = await risk_advisor.analyze_trade_risk(token_data)
        
        # Extract key information
        ai_prediction = analysis.get('ai_prediction', {})
        risk_assessment = analysis.get('risk_assessment', {})
        advice = analysis.get('personalized_advice', [])
        confidence = analysis.get('confidence_level', 'medium')
        position_size = analysis.get('recommended_position_size', 0.5)
        
        # Format the recommendation message
        recommendation_parts = []
        
        # AI Prediction
        predicted_profit = ai_prediction.get('predicted_profit_pct', 0)
        risk_level = ai_prediction.get('predicted_risk_level', 'medium')
        
        recommendation_parts.append(f"🤖 **AI ANALYSIS**")
        recommendation_parts.append(f"• Predicted Profit: {predicted_profit:+.1f}%")
        recommendation_parts.append(f"• Risk Level: {risk_level.upper()}")
        recommendation_parts.append(f"• Confidence: {confidence.upper()}")
        
        # Risk Assessment
        overall_risk = risk_assessment.get('overall_risk', 'MEDIUM')
        risk_factors = risk_assessment.get('risk_factors', [])
        
        recommendation_parts.append(f"\n⚠️ **RISK ASSESSMENT**")
        recommendation_parts.append(f"• Overall Risk: {overall_risk}")
        if risk_factors:
            recommendation_parts.append(f"• Risk Factors: {len(risk_factors)} identified")
        
        # Position Size Recommendation
        position_pct = int(position_size * 100)
        recommendation_parts.append(f"\n💰 **POSITION SIZE**")
        recommendation_parts.append(f"• Recommended: {position_pct}% of normal size")
        
        # AI Advice
        if advice:
            recommendation_parts.append(f"\n💡 **AI ADVICE**")
            for i, tip in enumerate(advice[:3], 1):  # Show top 3 tips
                recommendation_parts.append(f"• {tip}")
        
        # Main Recommendation
        main_rec = ai_prediction.get('recommendation', 'NEUTRAL')
        recommendation_parts.append(f"\n🎯 **RECOMMENDATION: {main_rec}**")
        
        return "\n".join(recommendation_parts)
        
    except Exception as e:
        logger.error(f"Error getting AI recommendation: {e}")
        return "🤖 AI analysis temporarily unavailable. Proceed with standard caution."

async def record_completed_trade(user_id: str, trade_entry: Dict, trade_exit: Dict) -> None:
    """Record a completed trade for AI learning"""
    try:
        # Calculate hold duration
        entry_time = trade_entry.get('timestamp', datetime.utcnow())
        exit_time = trade_exit.get('timestamp', datetime.utcnow())
        
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
            
        hold_duration = (exit_time - entry_time).total_seconds() / 60  # minutes
        
        # Prepare outcome data
        outcome_data = {
            'exit_price': trade_exit.get('exit_price', 0),
            'hold_duration_minutes': int(hold_duration),
            'timestamp': exit_time
        }
        
        # Record for AI learning
        risk_advisor.record_trade_outcome(user_id, trade_entry, outcome_data)
        
        logger.info(f"Recorded trade outcome for AI learning: {trade_entry.get('token_name', 'Unknown')}")
        
    except Exception as e:
        logger.error(f"Error recording trade for AI learning: {e}")

async def get_learning_status() -> str:
    """Get current AI learning status for user"""
    try:
        insights = risk_advisor.get_trading_insights()
        learning_stats = insights.get('learning_stats', {})
        ai_status = insights.get('ai_status', 'unknown')
        
        status_parts = []
        
        status_parts.append("🧠 **AI LEARNING STATUS**")
        status_parts.append(f"• Status: {ai_status.replace('_', ' ').title()}")
        status_parts.append(f"• Trades Learned From: {learning_stats.get('total_trades_learned_from', 0)}")
        
        if learning_stats.get('models_trained', False):
            success_rate = learning_stats.get('overall_success_rate', 0)
            recent_rate = learning_stats.get('recent_success_rate', 0)
            
            status_parts.append(f"• Overall Success Rate: {success_rate:.1f}%")
            status_parts.append(f"• Recent Success Rate: {recent_rate:.1f}%")
            
            if recent_rate > success_rate + 5:
                status_parts.append("📈 AI is improving rapidly!")
            elif recent_rate < success_rate - 10:
                status_parts.append("📉 Recent performance declined")
        else:
            remaining = learning_stats.get('trades_until_full_learning', 20)
            status_parts.append(f"• Trades Needed for Full AI: {remaining}")
        
        # Add insights
        ai_insights = insights.get('insights', [])
        if ai_insights:
            status_parts.append("\n💡 **KEY INSIGHTS**")
            for insight in ai_insights[:2]:  # Show top 2 insights
                status_parts.append(f"• {insight}")
        
        return "\n".join(status_parts)
        
    except Exception as e:
        logger.error(f"Error getting learning status: {e}")
        return "🧠 AI learning status temporarily unavailable"

async def should_recommend_trade(token_data: Dict) -> bool:
    """Quick check if AI recommends proceeding with trade"""
    try:
        analysis = await risk_advisor.analyze_trade_risk(token_data)
        
        # Check if AI suggests avoiding
        ai_prediction = analysis.get('ai_prediction', {})
        recommendation = ai_prediction.get('recommendation', '').upper()
        
        if 'AVOID' in recommendation or 'STRONG SELL' in recommendation:
            return False
        
        # Check risk level
        risk_assessment = analysis.get('risk_assessment', {})
        if risk_assessment.get('overall_risk') == 'HIGH' and risk_assessment.get('risk_score', 0) > 80:
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error in AI trade recommendation check: {e}")
        return True  # Default to allowing trade if AI fails