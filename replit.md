# Mork F.E.T.C.H Bot

## Overview

Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates. The business vision is to provide a user-friendly, automated trading solution for Solana degens, enhancing their trading efficiency and profitability.

## User Preferences

Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture

### Web Framework Architecture
The application utilizes Flask with a webhook-based architecture for Telegram integration. `app.py` handles Flask configuration, session management, database connectivity, and webhook processing. Bot logic in `bot.py` processes Telegram updates.

### Database Architecture
SQLAlchemy ORM with Flask-SQLAlchemy manages data persistence. `UserSession` stores conversation states and trading parameters, while `TradeSimulation` records simulation history. SQLite is default, with environment-variable support for other databases.

### State Management System
A finite state machine manages multi-step user interactions, including states for contract address input, financial parameters (stop-loss/take-profit/sell percentage), and confirmation. This ensures consistent user experience and data integrity.

### Message Processing Architecture
Telegram webhook updates are routed based on user state and commands. Session persistence is maintained to facilitate multi-step trading parameter collection.

### Trading Modes Architecture
The system supports three distinct trading modes:
- **Simulation mode**: Risk-free testing of strategies.
- **Manual live trading mode (`/snipe`)**: Direct token purchasing requiring user confirmation and 0.1 SOL worth of $MORK.
- **Automated VIP trading mode (`/fetch`)**: Fully automated token discovery and trading, requiring 1 SOL worth of $MORK.
- **Trading Engine**: Utilizes PumpPortal Lightning Transaction API for verified token delivery.

### UI/UX Decisions
The bot adopts Mork Coin's branding guidelines, using green primary and light green accent colors. Text styling follows specific color rules for brand consistency. Playful, dog-themed messaging and meme-friendly language cater to the target crypto audience.

### Technical Implementations
- **AI Assistant**: A lightweight AI assistant system integrated with OpenAI GPT-4o for autonomous code generation and system management. It includes `assistant_dev_lite.py`, `cmd_assistant()`, `cmd_assistant_toggle()`, and `cmd_whoami()`. Safety features include admin-only access, write guard (dry-run by default), an emergency kill switch, and size limits for diffs. Intelligent model fallback attempts a preferred model (e.g., gpt-5-thinking) and defaults to gpt-4o if unavailable. Persistent model management via a local file (`.assistant_model`) allows dynamic switching at runtime without environment variable changes. Telegram commands (`/assistant_model`) enable real-time model management.
- **Token Filtering Engine**: A comprehensive rules-based token filtering and scoring architecture configured via YAML (`rules.yaml`). It includes `rules_loader.py` and `token_filter.py`. Two profiles exist: Conservative (strict safety) and Degen (relaxed thresholds). A six-category weighted scoring system covers liquidity, ownership, safety, holders, momentum, and social metrics. Features include threshold-based scoring, hard filter rejection, configurable output limits, and real-time profile switching via Telegram commands (`/rules_show`, `/rules_profile`, `/rules_set`, `/rules_reload`).
- **Telegram Integration**: Robust PTB v20+ integration with `ApplicationBuilder` pattern, webhook cleanup, group-based priority, and graceful Flask fallback for PTB import conflicts.

## External Dependencies

### Telegram Bot API
Used for all message handling, user interactions, and webhook processing with the Telegram platform.

### Solana Blockchain Integration
Interacts with the Solana blockchain for live trading, specifically targeting tokens on Pump.fun. The infrastructure supports real trading operations.

### Flask Web Server
Serves as the application's web server, handling Telegram webhook callbacks and providing a basic web interface.

### Database System
SQLAlchemy provides database abstraction. While SQLite is default for development, production deployments can leverage PostgreSQL or other databases via environment configuration.

### Python HTTP Requests
The `requests` library handles all HTTP communication with external APIs, including the Telegram Bot API and future blockchain service integrations.

### OpenAI API
Integrated for AI assistant functionalities, leveraging models like GPT-4o for code generation and system management.

### Jupiter DEX
Integrated for decentralized exchange operations, enabling token swaps on the Solana blockchain.

### PumpPortal Lightning Transaction API
Used as the core trading engine for verified token delivery on the Pump.fun platform.