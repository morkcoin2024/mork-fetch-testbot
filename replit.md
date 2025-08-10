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
- **AI Assistant**: A comprehensive AI assistant system with Flask webhook integration and dynamic model management. Features include `assistant_dev.py` for code generation, `assistant_generate_sync()` for webhook compatibility, and `/assistant_model` commands for real-time model switching. The system supports multiple AI models (GPT-4o, Claude-3.5-Sonnet, GPT-5-Thinking) with intelligent fallback (preferred model → gpt-4o on failure). Persistent model storage via `.assistant_model` file enables selection persistence across restarts. Admin-only access with comprehensive security controls. Flask webhook integration provides synchronous AI assistance without async complications.
- **Enhanced Tri-Source Token Engine with Pump.fun Enrichment**: A comprehensive tri-source token filtering and scoring architecture with real-time blockchain monitoring, intelligent fallback systems, and advanced Pump.fun enrichment capabilities. Features include enhanced `data_fetcher.py` (df-6) with tri-source integration (On-chain + Pump.fun + DexScreener), intelligent on-chain watcher via `pump_chain.py` for real-time Solana blockchain monitoring, dual-layer on-chain integration (primary 15min ultra-fresh + 60min fallback backup), advanced Pump.fun enrichment via `pumpfun_enrich.py` with comprehensive DexScreener metadata integration, source-aware deduplication with priority hierarchy (pumpfun-enriched > pumpfun-chain > pumpfun > dexscreener), advanced risk scoring with renounced authority bonuses, smart ranking algorithm (source → risk → liquidity), production-grade error handling with intelligent fallback when REST APIs fail, real-time event publishing via `eventbus.py` for live system monitoring, flexible JSON parsing supporting multiple API formats, timestamp normalization, enhanced metadata extraction with DexScreener liquidity/volume/market cap data, source tagging (⚡ Pump.fun-enriched, 🔗 On-chain, 🟢 Pump.fun, 🔵 DexScreener), bulk enrichment pipeline for high-throughput processing, and the comprehensive `fetch_and_rank()` function for unified tri-source data processing with resilient fallback architecture and real-time event streaming. Real-time configuration management via Telegram commands with Flask webhook integration providing synchronous multi-source data processing and enterprise-grade reliability.
- **Live Monitoring Dashboard with Token-Gated Streaming**: Professional real-time monitoring interface at `/monitor` with secure token-gated event streaming via `/events` endpoint. Features include matrix-style monitoring dashboard with Mork branding, Server-Sent Events (SSE) with compact JSON serialization for efficient bandwidth usage, token-based authentication via `LIVE_TOKEN` environment variable, automatic client reconnection with 1000ms retry interval, keepalive comments for connection maintenance, thread-safe subscriber management with automatic cleanup, manual fetch triggers with background processing, live statistics tracking (events, sources, performance metrics), responsive grid layout with real-time uptime counter, and comprehensive event timeline visualization. Enhanced CORS support and production-ready streaming architecture provide enterprise-grade observability for the complete trading system.
- **Compact Live Console Interface**: Ultra-lightweight real-time event console at `/live` endpoint with token-gated secure access and optimized performance. Features include minimal 593-byte HTML template with monospace GitHub-style dark theme, real-time EventSource streaming with automatic reconnection, sticky header with connection status indicator, newest-first event display with automatic DOM cleanup (500-event limit), clean ISO timestamp formatting, and zero external dependencies. Performance optimizations include minified CSS/JavaScript, event prepending for efficient display, built-in retry mechanisms, and seamless token parameter passthrough. Navigation integration provides direct access from main dashboard with consistent Mork branding across all monitoring interfaces.
- **Comprehensive Event Publishing System**: Real-time event tracking across all system components with `webhook.update` events for user interactions, `command.route` events for command initiation, `admin.command` events for administrative operations, `command.done` events for completion tracking with success/failure status, `command.error` events for exception monitoring with detailed error messages, source-specific data monitoring (`fetch.pumpfun.status`, `fetch.dexscreener.status`, `fetch.onchain.status`) with individual source performance tracking, granular yield events (`fetch.pumpfun.yield`, `fetch.dex.search`, `fetch.dex.pairs`, `fetch.onchain.yield`) for parameter optimization, early discovery tracking (`fetch.onchain.early`, `fetch.pumpfun.early`, `fetch.dex.early`) for real-time token discovery monitoring, complete data fetching lifecycle events (`fetch_started`, `source_complete`, `fallback_activated`, `fetch_completed`), and system performance monitoring. Event data includes user identification, command tracking, success/failure analytics, detailed exception tracking with stack traces, source-specific performance metrics, token discovery statistics, filter efficiency measurement, failure reason categorization, and comprehensive error reporting. Thread-safe event bus with automatic subscriber management, compact JSON serialization, and secure token-gated access provides enterprise-grade system observability for debugging, analytics, performance optimization, proactive error detection, source reliability monitoring, and real-time monitoring of the complete Solana trading bot operation.
- **Telegram Integration**: Robust PTB v20+ integration with `ApplicationBuilder` pattern, webhook cleanup, group-based priority, graceful Flask fallback for PTB import conflicts, and comprehensive async admin monitoring commands (`/status`, `/logs_tail`, `/logs_stream`, `/logs_watch`, `/mode`) with admin alias variants (`/a_status`, `/a_logs_tail`, etc.) for legacy collision avoidance. Features real-time log capture, pattern-based alerting, enhanced file-based logging with rotation (1MB max, 3 backups), efficient async admin monitoring system with 4KB block file reading, task-based streaming, high-priority admin router with ApplicationHandlerStop support, multiple deployment patterns (CommandHandler, manual routing, text handler), and complete fallback compatibility for maximum deployment flexibility.
- **Enhanced Logging System**: Comprehensive dual-layer logging with `robust_logging.py` providing RotatingFileHandler (1MB max, 3 backups) and RingBufferHandler (12,000 line capacity). Features ultra-fast `/a_logs_tail` with ring buffer access, advanced argument parsing (`/a_logs_tail [n] [level=error|warn|info|all]`), intelligent level filtering, and hybrid file + ring buffer fallback for maximum reliability. Integration includes `_read_ring_tail()` helper in `alerts/telegram.py` for PTB compatibility and `_read_tail_file()` for timestamped file access with comprehensive error handling.
- **Enhanced Multi-Source Diagnostics**: Complete diagnostic system with `cmd_a_diag_fetch` providing live module reloading, comprehensive version tracking (alerts.telegram=tg-4, data_fetcher=df-4), real-time endpoint monitoring, and enhanced debugging capabilities. Features `/fetch_source pumpfun|dexscreener` for multi-source testing, DexScreener search API integration with proper search endpoint (`https://api.dexscreener.com/latest/dex/search`), intelligent retry logic with httpx, and production-grade diagnostic variable tracking with `LAST_JSON_URL/STATUS` monitoring.

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