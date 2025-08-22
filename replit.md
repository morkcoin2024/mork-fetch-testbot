# Mork F.E.T.C.H Bot

## Overview
Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades, providing a user-friendly, automated trading solution for Solana degens. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates, enhancing trading efficiency and profitability.

## User Preferences
Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture
The application uses Flask with a robust single-poller architecture for Telegram integration, managing session states and database persistence with SQLAlchemy. A finite state machine handles multi-step user interactions. UI/UX aligns with Mork Coin branding. The system supports Simulation, Manual Live Trading (`/snipe`), and Automated VIP Trading (`/fetch`) modes.

**Core Architectural Decisions & Features:**
- **Single-Poller Architecture:** Uses a `POLLING_ENABLED` environment variable to control Telegram polling, ensuring no 409 conflicts in deployment.
- **Robust Message Delivery:** Implements a 3-tier fallback system for Telegram message delivery with resilient timeout handling.
- **Automated Restart Mechanisms:** Includes auto-restart mechanisms for maximum uptime.
- **Multi-Source Token Discovery & Scoring:** Integrates various APIs for comprehensive token discovery and scoring.
- **AI Assistant System:** Flask webhook integration supporting multiple AI models with intelligent fallback.
- **Live Monitoring & Diagnostics:** Secure, token-gated interfaces for real-time event streaming via SSE, a lightweight console, and a complete diagnostic system.
- **Enhanced Event Publishing System:** Advanced real-time event tracking with deduplication using a thread-safe publish/subscribe architecture.
- **Telegram Integration:** Production-ready polling mode with comprehensive admin command routing and unified command processing.
- **Enhanced Logging System:** Dual-layer logging with `RotatingFileHandler` and `RingBufferHandler`.
- **Simplified Scanner Control System:** Self-contained scanner module with JSON persistence, enabling granular controls via Telegram commands.
- **Mock Data Testing System:** Comprehensive testing infrastructure for realistic token generation and scoring.
- **Trade Management System:** Self-contained `trade_store.py` module with JSON persistence for position tracking.
- **Mock Trading Engine:** Provides realistic buy/sell operations with slippage simulation.
- **Complete Mock Trading System:** Comprehensive trading functionality with preview/confirmation flow, position tracking, and PnL tracking.
- **Autobuy Functionality:** Enhanced scanner state with autobuy configuration for automated token purchases.
- **AutoSell System:** Sophisticated automated selling engine with take-profit, stop-loss, and trailing stop functionality, integrated with Dexscreener API.
- **Watchlist Alert System:** Real-time price monitoring with configurable percent-change thresholds for alerts.
- **Paper Trade Ledger System:** Complete DRY-RUN trading ledger with position tracking and P&L management.
- **Alert Routing System:** Real-time alert forwarding to specified Telegram groups/channels with flood control and persistent configuration.
- **Snapshot/Restore System:** Backup management with point-in-time snapshots and dual-file persistence for configuration rollback.
- **Enhanced Wallet System:** Secure two-step wallet reset, QR deposit system, and comprehensive diagnostics.
- **Real-time SOL Price Integration:** Live CoinGecko API integration with intelligent caching.
- **Elegant Bridge Pattern Messaging System:** Centralized `send_message()` bridge function for unified Telegram API control.
- **Comprehensive Token Balance System:** Enhanced `/wallet_balance` command showing all SPL tokens.
- **Streamlined Centralized Messaging:** Ultra-clean centralized messaging pattern with enhanced MarkdownV2.
- **Smart Unknown Command Handling:** Professional error messages distinguishing between commands and regular text.
- **Unified Handler Architecture:** Single-point update processing with enhanced idempotency and a rolling memory system.
- **Webhook Conflict Resolution:** Automatic webhook deletion when polling starts.
- **Live Price Sources V2 System:** Multi-provider price discovery with hardened persistence supporting sim, dex, and birdeye sources, featuring intelligent fallback.
- **Unified Application Architecture:** Implemented unified `main.py` shim for consistent Flask app object.
- **Price Watch Alert Integration:** Automated price movement detection system that monitors `/price` command responses and triggers alerts.
- **Enhanced Watch Engine V4 with Modular Architecture:** Advanced real-time watchlist monitoring system with complete per-chat/per-group isolation using streamlined `_wl_bucket()` helper function for efficient state management. Features robust data persistence with automatic migration from legacy global watchlist to per-chat structure using `watchlist_by_chat` architecture in `scanner_state.json`. **Modular Command Architecture:** Dedicated handler functions `_cmd_watch()`, `_cmd_watchlist()`, `_cmd_unwatch()`, and `_cmd_watch_clear()` provide clean separation of concerns and improved maintainability. **Complete Command Suite:** `/watch <mint1> <mint2>...` (bulk add to watchlist), `/unwatch <mint1> <mint2>...` (bulk remove from watchlist), `/watchlist` (show per-chat tracked tokens), `/watch_clear` (clear entire chat watchlist). **Smart Data Management:** Simplified bucket system with automatic deduplication, legacy migration, and per-chat isolation ensuring each group maintains independent watchlists. **Enhanced Display:** Professional formatting with numbered lists, token name resolution showing tickers, and abbreviated mint addresses for clean presentation. **Robust Error Handling:** Comprehensive validation with graceful fallbacks and clear user feedback for all operations.
- **Enhanced Help System with Alert Alias:** Comprehensive command discovery system featuring `/help` (detailed help panel with categorized commands), `/commands` (compact command list), and `/alert` (manual price snapshot alias with custom "Price Alert" title). Enhanced `render_price_card()` function supports custom titles while maintaining backward compatibility. Professional help formatting with organized categories (General, Names, Watchlist, Auto alerts) providing clear usage guidance for all bot functionality.
- **Scanner Command Alias System:** Backward compatibility layer for legacy scanner commands with automatic redirection to modern alerts_auto equivalents. Features `/scanner_on` → `/alerts_auto_on`, `/scanner_off` → `/alerts_auto_off`, `/scanner_status` → `/alerts_auto_status`, and `/scanner_interval` → `/alerts_auto_on` with parameter forwarding. Implemented with robust error handling and transparent command rewriting ensuring seamless user experience during migration.
- **Smart Fetch Command System:** Advanced `/fetchnow` command providing intelligent token information retrieval with flexible input parsing. Features `/fetchnow` (fetch 1 from watchlist), `/fetchnow <n>` (fetch n from watchlist), and `/fetchnow <mint1> <mint2>...` (fetch specific tokens). Integrates with per-chat watchlist system, uses Birdeye price data, and renders professional token information cards with name resolution and price display.
- **Dual-Layer Message Deduplication System:** Enhanced `tg_send()` function with sophisticated duplicate message prevention using two-tier approach: (1) fast in-memory content-aware hashing with SHA1-based fingerprinting and automatic garbage collection, (2) cross-process SQLite-based deduplication for multi-worker environments. Features configurable TTL (3s default), force bypass capability, and comprehensive logging with layer identification for debugging and monitoring.
- **Comprehensive Price History Tracking System:** Lightweight JSONL-based price history storage system with multi-window performance analysis (30m, 1h, 4h, 12h, 24h tracking) featuring directional arrows, professional three-line token identity formatting, and enhanced `/info` command with `/about` alias support.
- **Multi-Window API Analysis System:** Real-time percentage change tracking using Birdeye and DexScreener APIs with intelligent fallback chains. Features `get_token_changes()` function providing comprehensive multi-provider analysis, enhanced `/info` command with professional visual indicators (🟢▲ gains, 🔴▼ losses, ⚪︎ unavailable), and smart API-first history-fallback strategy for maximum data accuracy.
- **Enhanced Parsing Guard System:** Comprehensive command parsing safety system preventing UnboundLocalError issues by replacing all ad-hoc `parts[x]` usage with standardized `cmd`, `arg`, and `args` variables throughout the entire codebase, ensuring robust command processing.
- **Updated Help Documentation:** Refined command descriptions with clearer explanations for `/about` as token snapshot alias, `/alerts_auto_on` as continuous scanning enabler, and improved command categorization for better user experience.
**Deployment Date:** August 21, 2025 - fully operational with enhanced `/about` command featuring comprehensive multi-timeframe analysis with clean list-based layout optimized for proportional fonts, advanced name parsing with `split_primary_secondary()` handling multiple formats, professional visual indicators (🟢▲🔴▼), provider-based (5m,1h,6h,24h) and recorder-based (30m) timeframes, intelligent error handling, and complete command discoverability. **Updated Layout:** Implemented aligned /about layout with figure-space padding using FIGURE_SPACE constant for consistent emoji arrow alignment across timeframes, improved visual presentation without code blocks, and hidden 12h timeframe for cleaner display. **Comprehensive Multi-Source Name Resolution V3 - FINAL:** Complete token name discovery system with user-specified implementation pattern featuring `_display_name_for()` function providing exact "TICKER\nLong Name" layout with 3-tier precedence: (1) explicit override (token_name_overrides.json), (2) cached/resolved (token_names.json via resolve_token_name), (3) short mint (abcd..wxyz). Enhanced `/about` command structure with proper error handling returning {"status": "ok"} to prevent duplicates. Features normalized symbol cleaning, ticker-first prioritization, comprehensive caching with 24h TTL, manual override capabilities with `/name_set <mint> <TICKER>|<Long Name>`, `/name_show <mint>`, and `/name_clear <mint>` commands, plus heuristic primary extraction from secondary names using intelligent stopword filtering. System automatically handles special cases (SOL pseudo-mint), provides robust error handling, and ensures consistent "TICKER\nLong Name" formatting. **Advanced Features:** Override system takes top priority, heuristic extraction derives tickers from names like "Light Protocol Token"→"LIGHT", comprehensive command suite for name management, and fallback to Jupiter catalog with bulk refresh capability. **Production Performance:** Successfully tested with SOL→"SOL\nSolana", USDC→"USDC\nUSD Coin", override functionality, and heuristic extraction covering both built-in handling and API-driven resolution with Jupiter catalog containing 424,295 tokens. **Live Telegram Verification:** PENGU displaying as "PENGU\nPudgy Penguins" via override system, LIGHT showing "LIGHT" via heuristic extraction, complete integration with live Telegram API confirmed operational. **Enhanced Ticker Support & /fetch Alias System - August 22, 2025:** Comprehensive ticker-to-mint resolution system enabling `/price <TICKER|MINT>`, `/about <TICKER|MINT>`, and `/fetch <TICKER|MINT>` commands with intelligent argument parsing. Features Base58 mint detection (32-44 characters), case-insensitive ticker lookup through name overrides system, and hardcoded fallback table (SOL→So1111...). Smart resolution logic via `_resolve_arg_to_mint()` function automatically determines input type, with `/fetch` command serving as identical alias to `/about`. Enhanced user experience through quick-actions footer showing "Actions: /price <MINT> • /watch <MINT> • /fetch <MINT>" for immediate workflow acceleration. Error handling returns "❌ Invalid mint or unknown ticker" for unknown symbols with clear usage guidance.

## External Dependencies
- **Telegram Bot API**
- **Solana Blockchain**
- **Flask Web Server**
- **SQLAlchemy**
- **Python HTTP Requests** (`requests` library)
- **OpenAI API**
- **Jupiter DEX**
- **PumpPortal Lightning Transaction API**
- **Birdeye API/WebSocket**
- **token.jup.ag API**
- **Solscan API**
- **DexScreener API**