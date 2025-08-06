from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class UserSession(db.Model):
    """Model to store user session data for multi-step interactions"""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    state = db.Column(db.String(32), default="idle", nullable=False)
    wallet_address = db.Column(db.String(64), nullable=True)
    contract_address = db.Column(db.String(64), nullable=True)
    token_name = db.Column(db.String(128), nullable=True)
    token_symbol = db.Column(db.String(32), nullable=True)
    entry_price = db.Column(db.Float, nullable=True)
    trade_amount = db.Column(db.Float, nullable=True)  # Amount in SOL or USD to trade
    stop_loss = db.Column(db.Float, nullable=True)
    take_profit = db.Column(db.Float, nullable=True)
    sell_percent = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserSession {self.chat_id}>'

class TradeSimulation(db.Model):
    """Model to store simulation trade history"""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(64), nullable=False, index=True)
    contract_address = db.Column(db.String(64), nullable=False)
    entry_price = db.Column(db.Float, nullable=True)
    trade_amount = db.Column(db.Float, nullable=True)  # Amount traded in simulation
    stop_loss = db.Column(db.Float, nullable=False)
    take_profit = db.Column(db.Float, nullable=False)
    sell_percent = db.Column(db.Float, nullable=False)
    result_type = db.Column(db.String(32), default="pending", nullable=False)  # "profit", "loss", "partial_profit"
    profit_loss = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TradeSimulation {self.chat_id}: {self.result_type}>'
