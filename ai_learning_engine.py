"""
AI Learning Engine for Mork F.E.T.C.H Bot
Continuously learns from trade outcomes to improve recommendations and risk assessment
"""

import logging
import json
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import pickle
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error

logger = logging.getLogger(__name__)

Base = declarative_base()

@dataclass
class TradeOutcome:
    """Data class for storing trade outcomes"""
    token_mint: str
    token_name: str
    entry_price: float
    exit_price: float
    profit_loss_pct: float
    profit_loss_sol: float
    hold_duration_minutes: int
    market_cap_at_entry: float
    volume_24h_at_entry: float
    holder_count_at_entry: int
    safety_score: int
    pump_score: int
    was_profitable: bool
    risk_level: str  # 'low', 'medium', 'high'
    trade_timestamp: datetime
    
    def to_features(self) -> List[float]:
        """Convert to feature vector for ML"""
        return [
            self.entry_price,
            self.market_cap_at_entry,
            self.volume_24h_at_entry,
            self.holder_count_at_entry,
            self.safety_score,
            self.pump_score,
            self.hold_duration_minutes,
        ]

class TradeHistory(Base):
    """Database model for trade history"""
    __tablename__ = 'trade_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50), nullable=False)
    token_mint = Column(String(50), nullable=False)
    token_name = Column(String(100))
    entry_price = Column(Float)
    exit_price = Column(Float)
    profit_loss_pct = Column(Float)
    profit_loss_sol = Column(Float)
    hold_duration_minutes = Column(Integer)
    market_cap_at_entry = Column(Float)
    volume_24h_at_entry = Column(Float)
    holder_count_at_entry = Column(Integer)
    safety_score = Column(Integer)
    pump_score = Column(Integer)
    was_profitable = Column(Boolean)
    risk_level = Column(String(10))
    trade_timestamp = Column(DateTime, default=datetime.utcnow)
    features_json = Column(Text)  # Store feature vector as JSON
    
class TokenPerformance(Base):
    """Track individual token performance patterns"""
    __tablename__ = 'token_performance'
    
    id = Column(Integer, primary_key=True)
    token_mint = Column(String(50), unique=True, nullable=False)
    token_name = Column(String(100))
    total_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    avg_profit_pct = Column(Float, default=0.0)
    avg_loss_pct = Column(Float, default=0.0)
    avg_hold_time_minutes = Column(Integer, default=0)
    risk_score = Column(Float, default=0.5)  # 0-1, higher = riskier
    success_rate = Column(Float, default=0.0)  # percentage successful
    last_updated = Column(DateTime, default=datetime.utcnow)

class AILearningEngine:
    """Advanced AI system that learns from trade outcomes"""
    
    def __init__(self):
        self.db_url = os.environ.get('DATABASE_URL')
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # ML Models
        self.profit_predictor = GradientBoostingRegressor(n_estimators=100, random_state=42)
        self.risk_classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        
        # Model state
        self.models_trained = False
        self.min_trades_for_training = 20
        
        # Load existing models if available
        self._load_models()
        
    def record_trade_outcome(self, user_id: str, trade_data: Dict, outcome_data: Dict) -> None:
        """Record a completed trade outcome for learning"""
        try:
            # Calculate profit/loss
            entry_price = trade_data.get('entry_price', 0)
            exit_price = outcome_data.get('exit_price', 0)
            sol_amount = trade_data.get('sol_amount', 0)
            
            profit_loss_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            profit_loss_sol = profit_loss_pct / 100 * sol_amount
            
            # Create trade outcome object
            outcome = TradeOutcome(
                token_mint=trade_data.get('token_mint', ''),
                token_name=trade_data.get('token_name', ''),
                entry_price=entry_price,
                exit_price=exit_price,
                profit_loss_pct=profit_loss_pct,
                profit_loss_sol=profit_loss_sol,
                hold_duration_minutes=outcome_data.get('hold_duration_minutes', 0),
                market_cap_at_entry=trade_data.get('market_cap', 0),
                volume_24h_at_entry=trade_data.get('volume_24h', 0),
                holder_count_at_entry=trade_data.get('holder_count', 0),
                safety_score=trade_data.get('safety_score', 50),
                pump_score=trade_data.get('pump_score', 50),
                was_profitable=profit_loss_pct > 0,
                risk_level=self._assess_risk_level(trade_data),
                trade_timestamp=datetime.utcnow()
            )
            
            # Store in database
            trade_record = TradeHistory(
                user_id=user_id,
                token_mint=outcome.token_mint,
                token_name=outcome.token_name,
                entry_price=outcome.entry_price,
                exit_price=outcome.exit_price,
                profit_loss_pct=outcome.profit_loss_pct,
                profit_loss_sol=outcome.profit_loss_sol,
                hold_duration_minutes=outcome.hold_duration_minutes,
                market_cap_at_entry=outcome.market_cap_at_entry,
                volume_24h_at_entry=outcome.volume_24h_at_entry,
                holder_count_at_entry=outcome.holder_count_at_entry,
                safety_score=outcome.safety_score,
                pump_score=outcome.pump_score,
                was_profitable=outcome.was_profitable,
                risk_level=outcome.risk_level,
                trade_timestamp=outcome.trade_timestamp,
                features_json=json.dumps(outcome.to_features())
            )
            
            self.session.add(trade_record)
            self.session.commit()
            
            # Update token performance stats
            self._update_token_performance(outcome)
            
            # Retrain models periodically
            total_trades = self.session.query(TradeHistory).count()
            if total_trades >= self.min_trades_for_training and total_trades % 10 == 0:
                self._retrain_models()
                
            logger.info(f"Recorded trade outcome: {outcome.token_name} - {profit_loss_pct:.2f}% profit")
            
        except Exception as e:
            logger.error(f"Error recording trade outcome: {e}")
            self.session.rollback()
    
    def predict_trade_outcome(self, trade_data: Dict) -> Dict:
        """Predict expected profit and risk for a potential trade"""
        try:
            if not self.models_trained:
                return self._fallback_assessment(trade_data)
            
            # Extract features
            features = [
                trade_data.get('entry_price', 0),
                trade_data.get('market_cap', 0),
                trade_data.get('volume_24h', 0),
                trade_data.get('holder_count', 0),
                trade_data.get('safety_score', 50),
                trade_data.get('pump_score', 50),
                5,  # Expected hold time in minutes
            ]
            
            # Scale features
            features_scaled = self.scaler.transform([features])
            
            # Predict profit
            predicted_profit_pct = self.profit_predictor.predict(features_scaled)[0]
            
            # Predict risk level
            risk_proba = self.risk_classifier.predict_proba(features_scaled)[0]
            risk_levels = ['low', 'medium', 'high']
            predicted_risk = risk_levels[np.argmax(risk_proba)]
            
            # Get token-specific insights
            token_insights = self._get_token_insights(trade_data.get('token_mint', ''))
            
            return {
                'predicted_profit_pct': round(predicted_profit_pct, 2),
                'predicted_risk_level': predicted_risk,
                'risk_confidence': round(max(risk_proba) * 100, 1),
                'recommendation': self._generate_recommendation(predicted_profit_pct, predicted_risk),
                'token_insights': token_insights,
                'model_confidence': 'high' if self.models_trained else 'learning'
            }
            
        except Exception as e:
            logger.error(f"Error predicting trade outcome: {e}")
            return self._fallback_assessment(trade_data)
    
    def get_risk_assessment(self, trade_data: Dict) -> Dict:
        """Provide detailed risk assessment for a trade"""
        try:
            # Base risk factors
            risk_factors = []
            risk_score = 0
            
            # Market cap risk
            market_cap = trade_data.get('market_cap', 0)
            if market_cap < 10000:
                risk_factors.append("Very low market cap - high volatility risk")
                risk_score += 30
            elif market_cap < 100000:
                risk_factors.append("Low market cap - moderate volatility risk")
                risk_score += 15
            
            # Volume risk
            volume_24h = trade_data.get('volume_24h', 0)
            if volume_24h < 1000:
                risk_factors.append("Low trading volume - liquidity risk")
                risk_score += 25
            
            # Holder count risk
            holder_count = trade_data.get('holder_count', 0)
            if holder_count < 100:
                risk_factors.append("Few holders - concentration risk")
                risk_score += 20
            
            # Safety score risk
            safety_score = trade_data.get('safety_score', 50)
            if safety_score < 30:
                risk_factors.append("Low safety score - potential rug pull risk")
                risk_score += 35
            
            # Historical performance
            token_insights = self._get_token_insights(trade_data.get('token_mint', ''))
            if token_insights['success_rate'] < 30:
                risk_factors.append("Poor historical performance")
                risk_score += 20
            
            # Overall risk level
            if risk_score < 25:
                overall_risk = "LOW"
            elif risk_score < 60:
                overall_risk = "MEDIUM"
            else:
                overall_risk = "HIGH"
            
            return {
                'overall_risk': overall_risk,
                'risk_score': min(risk_score, 100),
                'risk_factors': risk_factors,
                'recommendation': self._get_risk_recommendation(overall_risk, risk_score)
            }
            
        except Exception as e:
            logger.error(f"Error in risk assessment: {e}")
            return {
                'overall_risk': 'MEDIUM',
                'risk_score': 50,
                'risk_factors': ['Unable to assess - proceed with caution'],
                'recommendation': 'Start with small position size'
            }
    
    def get_learning_stats(self) -> Dict:
        """Get statistics about the AI learning progress"""
        try:
            total_trades = self.session.query(TradeHistory).count()
            profitable_trades = self.session.query(TradeHistory).filter(
                TradeHistory.was_profitable == True
            ).count()
            
            success_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Recent performance (last 30 days)
            recent_date = datetime.utcnow() - timedelta(days=30)
            recent_trades = self.session.query(TradeHistory).filter(
                TradeHistory.trade_timestamp >= recent_date
            ).all()
            
            recent_success_rate = 0
            if recent_trades:
                recent_profitable = sum(1 for t in recent_trades if t.was_profitable)
                recent_success_rate = recent_profitable / len(recent_trades) * 100
            
            return {
                'total_trades_learned_from': total_trades,
                'overall_success_rate': round(success_rate, 1),
                'recent_success_rate': round(recent_success_rate, 1),
                'models_trained': self.models_trained,
                'learning_phase': 'active' if total_trades >= self.min_trades_for_training else 'collecting_data',
                'trades_until_full_learning': max(0, self.min_trades_for_training - total_trades)
            }
            
        except Exception as e:
            logger.error(f"Error getting learning stats: {e}")
            return {
                'total_trades_learned_from': 0,
                'overall_success_rate': 0,
                'models_trained': False,
                'learning_phase': 'initializing'
            }
    
    def _assess_risk_level(self, trade_data: Dict) -> str:
        """Assess risk level based on trade parameters"""
        risk_score = 0
        
        # Market cap factor
        market_cap = trade_data.get('market_cap', 0)
        if market_cap < 50000:
            risk_score += 2
        elif market_cap < 200000:
            risk_score += 1
        
        # Safety score factor
        safety_score = trade_data.get('safety_score', 50)
        if safety_score < 30:
            risk_score += 2
        elif safety_score < 60:
            risk_score += 1
        
        # Volume factor
        volume_24h = trade_data.get('volume_24h', 0)
        if volume_24h < 5000:
            risk_score += 1
        
        if risk_score >= 4:
            return 'high'
        elif risk_score >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _update_token_performance(self, outcome: TradeOutcome) -> None:
        """Update performance statistics for a specific token"""
        try:
            token_perf = self.session.query(TokenPerformance).filter(
                TokenPerformance.token_mint == outcome.token_mint
            ).first()
            
            if not token_perf:
                token_perf = TokenPerformance(
                    token_mint=outcome.token_mint,
                    token_name=outcome.token_name
                )
                self.session.add(token_perf)
            
            token_perf.total_trades += 1
            if outcome.was_profitable:
                token_perf.profitable_trades += 1
                token_perf.avg_profit_pct = (
                    (token_perf.avg_profit_pct * (token_perf.profitable_trades - 1) + outcome.profit_loss_pct) / 
                    token_perf.profitable_trades
                )
            else:
                token_perf.avg_loss_pct = (
                    (token_perf.avg_loss_pct * (token_perf.total_trades - token_perf.profitable_trades - 1) + 
                     abs(outcome.profit_loss_pct)) / 
                    (token_perf.total_trades - token_perf.profitable_trades)
                )
            
            token_perf.success_rate = token_perf.profitable_trades / token_perf.total_trades * 100
            token_perf.avg_hold_time_minutes = (
                (token_perf.avg_hold_time_minutes * (token_perf.total_trades - 1) + outcome.hold_duration_minutes) / 
                token_perf.total_trades
            )
            token_perf.last_updated = datetime.utcnow()
            
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Error updating token performance: {e}")
            self.session.rollback()
    
    def _retrain_models(self) -> None:
        """Retrain ML models with latest data"""
        try:
            logger.info("Retraining AI models with latest trade data...")
            
            # Get all trade data
            trades = self.session.query(TradeHistory).all()
            
            if len(trades) < self.min_trades_for_training:
                return
            
            # Prepare features and targets
            features = []
            profit_targets = []
            risk_targets = []
            
            for trade in trades:
                feature_vector = json.loads(trade.features_json)
                features.append(feature_vector)
                profit_targets.append(trade.profit_loss_pct)
                risk_targets.append(['low', 'medium', 'high'].index(trade.risk_level))
            
            features = np.array(features)
            profit_targets = np.array(profit_targets)
            risk_targets = np.array(risk_targets)
            
            # Scale features
            self.scaler.fit(features)
            features_scaled = self.scaler.transform(features)
            
            # Train profit predictor
            self.profit_predictor.fit(features_scaled, profit_targets)
            
            # Train risk classifier
            self.risk_classifier.fit(features_scaled, risk_targets)
            
            self.models_trained = True
            
            # Save models
            self._save_models()
            
            logger.info(f"AI models retrained with {len(trades)} trade examples")
            
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
    
    def _get_token_insights(self, token_mint: str) -> Dict:
        """Get historical insights for a specific token"""
        try:
            token_perf = self.session.query(TokenPerformance).filter(
                TokenPerformance.token_mint == token_mint
            ).first()
            
            if token_perf:
                return {
                    'total_trades': token_perf.total_trades,
                    'success_rate': round(token_perf.success_rate, 1),
                    'avg_profit_when_win': round(token_perf.avg_profit_pct, 2),
                    'avg_loss_when_lose': round(token_perf.avg_loss_pct, 2),
                    'avg_hold_time_minutes': token_perf.avg_hold_time_minutes,
                    'has_history': True
                }
            else:
                return {
                    'total_trades': 0,
                    'success_rate': 50,  # Default neutral
                    'avg_profit_when_win': 0,
                    'avg_loss_when_lose': 0,
                    'avg_hold_time_minutes': 0,
                    'has_history': False
                }
                
        except Exception as e:
            logger.error(f"Error getting token insights: {e}")
            return {'has_history': False, 'success_rate': 50}
    
    def _generate_recommendation(self, predicted_profit: float, risk_level: str) -> str:
        """Generate trading recommendation based on predictions"""
        if predicted_profit > 10 and risk_level == 'low':
            return "STRONG BUY - High profit potential with low risk"
        elif predicted_profit > 5 and risk_level in ['low', 'medium']:
            return "BUY - Good profit potential with manageable risk"
        elif predicted_profit > 0 and risk_level == 'low':
            return "WEAK BUY - Small profit potential but safe"
        elif predicted_profit < -5 or risk_level == 'high':
            return "AVOID - High risk or negative profit expected"
        else:
            return "NEUTRAL - Unclear signals, proceed with caution"
    
    def _get_risk_recommendation(self, risk_level: str, risk_score: int) -> str:
        """Get recommendation based on risk assessment"""
        if risk_level == 'LOW':
            return "Safe to trade with normal position size"
        elif risk_level == 'MEDIUM':
            return "Reduce position size by 50% due to moderate risk"
        else:
            return "Avoid trade or use very small position size (10% of normal)"
    
    def _fallback_assessment(self, trade_data: Dict) -> Dict:
        """Fallback assessment when ML models aren't trained yet"""
        safety_score = trade_data.get('safety_score', 50)
        pump_score = trade_data.get('pump_score', 50)
        
        # Simple heuristic-based assessment
        if safety_score > 70 and pump_score > 70:
            predicted_profit = 8.0
            risk_level = 'low'
        elif safety_score > 50 and pump_score > 50:
            predicted_profit = 3.0
            risk_level = 'medium'
        else:
            predicted_profit = -2.0
            risk_level = 'high'
        
        return {
            'predicted_profit_pct': predicted_profit,
            'predicted_risk_level': risk_level,
            'risk_confidence': 60.0,
            'recommendation': self._generate_recommendation(predicted_profit, risk_level),
            'token_insights': {'has_history': False},
            'model_confidence': 'learning'
        }
    
    def _save_models(self) -> None:
        """Save trained models to disk"""
        try:
            models_data = {
                'profit_predictor': self.profit_predictor,
                'risk_classifier': self.risk_classifier,
                'scaler': self.scaler,
                'models_trained': self.models_trained
            }
            
            with open('ai_models.pkl', 'wb') as f:
                pickle.dump(models_data, f)
                
        except Exception as e:
            logger.error(f"Error saving models: {e}")
    
    def _load_models(self) -> None:
        """Load existing trained models from disk"""
        try:
            with open('ai_models.pkl', 'rb') as f:
                models_data = pickle.load(f)
                
            self.profit_predictor = models_data['profit_predictor']
            self.risk_classifier = models_data['risk_classifier']
            self.scaler = models_data['scaler']
            self.models_trained = models_data['models_trained']
            
            logger.info("Loaded existing AI models successfully")
            
        except FileNotFoundError:
            logger.info("No existing models found - will train from scratch")
        except Exception as e:
            logger.error(f"Error loading models: {e}")