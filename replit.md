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
- **COMPLETED**: **ENHANCED WALLET RESET SYSTEM** - Implemented secure two-step wallet reset confirmation with `/wallet_reset` → `/wallet_reset_confirm` flow, 120-second timeout window, automatic cleanup of expired confirmations, in-memory state management per user, and proper error handling for expired/missing confirmations while maintaining admin-only protection. Enhanced with current address visibility, detailed fund movement warnings, old/new address confirmation display, and `/wallet_reset_cancel` cancellation support (August 14, 2025)
- **COMPLETED**: **ENHANCED QR DEPOSIT SYSTEM** - Upgraded `/wallet_deposit_qr` command with optional SOL amount parameter support, `/wallet_qr` shorthand alias, Solana URI amount specification, improved captions with amount display, and safety warnings for burner wallets. Features robust number parsing with comma support and intelligent decimal formatting (August 14, 2025)
- **COMPLETED**: **ENHANCED WALLET DIAGNOSTICS** - Upgraded `/wallet_selftest` with precise Base58 address validation, comprehensive diagnostic output, text normalization, and detailed failure reporting. Enhanced `/wallet_balance_usd` with multi-pattern SOL extraction (SOL:, ◎), robust fallback parsing, and support for comma-separated numbers (August 14, 2025)
- **COMPLETED**: **WALLET QR DEPOSIT SYSTEM** - Added `/wallet_deposit_qr` command generating shareable QR codes for wallet deposits using Solana URI format, integrated with telegram_media.py for seamless photo delivery. Features automatic address extraction, unique filename generation, and comprehensive error handling with admin-only protection (August 14, 2025)
- **COMPLETED**: **REAL-TIME SOL PRICE INTEGRATION** - Implemented live CoinGecko API integration in prices.py replacing placeholder $155.00 with real-time SOL pricing ($193.82). Features intelligent caching, multi-level fallback protection, and seamless integration with `/wallet_balance_usd` command for accurate USD conversions (August 14, 2025)
- **COMPLETED**: **ELEGANT BRIDGE PATTERN MESSAGING SYSTEM** - Implemented centralized `send_message()` bridge function in telegram_polling.py that redirects all legacy Telegram API calls to unified `send_telegram_safe()` system. Added bridge imports to alerts/telegram.py and polling_test.py for backward compatibility, achieving true single-point Telegram API control without converting hundreds of existing calls (August 13, 2025)
- **COMPLETED**: **COMPREHENSIVE TOKEN BALANCE SYSTEM** - Enhanced `/wallet_balance` command to show all SPL tokens in addition to SOL, with automatic token discovery, metadata parsing, and formatted display supporting up to 10 tokens per wallet with comprehensive error handling. Added token recognition for MORK (1M tokens), GEMINI (2.46M tokens), and CLIPPY (4,616 tokens) with correct mint address mappings for proper symbol display (August 13, 2025)
- **COMPLETED**: **CRITICAL WALLET RECOVERY** - Successfully recovered user wallet `GcWdU2s5wem8nuF5AfWC8A2LrdTswragQtmkeUhByxk` with funds by locating private key in clippy_sale_plan.py, converting Base64 format to wallet system seed format, and updating wallet storage for proper `/wallet_export` functionality (August 13, 2025)
- **COMPLETED**: **STREAMLINED CENTRALIZED MESSAGING** - Implemented ultra-clean centralized messaging pattern using direct `send_telegram_safe()` integration with single-line error logging, eliminating redundant methods and achieving true single-point Telegram API control. Updated with enhanced "detect → validate → send MDV2 → fallback to plain" flow for bulletproof message delivery (August 13, 2025)
- **COMPLETED**: **ENHANCED MARKDOWNV2 SYSTEM** - Replaced basic markdown detection with advanced telegram_safety.py featuring MarkdownV2 support, proper character escaping, balanced format checking, and intelligent fallback mechanisms for bulletproof message delivery (August 13, 2025)
- **COMPLETED**: **MISSING FETCH FUNCTION RESOLVED** - Added multi_source_fetch() function to data_fetcher.py enabling full functionality of /fetch and /fetch_now commands with multi-source token discovery, YAML filtering, risk scoring, and comprehensive error handling (August 13, 2025)
- **COMPLETED**: **ENTERPRISE MESSAGE SAFETY** - Integrated unified send_telegram_safe() function across all Telegram messaging with advanced pattern recognition, automatic retry logic, and multi-level fallback protection (August 13, 2025)
- **COMPLETED**: **CENTRALIZED MESSAGE SENDING** - Eliminated all direct Telegram API calls from app.py (send_admin_md, _send_chunk, _send_safe, _reply, _send_admin_debug, _on_new_token), ensuring only telegram_polling.py handles message sending for true single-point control (August 13, 2025)
- **COMPLETED**: **UNIFIED HANDLER ARCHITECTURE** - Implemented single-point update processing with enhanced idempotency using update_id:message_id:chat_id format, supporting both message and edited_message updates with guaranteed single send per update (August 13, 2025)
- **COMPLETED**: **IDEMPOTENCY DEDUPLICATION SYSTEM** - Added rolling memory system using deque and set to prevent duplicate message processing with TTL-based cleanup, ensuring each update_id:message_id combination is processed only once (August 13, 2025)
- **COMPLETED**: **WEBHOOK CONFLICT RESOLUTION** - Fixed duplicate processing and silent command failures by implementing automatic webhook deletion when polling starts, eliminating "double/silent" processing symptoms (August 13, 2025)
- **COMPLETED**: **HELP COMMAND FULLY OPERATIONAL** - All Telegram commands including `/help` and `/wallet_export` now responding correctly after webhook/polling conflict resolution (August 13, 2025)
- **COMPLETED**: **WALLET EXPORT SYSTEM** - Added `/wallet_export` command providing complete wallet details including base58 private key, Base64 seed, and address with security warnings and admin-only protection (August 13, 2025)
- **COMPLETED**: **COMPLETE 12-COMMAND WALLET SUITE** - All wallet commands fully operational - `/wallet`, `/wallet_new`, `/wallet_addr`, `/wallet_balance`, `/wallet_balance_usd`, `/wallet_link`, `/wallet_deposit_qr`, `/wallet_qr`, `/wallet_selftest`, `/wallet_reset`, `/wallet_reset_cancel`, `/wallet_fullcheck`, `/wallet_export` with comprehensive testing
- **COMPLETED**: **MAJOR BREAKTHROUGH** - Resolved critical Telegram webhook delivery issue by implementing production-ready polling mode integration (August 13, 2025)
- **COMPLETED**: Created unified command processing system with proper Telegram API integration and comprehensive command handling
- **COMPLETED**: All Telegram commands now fully operational (/help, /commands, /info, /test123, /ping, wallet commands) with professional Mork F.E.T.C.H branding
- **COMPLETED**: Enhanced wallet system one-shot patch with improved error handling, safe Telegram messaging, and comprehensive fallback protection (August 12, 2025)
- **COMPLETED**: Implemented chunked /help response system using _reply() function with automatic 3900-character splitting to prevent Telegram 500 errors
- **COMPLETED**: Added AUTO_START_SCANS environment variable functionality with conditional scanner startup control (defaults to false for safety)
- **COMPLETED**: Fixed LSP errors and duplicate function declarations, cleaned up orphaned code for better maintainer experience
- **COMPLETED**: Enhanced safe reply fallback system with comprehensive Markdown→plain text retry protection and robust error handling
- **COMPLETED**: Enhanced EventBus migration to new events.py with deduplication cache, thread-safe operations, and backward compatibility
- **COMPLETED**: Implemented wallets.py production-ready wallet system with PyNaCl ed25519 keypairs, secure base64 seed storage, and async Solana RPC balance fetching
- **COMPLETED**: Fixed critical webhook routing conflict - all wallet commands now fully operational in both single and multi-command scenarios
- **COMPLETED**: Integrated wallet system with comprehensive Telegram bot commands: /wallet_new, /wallet_addr, /wallet_balance, and legacy /wallet (all admin-restricted)
- **COMPLETED**: Added /bus_test command for wallet + event bus integration testing with synthetic token publishing
- **COMPLETED**: Patched app.py with event bus integration including imports for BUS, rules, and wallet modules
- **COMPLETED**: Implemented _normalize_token() helper function and _on_new_token() subscriber for NEW_TOKEN events with rules validation and Telegram notifications
- **COMPLETED**: Added NEW_TOKEN publishing to all scanners (Birdeye WS/HTTP, Solscan, DexScreener, Jupiter) with source-specific normalization
- **COMPLETED**: Integrated comprehensive admin command interface for rules management (/rules_show, /rules_reload, /rules_test) and wallet operations with proper error handling and Telegram formatting

**Core Architectural Decisions & Features:**
- **Unified Single-Process Architecture:** Gunicorn configured for single-worker to ensure webhook handlers and scanner threads share the same process and data, resolving process isolation issues.
- **Multi-Source Token Discovery:** Integrates Birdeye (HTTP & WebSocket), Jupiter, and Solscan Pro for comprehensive token discovery, enrichment, and scoring. Birdeye WebSocket includes launchpad stream priority, real-time processing, and automatic reconnection. Solscan Pro features auth header rotation, rate-limited discovery, and intelligent caching.
- **AI Assistant System:** Flask webhook integration supporting multiple AI models (e.g., GPT-4o, Claude-3.5-Sonnet) with intelligent fallback and persistent storage.
- **Enhanced Tri-Source Token Engine:** Comprehensive filtering and scoring architecture with real-time blockchain monitoring and advanced Solana RPC enrichment.
- **Live Monitoring Dashboard & Console:** Secure, token-gated interfaces for real-time event streaming via Server-Sent Events (SSE) and an ultra-lightweight console.
- **Enhanced Event Publishing System:** Advanced real-time event tracking with deduplication capabilities across all system components, featuring a thread-safe publish/subscribe architecture, configurable cache windows, and comprehensive event fingerprinting.
- **Telegram Integration:** Production-ready polling mode integration that bypasses webhook delivery issues, comprehensive admin command routing, unified command processing system, and reliable Telegram API integration with proper error handling and fallback protection.
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