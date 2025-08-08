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
    trading_mode = db.Column(db.String(16), nullable=True)  # 'snipe' or 'fetch' for VIP mode
    wallet_address = db.Column(db.String(64), nullable=True)
    contract_address = db.Column(db.String(64), nullable=True)
    token_name = db.Column(db.String(128), nullable=True)
    token_symbol = db.Column(db.String(32), nullable=True)
    entry_price = db.Column(db.Float, nullable=True)
    trade_amount = db.Column(db.Float, nullable=True)  # Amount in SOL or USD to trade
    stop_loss = db.Column(db.Float, nullable=True)
    take_profit = db.Column(db.Float, nullable=True)
    sell_percent = db.Column(db.Float, nullable=True)
    token_count = db.Column(db.Integer, default=1)  # Number of tokens to split SOL across  
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
    token_name = db.Column(db.String(128), nullable=True)  # Added for compatibility
    token_symbol = db.Column(db.String(32), nullable=True)  # Added for compatibility
    auto_mode = db.Column(db.Boolean, default=False)  # Added for compatibility
    status = db.Column(db.String(32), default="pending", nullable=False)  # Added for compatibility
    result_type = db.Column(db.String(32), default="pending", nullable=False)  # "profit", "loss", "partial_profit"
    profit_loss = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<TradeSimulation {self.chat_id}: {self.result_type}>'

class ActiveTrade(db.Model):
    """Model to store active live trades"""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(64), nullable=False, index=True)
    trade_type = db.Column(db.String(16), nullable=False)  # 'snipe', 'fetch', 'manual'
    contract_address = db.Column(db.String(64), nullable=False)
    token_name = db.Column(db.String(128), nullable=True)
    token_symbol = db.Column(db.String(32), nullable=True)
    entry_price = db.Column(db.Float, nullable=True)
    current_price = db.Column(db.Float, nullable=True)
    trade_amount = db.Column(db.Float, nullable=False)  # Amount in SOL
    tokens_purchased = db.Column(db.Float, nullable=True)  # Number of tokens bought
    stop_loss = db.Column(db.Float, nullable=False)
    take_profit = db.Column(db.Float, nullable=False)
    sell_percent = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(32), default="active", nullable=False)  # "active", "completed", "cancelled", "stopped"
    pnl = db.Column(db.Float, default=0.0)  # Current profit/loss in SOL
    pnl_percentage = db.Column(db.Float, default=0.0)  # Current P&L percentage
    tx_hash = db.Column(db.String(128), nullable=True)  # Transaction hash for entry
    exit_tx_hash = db.Column(db.String(128), nullable=True)  # Transaction hash for exit
    monitoring_active = db.Column(db.Boolean, default=True)  # Whether price monitoring is active
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<ActiveTrade {self.chat_id}: {self.token_symbol} - {self.status}>'
