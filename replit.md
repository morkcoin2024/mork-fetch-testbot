# Mork F.E.T.C.H Bot

## Overview
Mork F.E.T.C.H Bot, "The Degens' Best Friend," is a production-ready Telegram-based cryptocurrency trading bot for Solana blockchain tokens, specifically those on Pump.fun. Its purpose is to enable fast execution and control over trades, providing a user-friendly, automated trading solution for Solana degens. Key capabilities include secure wallet management, Jupiter DEX integration, comprehensive safety checks, and MORK holder access gates, enhancing trading efficiency and profitability. The business vision is to provide a user-friendly, automated trading solution for Solana degens, enhancing trading efficiency and profitability.

## User Preferences
Preferred communication style: Simple, everyday language.
Brand colors: Mork Coin branding with green primary color (#7cb342) and light green accent (#9ccc65) to match current brand guidelines.
Branding rules: "Mork F.E.T.C.H Bot" text should be dark green (#1a2e0a) on light green backgrounds, all other text should be white unless they are headline text. The bot is positioned as "The Degens' Best Friend" with playful dog-themed messaging around "fetching" profits and "sniffing" trades. F.E.T.C.H. = Fast Execution, Trade Control Handler. Uses casual, meme-friendly language appealing to crypto degenerates while maintaining professionalism.

## System Architecture
The application uses Flask with a robust single-poller architecture for Telegram integration, managing session states and database persistence with SQLAlchemy. A finite state machine handles multi-step user interactions. UI/UX aligns with Mork Coin branding, utilizing the specified color scheme and playful dog-themed messaging. The system supports Simulation, Manual Live Trading (`/snipe`), and Automated VIP Trading (`/fetch`) modes.

**Core Architectural Decisions & Features:**
- **Single-Poller Architecture:** Controls Telegram polling via an environment variable to prevent conflicts and ensure stable deployment. Implements an exclusive file-based locking system to prevent multiple Telegram poller instances.
- **Robust Message Delivery:** Features a 3-tier fallback system for Telegram messages with resilient timeout handling.
- **Automated Restart Mechanisms:** Ensures maximum uptime through auto-restart capabilities.
- **Multi-Source Token Discovery & Scoring:** Integrates various APIs for comprehensive token discovery and scoring.
- **AI Assistant System:** Flask webhook integration supporting multiple AI models with intelligent fallback.
- **Live Monitoring & Diagnostics:** Secure, token-gated interfaces for real-time event streaming via SSE, a lightweight console, and a complete diagnostic system.
- **Enhanced Event Publishing System:** Advanced real-time event tracking with deduplication using a thread-safe publish/subscribe architecture.
- **Enhanced Logging System:** Dual-layer logging with `RotatingFileHandler` and `RingBufferHandler`.
- **Simplified Scanner Control System:** Self-contained scanner module with JSON persistence for granular controls.
- **Trade Management System:** Self-contained `trade_store.py` module with JSON persistence for position tracking, including a mock trading engine for realistic simulations.
- **Autobuy & AutoSell Functionality:** Enhanced scanner state with autobuy configuration and a sophisticated automated selling engine (take-profit, stop-loss, trailing stop).
- **Watchlist Alert System:** Real-time price monitoring with configurable percent-change thresholds and a modular watch engine with per-chat/per-group isolation.
- **Paper Trade Ledger System:** Complete DRY-RUN trading ledger with position tracking and P&L management.
- **Alert Routing System:** Real-time alert forwarding to specified Telegram groups/channels with flood control and persistent configuration.
- **Snapshot/Restore System:** Backup management with point-in-time snapshots and dual-file persistence for configuration rollback.
- **Enhanced Wallet System:** Secure two-step wallet reset, QR deposit system, and comprehensive diagnostics.
- **Real-time SOL Price Integration:** Live CoinGecko API integration with intelligent caching.
- **Elegant Bridge Pattern Messaging System:** Centralized `send_message()` bridge function for unified Telegram API control.
- **Comprehensive Token Balance System:** Enhanced `/wallet_balance` command showing all SPL tokens.
- **Smart Unknown Command Handling:** Professional error messages distinguishing between commands and regular text.
- **Unified Handler Architecture:** Single-point update processing with enhanced idempotency and a rolling memory system.
- **Live Price Sources V2 System:** Multi-provider price discovery with hardened persistence supporting sim, dex, and birdeye sources, featuring intelligent fallback.
- **Unified Application Architecture:** Implemented unified `main.py` shim for consistent Flask app object.
- **Price Watch Alert Integration:** Automated price movement detection system that monitors `/price` command responses and triggers alerts.
- **Enhanced Help System with Alert Alias:** Comprehensive command discovery system featuring detailed and compact help panels, and a manual price snapshot alias.
- **Scanner Command Alias System:** Backward compatibility for legacy scanner commands with automatic redirection to modern `alerts_auto` equivalents.
- **Smart Fetch Command System:** Advanced `/fetchnow` command for intelligent token information retrieval with flexible input parsing and integration with per-chat watchlist.
- **Dual-Layer Message Deduplication System:** Enhanced `tg_send()` function with sophisticated duplicate message prevention using in-memory content-aware hashing and cross-process SQLite-based deduplication.
- **Comprehensive Price History Tracking System:** Lightweight JSONL-based price history storage with multi-window performance analysis and enhanced `/info` command.
- **Multi-Window API Analysis System:** Real-time percentage change tracking using Birdeye and DexScreener APIs with intelligent fallback.
- **Enhanced Parsing Guard System:** Comprehensive command parsing safety system preventing errors by standardizing variable usage.
- **Comprehensive Multi-Source Name Resolution:** Complete token name discovery system with user-specified implementation patterns, including overrides, caching, and heuristic extraction, ensuring consistent "TICKER\nLong Name" formatting.
- **Enhanced Ticker Support & /fetch Alias System:** Comprehensive ticker-to-mint resolution system enabling commands like `/price <TICKER|MINT>`, `/about <TICKER|MINT>`, and `/fetch <TICKER|MINT>` with intelligent argument parsing and quick-actions footer.

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