# Mork F.E.T.C.H Bot

## Overview
Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates. The business vision is to provide a user-friendly, automated trading solution for Solana degens, enhancing their trading efficiency and profitability.

## User Preferences
Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture
The application uses Flask with a polling-based architecture for Telegram integration (switched from webhook due to external domain 404 issues), managing session states and database persistence with SQLAlchemy. A finite state machine handles multi-step user interactions. UI/UX aligns with Mork Coin branding. The system supports Simulation, Manual Live Trading (`/snipe`), and Automated VIP Trading (`/fetch`) modes.

**Core Architectural Decisions & Features:**
- **Unified Single-Process Architecture:** Gunicorn configured for single-worker to ensure webhook handlers and scanner threads share the same process and data.
- **Multi-Source Token Discovery:** Integrates Birdeye (HTTP & WebSocket), Jupiter, and Solscan Pro for comprehensive token discovery, enrichment, and scoring, including real-time processing and automatic reconnection.
- **AI Assistant System:** Flask webhook integration supporting multiple AI models (e.g., GPT-4o, Claude-3.5-Sonnet) with intelligent fallback and persistent storage.
- **Enhanced Tri-Source Token Engine:** Comprehensive filtering and scoring architecture with real-time blockchain monitoring and advanced Solana RPC enrichment.
- **Live Monitoring Dashboard & Console:** Secure, token-gated interfaces for real-time event streaming via Server-Sent Events (SSE) and an ultra-lightweight console.
- **Enhanced Event Publishing System:** Advanced real-time event tracking with deduplication capabilities across all system components, featuring a thread-safe publish/subscribe architecture and comprehensive event fingerprinting.
- **Telegram Integration:** Production-ready polling mode integration (active), comprehensive admin command routing, unified command processing system, and reliable Telegram API integration with proper error handling and fallback protection. Includes dedicated `telegram_polling.py` service for reliable AutoSell command processing.
- **Enhanced Logging System:** Dual-layer logging with `RotatingFileHandler` and `RingBufferHandler`.
- **Enhanced Multi-Source Diagnostics:** Complete diagnostic system for live module reloading, version tracking, real-time endpoint monitoring, and debugging.
- **Production Readiness:** Robust system with reliable thread-safe data, enterprise-grade timestamp precision, and automatic recovery capabilities for WebSocket connections.
- **Multiple Command Processing:** Webhook handles multiple Telegram commands in a single message with sequential processing and combined responses.
- **Simplified Scanner Control System:** Self-contained scanner module with direct JSON persistence (`scanner_state.json`) eliminating config_manager.py dependency. Enhanced granular controls via Telegram commands: `/scanner_on`/`/scanner_off` toggles, `/threshold <score>` dynamic adjustment, `/watch`/`/unwatch`/`/watchlist` management, `/config_show`/`/config_update` real-time updates. Thread-safe operations with RLock protection and intelligent alert integration.
- **Mock Data Testing System:** Comprehensive testing infrastructure with `token_fetcher.py` for realistic token generation and `flip_checklist.py` for advanced scoring (75-110 range). Complete scanner system integration with background thread auto-start and Telegram alert system. Added `/fetch_now` command for instant token scanning and scoring display.
- **Trade Management System:** Self-contained `trade_store.py` module with JSON persistence (`trades_state.json`) for future trading integration. Features position tracking, fill recording, pending action management with TTL, safety caps, slippage configuration, and live trading toggle (disabled by default).
- **Mock Trading Engine:** `trade_engine.py` module providing realistic buy/sell operations with slippage simulation, preview/execution functions, and integration with trade_store for position tracking. Includes random fill variations for realistic mock trading experience.
- **Complete Mock Trading System:** Comprehensive trading functionality with preview/confirmation flow and position tracking capabilities. Features buy/sell operations, position management, PnL tracking, and integrated safety systems with live trading disabled by default.
- **Autobuy Functionality:** Enhanced scanner state with autobuy configuration for automated token purchases based on scanner alerts. Features per-token configuration, enable/disable controls, safety caps integration, and automatic execution when qualifying tokens are discovered.
- **AutoSell System:** Fully operational sophisticated automated selling engine with take-profit, stop-loss, and trailing stop functionality. Features per-token rule configuration, position monitoring, real-time price tracking, and automatic execution with safety controls. Includes comprehensive 7-command Telegram suite (/autosell_on, /autosell_off, /autosell_status, /autosell_interval, /autosell_set, /autosell_list, /autosell_remove) for complete rule management and real-time control.
- **Enhanced Wallet System:** Secure two-step wallet reset, QR deposit system with optional SOL amount, comprehensive diagnostics, and multi-pattern SOL extraction. Includes full 12-command wallet suite (`/wallet`, `/wallet_new`, `/wallet_addr`, `/wallet_balance`, `/wallet_balance_usd`, `/wallet_link`, `/wallet_deposit_qr`, `/wallet_qr`, `/wallet_selftest`, `/wallet_reset`, `/wallet_reset_cancel`, `/wallet_fullcheck`, `/wallet_export`).
- **Real-time SOL Price Integration:** Live CoinGecko API integration with intelligent caching and multi-level fallback protection.
- **Elegant Bridge Pattern Messaging System:** Centralized `send_message()` bridge function for unified Telegram API control.
- **Comprehensive Token Balance System:** Enhanced `/wallet_balance` command showing all SPL tokens with automatic discovery and metadata parsing.
- **Streamlined Centralized Messaging:** Ultra-clean centralized messaging pattern with enhanced MarkdownV2 system and bulletproof message delivery.
- **Simplified Alert System:** Clean alerts/telegram.py module with direct imports from app.py (BOT_TOKEN, ADMIN_CHAT_ID) using telegram_safety.send_telegram_safe for reliable message delivery with fallback protection.
- **Enhanced Command Processing:** Robust `_parse_cmd` utility function supporting @BotName suffixes, case-insensitive processing, and clean argument separation for improved group chat compatibility.
- **Dual-Pattern Command Matching:** AutoSell commands use both `cmd` variable and legacy `text` parsing for bulletproof backward compatibility.
- **Smart Unknown Command Handling:** Professional error messages with text sanitization to prevent formatting issues, distinguishing between commands and regular text.
- **Single-Send Guarantee Update Handling:** Enhanced `handle_update` function with explicit `handled` flags, preventing duplicate responses and ensuring clean message flow.
- **Unified Handler Architecture:** Single-point update processing with enhanced idempotency for message and edited_message updates.
- **Idempotency Deduplication System:** Rolling memory system to prevent duplicate message processing.
- **Webhook Conflict Resolution:** Automatic webhook deletion when polling starts.
- **Enhanced Command Processing System:** Advanced `_parse_cmd()` function with regex-based parsing, zero-width character normalization (ZWSP, ZWNJ, ZWJ, WORD JOINER, BOM), and robust @BotName handling, unified `process_telegram_command()` function with clean response architecture, and integrated AutoSell command suite with comprehensive error handling and admin-only access controls. Updated with streamlined parsing implementation featuring condensed zero-width character handling and improved fallback logic. Includes temporary AutoSell safety override mechanism for maintenance periods.
- **Standardized Command Parsing Pattern:** Enforced consistent command processing throughout webhook handler using mandatory pattern: `msg = update.get("message") or {}; user = msg.get("from") or {}; text = msg.get("text") or ""; cmd, args = _parse_cmd(text)` - ensuring unified parsing, enhanced debugging capabilities via `/debug_cmd`, and bulletproof command introspection across all message processing paths.
- **Smart Unknown Command Handling:** Professional error messages with text sanitization to prevent formatting issues, distinguishing between commands and regular text using `clean = (text or "").replace("\n", " ")` pattern for clean Telegram delivery.
- **Robust Result Handling Pattern:** Enhanced webhook integration with bulletproof result processing supporting dict/string/error responses, intelligent output detection, and safe Telegram delivery using `telegram_safety.send_telegram_safe` for maximum reliability.

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