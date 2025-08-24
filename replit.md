# Mork F.E.T.C.H Bot

## Overview
Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades, providing a user-friendly, automated trading solution. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates, enhancing trading efficiency and profitability. The business vision is to provide a user-friendly, automated trading solution for Solana degens, enhancing trading efficiency and profitability.

## User Preferences
Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture
The application uses Flask with a robust single-poller architecture for Telegram integration, managing session states and database persistence with SQLAlchemy. A finite state machine handles multi-step user interactions. UI/UX aligns with Mork Coin branding, utilizing the specified color scheme and playful dog-themed messaging. The system supports Simulation, Manual Live Trading (`/snipe`), and Automated VIP Trading (`/fetch`) modes.

**Core Architectural Decisions & Features:**
- **Single-Poller Architecture:** Exclusive file-based locking prevents multiple Telegram poller instances.
- **Robust Message Delivery & Automated Restart:** Features a 3-tier fallback system for Telegram messages and ensures maximum uptime.
- **Token Discovery & Scoring:** Integrates various APIs for comprehensive token discovery and scoring.
- **AI Assistant System:** Flask webhook integration supporting multiple AI models with intelligent fallback.
- **Live Monitoring & Diagnostics:** Secure, token-gated interfaces for real-time event streaming, console, and diagnostic system.
- **Enhanced Event Publishing & Logging:** Advanced real-time event tracking with deduplication and dual-layer logging.
- **Simplified Scanner Control & Trade Management:** Self-contained modules with JSON persistence for granular controls and position tracking, including a mock trading engine.
- **Autobuy & AutoSell Functionality:** Enhanced scanner state with autobuy configuration and sophisticated automated selling (take-profit, stop-loss, trailing stop).
- **Watchlist Alert System:** Real-time price monitoring with configurable thresholds and per-chat/per-group isolation.
- **Paper Trade Ledger System:** Complete DRY-RUN trading ledger with position tracking and P&L management.
- **Alert Routing System:** Real-time alert forwarding with flood control and persistent configuration.
- **Snapshot/Restore System:** Backup management with point-in-time snapshots and dual-file persistence.
- **Enhanced Wallet System:** Secure two-step wallet reset, QR deposit, and comprehensive diagnostics.
- **Real-time SOL Price Integration:** Live CoinGecko API integration with intelligent caching.
- **Elegant Bridge Pattern Messaging System:** Centralized `send_message()` for unified Telegram API control.
- **Comprehensive Token Balance System:** Enhanced `/wallet_balance` showing all SPL tokens.
- **Smart Unknown Command Handling:** Professional error messages.
- **Unified Handler Architecture:** Single-point update processing with idempotency and rolling memory.
- **Live Price Sources V2 System:** Multi-provider price discovery with hardened persistence and intelligent fallback.
- **Unified Application Architecture:** Consistent Flask app object via `main.py` shim.
- **Price Watch Alert Integration:** Automated price movement detection and alerts.
- **Enhanced Help System with Alert Alias:** Comprehensive command discovery and manual price snapshot alias.
- **Scanner Command Alias System:** Backward compatibility for legacy scanner commands.
- **Smart Fetch Command System:** Advanced `/fetchnow` for intelligent token information retrieval with flexible input parsing.
- **Dual-Layer Message Deduplication System:** Sophisticated duplicate message prevention using in-memory hashing and cross-process SQLite-based deduplication.
- **Comprehensive Price History Tracking System:** Lightweight JSONL-based storage with multi-window performance analysis and enhanced `/info` command.
- **Multi-Window API Analysis System:** Real-time percentage change tracking using Birdeye and DexScreener APIs with intelligent fallback.
- **Enhanced Parsing Guard System:** Comprehensive command parsing safety.
- **Comprehensive Multi-Source Name Resolution:** Token name discovery with overrides, caching, and heuristic extraction.
- **Enhanced Ticker Support & /fetch Alias System:** Comprehensive ticker-to-mint resolution enabling commands like `/price <TICKER|MINT>`.
- **Dry-Run Trading Commands System:** Safe trading simulation commands `/buy` and `/sell` with comprehensive validation and clear dry-run messaging.
- **Singleton Poller Lock System:** Dedicated `poller_lock.py` module with exclusive file-based locking.
- **Enhanced Liquidity Analysis System (LIQ_V2):** Institutional-grade financial precision using `Decimal.quantize()` and comprehensive Birdeye API integration.
- **Market Capitalization & 24h Volume Command Systems:** Dedicated commands `/marketcap` and `/volume` reusing Birdeye API integration.
- **Enhanced Watchlist Display Variants:** Complete `/watchlist` command system with multiple display modes and sorting, featuring per-chat isolation.
- **Supply/FDV/Holders Analysis Helpers:** Comprehensive helper functions for advanced token metrics with robust field mapping.
- **Unified Token Overview Fetcher:** Standardized `_get_token_overview()` for consistent data sources.
- **Advanced Token Analysis Commands:** Suite of advanced token metrics including `/supply`, `/fdv`, and `/holders`.
- **Enhanced Data Access Utilities:** Comprehensive utility system with intelligent fallback chains and graceful error handling.
- **Enterprise-Grade Unified Watchlist System with Tolerant Data Processing:** Production-ready watchlist system with six display modes, canonical numeric getters, sophisticated sorting, and robust error handling.
- **Enterprise-Grade Watchlist Optimization System with Complete Timeout Protection:** Production-grade multi-layer performance optimization featuring comprehensive timeout protection, intelligent caching, and parallel processing. System includes strict timeout-protected HTTP helper functions with default (3.05s connect, 5s read) timeouts, enhanced httpx.Timeout configurations, and thread-based watchdog protection using `with_timeout()` function. Features TTL caching system with `@ttl_cache(60)` decorator for primitive values (`_cached_price_usd`, `_cached_supply_val`, etc.), short-circuiting unknown tokens with `_is_known_token()` validation, parallel watchlist builder using `build_watchlist_parallel()` with ThreadPoolExecutor (max 8 workers), and resilient sorting system using `sort_key_numeric_qmark_last()` for formatted values. Individual operations use 7-second watchdog timeouts (increased from 4s to reduce false positives on slow links). Cross-mode value reuse ensures FDV calculations leverage cached price and supply data. Critical enterprise-grade optimization ensures maximum production reliability with minimal API load.
- **Comprehensive Enterprise Test Suite:** Complete validation framework with `tests/test_watchlist.py` providing comprehensive testing of all 6 watchlist modes, sorting functionality, advanced row parsing with regex fallback, and enterprise optimization features. Test suite validates parallel processing, TTL caching, timeout protection, graceful degradation, and resilient sorting systems. Includes automated test runner `tests/run_tests.sh` and comprehensive documentation confirming production-grade reliability with consistent performance regardless of network conditions or data source availability.

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
- **CoinGecko API**