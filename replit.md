# Mork F.E.T.C.H Bot

## Overview
Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates. The business vision is to provide a user-friendly, automated trading solution for Solana degens, enhancing their trading efficiency and profitability.

## User Preferences
Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture
The application uses Flask with a webhook-based architecture for Telegram integration, managing session states and database persistence with SQLAlchemy. A finite state machine handles multi-step user interactions. UI/UX aligns with Mork Coin branding. The system supports Simulation, Manual Live Trading (`/snipe`), and Automated VIP Trading (`/fetch`) modes.

**Latest Updates:**
- **COMPLETED**: Enhanced EventBus migration to new events.py with deduplication cache, thread-safe operations, and backward compatibility
- **COMPLETED**: Implemented wallet.py burner wallet MVP with per-user Solana keypair generation, balance checking, and JSON persistence (development use only)
- **COMPLETED**: Integrated wallet system with Telegram bot via `/wallet` command for admin access to burner wallet info
- **COMPLETED**: Patched app.py with event bus integration including imports for BUS, rules, and wallet modules
- **COMPLETED**: Implemented _normalize_token() helper function and _on_new_token() subscriber for NEW_TOKEN events with rules validation and Telegram notifications

**Core Architectural Decisions & Features:**
- **Unified Single-Process Architecture:** Gunicorn configured for single-worker to ensure webhook handlers and scanner threads share the same process and data, resolving process isolation issues.
- **Multi-Source Token Discovery:** Integrates Birdeye (HTTP & WebSocket), Jupiter, and Solscan Pro for comprehensive token discovery, enrichment, and scoring. Birdeye WebSocket includes launchpad stream priority, real-time processing, and automatic reconnection. Solscan Pro features auth header rotation, rate-limited discovery, and intelligent caching.
- **AI Assistant System:** Flask webhook integration supporting multiple AI models (e.g., GPT-4o, Claude-3.5-Sonnet) with intelligent fallback and persistent storage.
- **Enhanced Tri-Source Token Engine:** Comprehensive filtering and scoring architecture with real-time blockchain monitoring and advanced Solana RPC enrichment.
- **Live Monitoring Dashboard & Console:** Secure, token-gated interfaces for real-time event streaming via Server-Sent Events (SSE) and an ultra-lightweight console.
- **Enhanced Event Publishing System:** Advanced real-time event tracking with deduplication capabilities across all system components, featuring a thread-safe publish/subscribe architecture, configurable cache windows, and comprehensive event fingerprinting.
- **Telegram Integration:** Direct webhook processing with bypassed PTB dependency, comprehensive admin command routing, and real-time Telegram API integration.
- **Enhanced Logging System:** Dual-layer logging with `RotatingFileHandler` and `RingBufferHandler`.
- **Enhanced Multi-Source Diagnostics:** Complete diagnostic system for live module reloading, version tracking, real-time endpoint monitoring, and debugging, including a comprehensive scan command system.
- **Production Readiness:** Robust system with reliable thread-safe data, enterprise-grade timestamp precision, and automatic recovery capabilities for WebSocket connections.
- **Multiple Command Processing:** Webhook handles multiple Telegram commands in a single message with sequential processing and combined responses.

## External Dependencies
- **Telegram Bot API**: For all message handling and user interactions.
- **Solana Blockchain Integration**: Interacts with the Solana blockchain for live trading on Pump.fun.
- **Flask Web Server**: The application's web server for webhook callbacks and web interface.
- **Database System**: SQLAlchemy for database abstraction (defaults to SQLite).
- **Python HTTP Requests**: The `requests` library for all HTTP communication with external APIs.
- **OpenAI API**: For AI assistant functionalities.
- **Jupiter DEX**: For decentralized exchange operations on Solana.
- **PumpPortal Lightning Transaction API**: The core trading engine for verified token delivery on Pump.fun.
- **Birdeye API/WebSocket**: For real-time token data and discovery.
- **token.jup.ag API**: For fetching Jupiter token lists.
- **Solscan API**: For blockchain data and new token discovery.
- **DexScreener API**: For Solana pairs monitoring and token data.
```