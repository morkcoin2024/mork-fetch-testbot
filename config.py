"""
Configuration settings for Mork F.E.T.C.H Bot
Environment variables and system constants
"""

import os

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_MODEL = os.getenv("ASSISTANT_MODEL", "gpt-5-thinking")  # AI model for assistant code generation

# Assistant Configuration  
ASSISTANT_ADMIN_TELEGRAM_ID = int(os.getenv("ASSISTANT_ADMIN_TELEGRAM_ID", "0"))
ASSISTANT_WRITE_GUARD = os.getenv("ASSISTANT_WRITE_GUARD", "OFF")  # "OFF" = dry-run; "ON" = actually write
ASSISTANT_GIT_BRANCH = os.getenv("ASSISTANT_GIT_BRANCH", "")  # If set, stage changes on this branch
ASSISTANT_FAILSAFE = os.getenv("ASSISTANT_FAILSAFE", "OFF").upper()  # "ON" or "OFF"

# Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Trading Configuration
MORK_MINT = "ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH"
JUPITER_API_BASE = "https://quote-api.jup.ag/v6"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# Safety Limits
MAX_TRADE_SOL = 0.5
DAILY_SPEND_LIMIT = 1.0
MIN_MORK_FOR_SNIPE = 0.1  # SOL worth
MIN_MORK_FOR_FETCH = 1.0  # SOL worth

# System Settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"