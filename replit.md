# Mork Sniper Bot

## Overview

Mork Sniper Bot is a Telegram-based cryptocurrency trading bot designed for Solana blockchain tokens, particularly those launched on Pump.fun. The bot operates in two modes: a free simulation mode for testing and a paid live trading mode for users holding at least 100,000 $MORK tokens. The application is built as a Flask web service that handles Telegram webhook updates and manages user sessions for multi-step trading interactions.

## User Preferences

Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork Sniper Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text.

## Recent Changes

**2025-08-06**: Successfully implemented comprehensive live trading mode with wallet integration and $MORK token verification. Renamed commands to `/simulate` for practice mode and `/snipe` for live trading (previously `/snipe` and `/fetch`). Added dynamic threshold of 1 SOL worth of $MORK tokens, real Solana blockchain wallet balance checking, and complete live trading flow with risk warnings. Enhanced simulation mode with realistic ±10% variance system and `/whatif` performance tracking. Added instant Jupiter DEX purchase links for users with insufficient $MORK holdings and real-time price display. Both modes now fully operational with professional user experience.

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