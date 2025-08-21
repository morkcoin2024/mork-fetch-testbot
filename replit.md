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
- **Enhanced Watch Engine V2 with Normalized Data Architecture:** Optimized real-time watchlist monitoring system with background price tracking and automated alert generation. Features persistent configuration via `watchlist.json` with robust data normalization supporting legacy string entries and modern dict formats. Enhanced helper functions with source tracking transparency, ultra-compact command implementations, and backward compatibility for existing data. Integrates with existing price sources (sim/dex/birdeye) showing provider information in all outputs. Includes 6-command suite: `/watch <mint>` (add to watchlist), `/unwatch <mint>` (remove from watchlist), `/watchlist` (show tracked tokens with price movements), `/watch_tick` (force immediate watchlist check with detailed metrics), `/watch_off <mint>` (optimized alias for `/unwatch <mint>`), plus admin control `/watch_on` (start watcher). **Normalized Data Features:** Robust `_normalize_watch_item()` function handles legacy string entries, dict formats with various key names (mint/address/token), and ensures stable schema with keys: mint, last, delta_pct, src. Smart `_watch_contains()` and `_load_watchlist()`/`_save_watchlist()` functions ensure backward compatibility while normalizing all data on read/write operations. **Full Route Integration Complete:** All helper functions successfully integrated into app.py with complete normalization system active. **Token Label Resolver Integration:** Enhanced watchlist display with `_token_label()` function providing human-readable "SYMBOL (So11…1112)" format using cached Birdeye API metadata (24h TTL) for improved user experience. 
- **Comprehensive Price History Tracking System:** Lightweight JSONL-based price history storage system with multi-window performance analysis (30m, 1h, 4h, 12h, 24h tracking) featuring directional arrows, professional three-line token identity formatting, and enhanced `/info` command with `/about` alias support.
- **Multi-Window API Analysis System:** Real-time percentage change tracking using Birdeye and DexScreener APIs with intelligent fallback chains. Features `get_token_changes()` function providing comprehensive multi-provider analysis, enhanced `/info` command with professional visual indicators (🟢▲ gains, 🔴▼ losses, ⚪︎ unavailable), and smart API-first history-fallback strategy for maximum data accuracy.
- **Enhanced Parsing Guard System:** Comprehensive command parsing safety system preventing UnboundLocalError issues by replacing all ad-hoc `parts[x]` usage with standardized `cmd`, `arg`, and `args` variables throughout the entire codebase, ensuring robust command processing.
- **Updated Help Documentation:** Refined command descriptions with clearer explanations for `/about` as token snapshot alias, `/alerts_auto_on` as continuous scanning enabler, and improved command categorization for better user experience.
**Deployment Date:** August 21, 2025 - fully operational with enhanced `/about` command featuring comprehensive multi-timeframe analysis with clean vertical layout, ALL CAPS primary ticker display, professional visual indicators (🟢▲🔴▼), provider-based (5m,1h,6h,24h) and recorder-based (30m,12h) timeframes in separate rows, intelligent error handling with proper `_reply()` format, and complete command discoverability integration with updated help text.

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