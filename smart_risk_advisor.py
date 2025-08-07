"""
Smart Risk Advisor for Mork F.E.T.C.H Bot
Provides real-time risk assessments and trading recommendations based on AI learning
"""

import logging
from typing import Dict, List
from ai_learning_engine import AILearningEngine
import asyncio

logger = logging.getLogger(__name__)

class SmartRiskAdvisor:
    """Advanced risk advisor that learns from trade history"""
    
    def __init__(self):
        self.ai_engine = AILearningEngine()
        
    async def analyze_trade_risk(self, trade_data: Dict) -> Dict:
        """Comprehensive trade risk analysis"""
        try:
            # Get AI predictions
            ai_prediction = self.ai_engine.predict_trade_outcome(trade_data)
            
            # Get detailed risk assessment
            risk_assessment = self.ai_engine.get_risk_assessment(trade_data)
            
            # Get learning statistics
            learning_stats = self.ai_engine.get_learning_stats()
            
            # Generate personalized advice
            advice = self._generate_personalized_advice(ai_prediction, risk_assessment, learning_stats)
            
            return {
                'ai_prediction': ai_prediction,
                'risk_assessment': risk_assessment,
                'learning_stats': learning_stats,
                'personalized_advice': advice,
                'confidence_level': self._calculate_confidence(learning_stats),
                'recommended_position_size': self._calculate_position_size(risk_assessment)
            }
            
        except Exception as e:
            logger.error(f"Error in trade risk analysis: {e}")
            return self._fallback_analysis()
    
    def record_trade_outcome(self, user_id: str, trade_data: Dict, outcome_data: Dict) -> None:
        """Record completed trade for learning"""
        self.ai_engine.record_trade_outcome(user_id, trade_data, outcome_data)
    
    def get_trading_insights(self) -> Dict:
        """Get overall trading insights and patterns"""
        try:
            learning_stats = self.ai_engine.get_learning_stats()
            
            # Generate insights based on accumulated learning
            insights = []
            
            if learning_stats['total_trades_learned_from'] > 50:
                if learning_stats['recent_success_rate'] > learning_stats['overall_success_rate']:
                    insights.append("AI is improving - recent performance better than historical average")
                elif learning_stats['recent_success_rate'] < learning_stats['overall_success_rate'] - 10:
                    insights.append("Performance has declined recently - market conditions may have changed")
                
                if learning_stats['overall_success_rate'] > 60:
                    insights.append("Strong overall performance - AI recommendations are highly reliable")
                elif learning_stats['overall_success_rate'] < 40:
                    insights.append("Performance below target - consider more conservative position sizes")
            
            return {
                'learning_stats': learning_stats,
                'insights': insights,
                'ai_status': self._get_ai_status(learning_stats),
                'recommendations': self._get_general_recommendations(learning_stats)
            }
            
        except Exception as e:
            logger.error(f"Error getting trading insights: {e}")
            return {'ai_status': 'learning', 'insights': [], 'recommendations': []}
    
    def _generate_personalized_advice(self, ai_prediction: Dict, risk_assessment: Dict, learning_stats: Dict) -> List[str]:
        """Generate personalized trading advice"""
        advice = []
        
        # AI confidence-based advice
        if learning_stats['models_trained']:
            if ai_prediction['predicted_profit_pct'] > 5:
                advice.append(f"AI predicts {ai_prediction['predicted_profit_pct']:.1f}% profit - favorable trade")
            elif ai_prediction['predicted_profit_pct'] < -3:
                advice.append(f"AI predicts {ai_prediction['predicted_profit_pct']:.1f}% loss - avoid this trade")
        else:
            advice.append("AI is still learning - recommendations based on heuristics")
        
        # Risk-based advice
        if risk_assessment['overall_risk'] == 'HIGH':
            advice.append("High risk detected - consider skipping or using 10% normal position")
        elif risk_assessment['overall_risk'] == 'MEDIUM':
            advice.append("Moderate risk - reduce position size by 50%")
        else:
            advice.append("Low risk detected - safe for normal position size")
        
        # Historical performance advice
        if 'token_insights' in ai_prediction and ai_prediction['token_insights']['has_history']:
            success_rate = ai_prediction['token_insights']['success_rate']
            if success_rate > 70:
                advice.append("This token has strong historical performance")
            elif success_rate < 30:
                advice.append("This token has poor historical performance - extra caution advised")
        
        # Learning progress advice
        if learning_stats['total_trades_learned_from'] < 10:
            advice.append("AI learning just started - expect recommendations to improve over time")
        elif learning_stats['recent_success_rate'] > 70:
            advice.append("AI performing well recently - high confidence in recommendations")
        
        return advice
    
    def _calculate_confidence(self, learning_stats: Dict) -> str:
        """Calculate confidence level in recommendations"""
        if not learning_stats['models_trained']:
            return 'low'
        elif learning_stats['total_trades_learned_from'] < 50:
            return 'medium'
        elif learning_stats['overall_success_rate'] > 60:
            return 'high'
        else:
            return 'medium'
    
    def _calculate_position_size(self, risk_assessment: Dict) -> float:
        """Calculate recommended position size as percentage of normal"""
        risk_level = risk_assessment['overall_risk']
        risk_score = risk_assessment['risk_score']
        
        if risk_level == 'LOW':
            return 1.0  # 100% of normal position
        elif risk_level == 'MEDIUM':
            return 0.5  # 50% of normal position
        else:
            return 0.1  # 10% of normal position
    
    def _get_ai_status(self, learning_stats: Dict) -> str:
        """Get current AI learning status"""
        if not learning_stats['models_trained']:
            if learning_stats['total_trades_learned_from'] == 0:
                return 'initializing'
            else:
                return f"collecting_data ({learning_stats['trades_until_full_learning']} trades needed)"
        elif learning_stats['overall_success_rate'] > 65:
            return 'expert'
        elif learning_stats['overall_success_rate'] > 55:
            return 'proficient'
        else:
            return 'learning'
    
    def _get_general_recommendations(self, learning_stats: Dict) -> List[str]:
        """Get general trading recommendations"""
        recommendations = []
        
        if learning_stats['models_trained']:
            if learning_stats['overall_success_rate'] > 70:
                recommendations.append("AI performance is excellent - follow recommendations confidently")
            elif learning_stats['overall_success_rate'] > 55:
                recommendations.append("AI performance is good - recommendations are reliable")
            else:
                recommendations.append("AI is still learning - use conservative position sizes")
        else:
            recommendations.append("AI needs more data - start with small trades to build learning dataset")
        
        if learning_stats['total_trades_learned_from'] > 0:
            recommendations.append("Each trade helps the AI learn - consistent trading improves recommendations")
        
        return recommendations
    
    def _fallback_analysis(self) -> Dict:
        """Fallback analysis when main system fails"""
        return {
            'ai_prediction': {
                'predicted_profit_pct': 0,
                'predicted_risk_level': 'medium',
                'recommendation': 'Unable to analyze - proceed with caution',
                'model_confidence': 'error'
            },
            'risk_assessment': {
                'overall_risk': 'MEDIUM',
                'risk_score': 50,
                'risk_factors': ['Analysis unavailable'],
                'recommendation': 'Use conservative position size'
            },
            'personalized_advice': ['System error - trade at your own risk'],
            'confidence_level': 'low',
            'recommended_position_size': 0.25
        }

# Global instance for easy access
risk_advisor = SmartRiskAdvisor()