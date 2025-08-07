# Mork F.E.T.C.H Bot

## Overview

Mork F.E.T.C.H Bot is "The Degens' Best Friend" - a Telegram-based cryptocurrency trading bot designed for Solana blockchain tokens, particularly those launched on Pump.fun. F.E.T.C.H. stands for "Fast Execution, Trade Control Handler". The bot operates in two modes: Free Mode (simulation for learning) and V.I.P. Mode (live trading for users holding 1 SOL worth of $MORK tokens). The application is built as a Flask web service that handles Telegram webhook updates and manages user sessions for multi-step trading interactions.

## User Preferences

Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## Recent Changes

**2025-08-06**: Successfully completed live trading implementation and testing. Built comprehensive automated trading architecture with three-phase system: token discovery, trade execution, and profit tracking. Added `pump_scanner.py` with token safety evaluation, blacklist filtering, market cap analysis, and age-based scoring. Created `trade_executor.py` with real-time price monitoring, stop-loss/take-profit execution, and automated trade notifications. VIP FETCH mode provides fully automated token discovery from Pump.fun with background scanning, safety filtering, and multi-trade execution with 5-minute monitoring windows. Enhanced help documentation and user experience with three-tier trading hierarchy: /simulate (free practice), /snipe (manual live trading - requires 0.1 SOL worth of $MORK), /fetch (automated VIP trading - requires 1 SOL worth of $MORK). Updated official $MORK purchase links to Jupiter: https://jup.ag/swap?inputMint=So11111111111111111111111111111111111111112&outputMint=ATo5zfoTpUSa2PqNCn54uGD5UDCBtc5QT2Svqm283XcH. Bot currently accessible at @MorkSniperBot on Telegram. **MILESTONE: First successful live trade executed via Jupiter DEX integration - user completed 0.1 SOL → MORK swap with Phantom wallet signing. Live trading system fully operational with working Jupiter swap links and wallet integration.**

**2025-08-07 (Latest)**: **SMART TRADING ROUTER + DISPLAY FIXES COMPLETED!** Implemented comprehensive smart trading platform selection based on user's rule: "If token ends in 'pump' → trade through Pump.fun (unless bonded) → Jupiter for bonded pump tokens + all other Solana projects". Created `smart_trading_router.py` with intelligent platform analysis that checks bonding curve status via Pump.fun API and Jupiter pricing. **TRADING LOGIC**: Tokens ending in "pump" are analyzed for bonding completion - unbonded tokens use Pump.fun bonding curves, bonded tokens graduate to Jupiter DEX. All non-pump tokens use Jupiter by default. **CHATGPT DIAGNOSTICS INTEGRATED**: Added `wallet_diagnostics.py` with comprehensive balance checking (lamports verification), enhanced `/executed` command with pre-trade wallet validation, added `/diagnostic` and `/checkwallet` commands for manual wallet health checking. **TECHNICAL IMPLEMENTATION**: Smart router automatically detects token platform via market cap analysis (~$69K graduation threshold), Jupiter price availability, and fallback assumptions. Enhanced error handling with detailed SOL/lamports reporting integrated with existing burner wallet system. **VIP FETCH ENHANCED**: Automatic token discovery now uses smart routing - MoonPump/ApePump/etc. use Pump.fun bonding curves, while bonded pump tokens and regular Solana tokens use Jupiter DEX. All previous features maintained: fee collection, multi-token diversification, AI filtering, real-time monitoring. **DISPLAY FIXES**: Updated all user interface messages to show "Smart Platform Trading (Pump.fun + Jupiter)" instead of misleading "Jupiter DEX only" messages. Fixed smart router function parameter errors for proper trade execution.

## System Architecture

### Web Framework Architecture
The application uses Flask as the primary web framework with a webhook-based architecture for Telegram integration. The main application entry point (`app.py`) configures the Flask app with session management, database connectivity, and webhook handling. The bot logic is separated into a dedicated module (`bot.py`) that processes Telegram updates and manages user interactions.

### Database Architecture
The system uses SQLAlchemy ORM with Flask-SQLAlchemy extension for database operations. Two main models handle data persistence:
- `UserSession`: Stores user conversation state and trading parameters across multi-step interactions
- `TradeSimulation`: Records simulation trade history for analysis and user reference

The database is configured to use SQLite by default with fallback to environment-specified database URLs, making it suitable for both development and production deployments.

### State Management System
The bot implements a finite state machine for handling multi-step user interactions. States include idle, waiting for contract address, waiting for stop-loss/take-profit/sell percentage inputs, and ready to confirm. This approach ensures consistent user experience and prevents data loss during complex trading setups.

### Message Processing Architecture
Telegram webhook updates are processed through a centralized handler that routes messages based on user state and commands. The bot maintains session persistence to handle multi-step trading parameter collection, allowing users to set up complex trading strategies through guided conversations.

### Trading Modes Architecture
The system is designed with two distinct operational modes:
- Simulation mode: Provides risk-free testing of trading strategies without real token transactions
- Live trading mode: Intended for verified users with sufficient $MORK token holdings (not fully implemented in current codebase)

## External Dependencies

### Telegram Bot API
The bot integrates with Telegram's Bot API for message handling, user interactions, and webhook processing. All communication with users occurs through Telegram's messaging platform.

### Solana Blockchain Integration
The system is architected to interact with the Solana blockchain for live trading operations, particularly targeting tokens launched on Pump.fun platform. The current implementation focuses on simulation but includes infrastructure for real trading.

### Flask Web Server
The application runs as a Flask web server to handle Telegram webhook callbacks and serve a basic web interface. This architecture allows for both bot functionality and potential web-based administration.

### Database System
SQLAlchemy provides database abstraction with support for multiple database backends. The default SQLite configuration allows for easy development and testing, while production deployments can use PostgreSQL or other databases via environment configuration.

### Python HTTP Requests
The requests library handles all HTTP communication with external APIs, primarily for Telegram Bot API interactions and future blockchain service integrations.