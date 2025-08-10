# Mork F.E.T.C.H Bot

## Overview
Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates. The business vision is to provide a user-friendly, automated trading solution for Solana degens, enhancing their trading efficiency and profitability.

## User Preferences
Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture
The application uses Flask with a webhook-based architecture for Telegram integration, managing session states and database persistence with SQLAlchemy. A finite state machine handles multi-step user interactions for consistent experience. The system supports Simulation, Manual Live Trading (`/snipe`), and Automated VIP Trading (`/fetch`) modes. UI/UX aligns with Mork Coin branding.

Key technical implementations include:
- **AI Assistant**: A comprehensive AI assistant system with Flask webhook integration and dynamic model management, supporting multiple AI models (GPT-4o, Claude-3.5-Sonnet, GPT-5-Thinking) with intelligent fallback and persistent model storage.
- **Enhanced Tri-Source Token Engine with Solana RPC Integration**: A comprehensive tri-source token filtering and scoring architecture with real-time blockchain monitoring, intelligent fallback systems, and advanced Solana RPC enrichment. It integrates on-chain data, Pump.fun, and DexScreener, with advanced risk scoring and a smart ranking algorithm.
- **Live Monitoring Dashboard**: A professional real-time monitoring interface with secure token-gated event streaming via Server-Sent Events (SSE).
- **Compact Live Console Interface**: An ultra-lightweight real-time event console with token-gated secure access and optimized performance.
- **Comprehensive Event Publishing System**: Real-time event tracking across all system components, publishing detailed events for user interactions, commands, errors, data fetching, and system performance.
- **Telegram Integration**: Robust PTB v20+ integration with webhook cleanup, group-based priority, graceful Flask fallback, and comprehensive async admin monitoring commands.
- **Enhanced Logging System**: Dual-layer logging with RotatingFileHandler and RingBufferHandler for efficient log access and reliability.
- **Enhanced Multi-Source Diagnostics**: A complete diagnostic system for live module reloading, version tracking, real-time endpoint monitoring, and debugging.
- **Comprehensive Scan Command System**: Full scan diagnostic infrastructure for system health monitoring and validation.
- **Birdeye Token Scanner Integration**: Real-time Solana token discovery system via Birdeye API for fresh token monitoring with configurable scan intervals and deduplication.

## External Dependencies
- **Telegram Bot API**: For all message handling and user interactions.
- **Solana Blockchain Integration**: Interacts with the Solana blockchain for live trading on Pump.fun.
- **Flask Web Server**: The application's web server for webhook callbacks and web interface.
- **Database System**: SQLAlchemy for database abstraction, defaulting to SQLite but supporting others via environment configuration.
- **Python HTTP Requests**: The `requests` library for all HTTP communication with external APIs.
- **OpenAI API**: For AI assistant functionalities.
- **Jupiter DEX**: For decentralized exchange operations on Solana.
- **PumpPortal Lightning Transaction API**: The core trading engine for verified token delivery on Pump.fun.