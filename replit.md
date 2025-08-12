# Mork F.E.T.C.H Bot

## Overview
Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates. The business vision is to provide a user-friendly, automated trading solution for Solana degens, enhancing their trading efficiency and profitability.

## User Preferences
Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture
The application uses Flask with a webhook-based architecture for Telegram integration, managing session states and database persistence with SQLAlchemy. A finite state machine handles multi-step user interactions for consistent experience. The system supports Simulation, Manual Live Trading (`/snipe`), and Automated VIP Trading (`/fetch`) modes. UI/UX aligns with Mork Coin branding.

**Current Configuration: Multi-Source Token Discovery + Enhanced Admin Commands (August 12, 2025)**
- **Birdeye HTTP Scanner**: Operational at 8-second intervals with API key 37c50ab5a1ac451980a1998b1c05fbf6
- **Jupiter Scanner**: Fully integrated and operational, fetching 287K+ tokens from https://token.jup.ag/all?includeCommunity=true
- **Solscan Pro Scanner**: Production-ready implementation with multi-endpoint support, safe header handling, and retry logic. Auto-initializes when FEATURE_SOLSCAN=on and SOLSCAN_API_KEY provided
- **WebSocket**: Disabled via FEATURE_WS=off with DisabledWS class implementation 
- **Centralized Scanner Registry**: SCANNERS global dictionary provides unified management of all scanner instances with _ensure_scanners() auto-registration
- **Enhanced Admin Commands**: Unified scanner control through /scan_start (starts all), /scan_stop (stops all), /scan_status (shows all sources), plus comprehensive diagnostic commands (/pumpfunstatus, /pumpfunprobe, /solscanstats, /solscan_start, /solscan_stop)
- **Fault-Tolerant Scanning Loop**: Multi-source scanning with individual error handling, API courtesy delays, and graceful failure recovery

Key technical implementations include:
- **AI Assistant**: A comprehensive AI assistant system with Flask webhook integration and dynamic model management, supporting multiple AI models (GPT-4o, Claude-3.5-Sonnet, GPT-5-Thinking) with intelligent fallback and persistent model storage.
- **Enhanced Tri-Source Token Engine with Solana RPC Integration**: A comprehensive tri-source token filtering and scoring architecture with real-time blockchain monitoring, intelligent fallback systems, and advanced Solana RPC enrichment. It integrates on-chain data, Pump.fun, and DexScreener, with advanced risk scoring and a smart ranking algorithm.
- **Live Monitoring Dashboard**: A professional real-time monitoring interface with secure token-gated event streaming via Server-Sent Events (SSE).
- **Compact Live Console Interface**: An ultra-lightweight real-time event console with token-gated secure access and optimized performance.
- **Comprehensive Event Publishing System**: Real-time event tracking across all system components, publishing detailed events for user interactions, commands, errors, data fetching, and system performance.
- **Telegram Integration**: Direct webhook processing with bypassed PTB dependency, comprehensive admin command routing, dual endpoint deployment (/webhook, /webhook_v2), and real-time Telegram API integration.
- **Enhanced Logging System**: Dual-layer logging with RotatingFileHandler and RingBufferHandler for efficient log access and reliability.
- **Enhanced Multi-Source Diagnostics**: A complete diagnostic system for live module reloading, version tracking, real-time endpoint monitoring, and debugging.
- **Comprehensive Scan Command System**: Full scan diagnostic infrastructure for system health monitoring and validation.
- **Enhanced Tri-Source Token Discovery with Launchpad Priority**: Complete tri-source Solana token discovery with Birdeye dual-mode + DexScreener integration. **Birdeye HTTP** (`birdeye.py`): Enhanced `/defi/tokenlist` endpoint, 8-second polling, 5000-token deduplication, smart WebSocket-aware optimization (skips HTTP when WS connected), admin commands (`/scan_start`, `/scan_stop`, `/scan_status`, `/scan_mode`, `/scan_probe`). **Birdeye WebSocket Enhanced** (`birdeye_ws.py`): **Launchpad stream priority** with intelligent fallback, real-time token stream processing, multi-topic subscription system (`launchpad.created` → `token.created`), enhanced event handling with source tracking, global connection status tracking (`WS_CONNECTED`, `is_ws_connected()`), auto-configured URLs, dual authentication support, 8000-token deduplication memory, automatic reconnection with exponential backoff, enhanced alert logging with source-specific formatting (🚀 Launchpad vs ⚡ WS), comprehensive admin commands (`/ws_start`, `/ws_stop`, `/ws_status`, `/ws_restart`, `/ws_sub`, `/ws_mode`, `/ws_tap`). **Enhanced WebSocket Debug System**: Advanced debugging capabilities with 30-message rolling cache, rate-limited admin forwarding (6/minute max), synthetic event injection for pipeline testing, comprehensive debug command suite (`/ws_debug on/off/inject/cache/status`, `/ws_dump [n]`, `/ws_probe`), real-time admin chat notifications with JSON formatting, enterprise-grade monitoring and troubleshooting for WebSocket streams. **DexScreener Scanner** (`dexscreener_scanner.py`): Solana pairs monitoring with configurable intervals (10s minimum), 3-minute discovery window, 8000-token deduplication, liquidity and price tracking, enhanced admin commands (`/ds_start [seconds]`, `/ds_stop`, `/ds_status`). **Event Bus Bridge**: Automatic alert forwarding from all scanner sources to admin chat with formatted batch alerts. All scanners feature auto-start functionality, event publishing integration, comprehensive Telegram notifications, and admin-only access control. Enhanced log filtering with advanced argument parsing supports line count limits, level filtering, and content substring filtering. Updated August 11, 2025.

## External Dependencies
- **Telegram Bot API**: For all message handling and user interactions.
- **Solana Blockchain Integration**: Interacts with the Solana blockchain for live trading on Pump.fun.
- **Flask Web Server**: The application's web server for webhook callbacks and web interface.
- **Database System**: SQLAlchemy for database abstraction, defaulting to SQLite but supporting others via environment configuration.
- **Python HTTP Requests**: The `requests` library for all HTTP communication with external APIs.
- **OpenAI API**: For AI assistant functionalities.
- **Jupiter DEX**: For decentralized exchange operations on Solana.
- **PumpPortal Lightning Transaction API**: The core trading engine for verified token delivery on Pump.fun.