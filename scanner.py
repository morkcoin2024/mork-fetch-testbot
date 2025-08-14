# scanner.py - Unified scanner module integrating with config_manager
import threading, time, json, os
from typing import List, Tuple
from config_manager import get_config

_LOCK = threading.RLock()
_thread = None
_stop = False

def enable():
    """Enable scanner and start background thread"""
    global _thread, _stop
    with _LOCK:
        config = get_config()
        config.set("scanner.enabled", True)
        config.save_config()
        
        if _thread is None or not _thread.is_alive():
            _stop = False
            _thread = threading.Thread(target=_loop, daemon=True)
            _thread.start()

def disable():
    """Disable scanner and stop background thread"""
    global _stop
    with _LOCK:
        config = get_config()
        config.set("scanner.enabled", False)
        config.save_config()
        _stop = True

def is_enabled() -> bool:
    """Check if scanner is enabled"""
    config = get_config()
    return config.get("scanner.enabled", True)

def set_threshold(v: int):
    """Set score threshold for filtering"""
    config = get_config()
    config.set("scanner.threshold", int(v))
    config.save_config()

def get_threshold() -> int:
    """Get current threshold value"""
    config = get_config()
    return config.get("scanner.threshold", 75)

def add_watch(mint: str) -> bool:
    """Add token to watchlist"""
    config = get_config()
    watchlist = config.get_watchlist()
    if mint in watchlist:
        return False
    config.add_to_watchlist(mint)
    return True

def remove_watch(mint: str) -> bool:
    """Remove token from watchlist"""
    config = get_config()
    watchlist = config.get_watchlist()
    if mint not in watchlist:
        return False
    config.remove_from_watchlist(mint)
    return True

def get_watchlist() -> List[str]:
    """Get current watchlist"""
    config = get_config()
    return config.get_watchlist()

def mark_seen(mint: str):
    """Mark token as seen for deduplication"""
    config = get_config()
    config.mark_seen(mint)

def is_seen(mint: str) -> bool:
    """Check if token was already seen"""
    config = get_config()
    return config.is_seen(mint)

def get_status() -> dict:
    """Get scanner status information"""
    config = get_config()
    global _thread
    
    return {
        "enabled": config.get("scanner.enabled", True),
        "running": _thread is not None and _thread.is_alive() and not _stop,
        "interval_sec": config.get("scanner.interval_sec", 20),
        "threshold": config.get("scanner.threshold", 75),
        "watchlist_size": len(config.get_watchlist()),
        "thread_alive": _thread is not None and _thread.is_alive()
    }

# One-shot scan used by /fetch_now
def scan_now(n: int = 15) -> List[Tuple[dict, int, str]]:
    """Perform immediate scan and return top results"""
    try:
        # Import scanner dependencies
        import token_fetcher
        import flip_checklist
        
        # Get recent tokens
        tokens = token_fetcher.recent(n)
        if not tokens:
            return []
        
        # Score tokens
        scored_tokens = []
        for token in tokens:
            score, verdict, details = flip_checklist.score(token)
            scored_tokens.append((token, score, verdict))
        
        # Sort by score descending
        scored_tokens.sort(key=lambda x: x[1], reverse=True)
        return scored_tokens
        
    except Exception as e:
        print(f"[scanner] scan_now error: {e}")
        return []

def _loop():
    """Main scanner loop running in background thread"""
    print("[scanner] Background scanning loop started")
    
    while not _stop:
        config = get_config()
        
        # Get current configuration
        enabled = config.get("scanner.enabled", True)
        interval = config.get("scanner.interval_sec", 20)
        threshold = config.get("scanner.threshold", 75)
        watchlist = set(config.get_watchlist())
        
        if enabled:
            try:
                # Import dependencies
                import token_fetcher
                import flip_checklist
                
                # Get recent tokens
                tokens = token_fetcher.recent(20)
                
                # Include watchlist tokens (force-fetch)
                for mint in watchlist:
                    if mint:
                        watchlist_token = token_fetcher.lookup(mint)
                        if watchlist_token:
                            tokens.append(watchlist_token)
                
                # Score and filter tokens
                new_tokens = []
                for token in tokens:
                    mint = token.get("mint")
                    if not mint:
                        continue
                        
                    # Skip if already seen (unless on watchlist)
                    if is_seen(mint) and mint not in watchlist:
                        continue
                    
                    # Score the token
                    score, verdict, details = flip_checklist.score(token)
                    
                    # Check if meets threshold or is on watchlist
                    if score >= threshold or mint in watchlist:
                        new_tokens.append((token, score, verdict, details))
                        mark_seen(mint)
                
                # Send alerts for qualifying tokens
                if new_tokens:
                    # Sort by score and take top 5
                    new_tokens.sort(key=lambda x: x[1], reverse=True)
                    _send_alerts(new_tokens[:5])
                    
            except Exception as e:
                print(f"[scanner] loop error: {e}")
        
        # Sleep for configured interval (minimum 5 seconds)
        time.sleep(max(5, interval))

def _send_alerts(tokens: List[Tuple[dict, int, str, str]]):
    """Send Telegram alerts for qualifying tokens"""
    try:
        from telegram_polling import send_telegram_safe
        
        config = get_config()
        admin_id = os.getenv("ASSISTANT_ADMIN_TELEGRAM_ID")
        
        if not admin_id:
            print("[scanner] No admin ID configured for alerts")
            return
            
        for token, score, verdict, details in tokens:
            symbol = token.get("symbol", "Unknown")
            mint = token.get("mint", "")
            price = token.get("usd_price", token.get("price", "?"))
            mcap = token.get("market_cap", token.get("fdv", "?"))
            age = token.get("age", token.get("age_seconds", "?"))
            holders = token.get("holders", token.get("holder_count", "?"))
            
            # Format message with enhanced details
            msg = (
                f"🚨 **Scanner Alert**\n"
                f"**{symbol}** ({verdict})\n"
                f"Score: **{score}** (threshold: {config.get('scanner.threshold', 75)})\n\n"
                f"💰 Price: ${price}\n"
                f"📊 Market Cap: ${mcap:,} \n"
                f"👥 Holders: {holders}\n"
                f"⏰ Age: {age}s\n\n"
                f"📋 Details: {details}\n\n"
                f"🔗 `{mint}`"
            )
            
            # Send alert
            success, status_code, response = send_telegram_safe(admin_id, msg)
            if success:
                print(f"[scanner] Alert sent for {symbol} (score: {score})")
            else:
                print(f"[scanner] Alert send failed for {symbol}: {status_code}")
                
    except Exception as e:
        print(f"[scanner] Alert error: {e}")

# Auto-start scanner if enabled
def _auto_start():
    """Automatically start scanner if enabled in config"""
    try:
        config = get_config()
        if config.get("scanner.enabled", False):
            enable()
            print("[scanner] Auto-started from configuration")
    except Exception as e:
        print(f"[scanner] Auto-start error: {e}")

# Initialize on import
_auto_start()