"""
models.py - Database Models
SQLAlchemy models for user data, wallets, positions, and trade logs
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    wallets = relationship("Wallet", back_populates="user")
    positions = relationship("Position", back_populates="user")
    trade_logs = relationship("TradeLog", back_populates="user")
    settings = relationship("Settings", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User(chat_id='{self.chat_id}', username='{self.username}')>"


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    label = Column(String(100), default="Main")
    pubkey = Column(String(44), nullable=False)  # Base58 encoded
    enc_privkey = Column(Text, nullable=False)  # Encrypted private key
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="wallets")

    def __repr__(self):
        return f"<Wallet(pubkey='{self.pubkey[:8]}...', label='{self.label}')>"


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mint = Column(String(44), nullable=False)
    symbol = Column(String(20))
    amount_raw = Column(String(50))  # Store as string to handle large numbers
    avg_price_sol = Column(Float)  # Average entry price in SOL
    status = Column(String(20), default="active")  # active, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="positions")

    def __repr__(self):
        return f"<Position(symbol='{self.symbol}', amount='{self.amount_raw}')>"


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mint = Column(String(44), nullable=False)
    symbol = Column(String(20))
    side = Column(String(10), nullable=False)  # 'buy' or 'sell'
    sol_amount = Column(Float, nullable=False)
    signature = Column(String(88))  # Transaction signature
    status = Column(String(20), nullable=False)  # 'success', 'failed', 'pending'
    pre_balance_raw = Column(String(50))  # Token balance before trade
    post_balance_raw = Column(String(50))  # Token balance after trade
    delta_raw = Column(String(50))  # Tokens received/sold
    error_message = Column(Text)  # Error details if failed
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="trade_logs")

    def __repr__(self):
        return f"<TradeLog(side='{self.side}', symbol='{self.symbol}', status='{self.status}')>"


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Trading settings
    slippage_bps = Column(Integer, default=150)  # 1.5% default
    priority_microlamports = Column(Integer, default=2000000)  # Priority fee
    spend_cap_sol = Column(Float, default=0.1)  # Max SOL per trade

    # Auto trading settings
    auto_tpsl = Column(Boolean, default=False)  # Auto take profit / stop loss
    stop_loss_pct = Column(Float, default=50.0)  # 50% stop loss
    take_profit_pct = Column(Float, default=200.0)  # 200% take profit

    # MORK holder requirements
    mork_min_snipe = Column(Float, default=0.1)  # 0.1 SOL worth of MORK for /snipe
    mork_min_fetch = Column(Float, default=1.0)  # 1.0 SOL worth of MORK for /fetch

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<Settings(user_id={self.user_id}, slippage={self.slippage_bps}bps)>"


class GlobalSettings(Base):
    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(200), nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GlobalSettings(key='{self.key}', value='{self.value}')>"
