"""
Scanner Configuration Manager
Unified configuration system for all scanner components
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_path: str = "scanner_config.json"):
        self.config_path = Path(config_path)
        self._config = {}
        self._defaults = self._get_defaults()
        self.load_config()

    def _get_defaults(self) -> dict[str, Any]:
        """Default configuration values"""
        return {
            "scanner": {
                "enabled": True,
                "interval_sec": 20,
                "threshold": 75,
                "seen_mints": [],
                "watchlist": [],
            },
            "solscan": {"enabled": True, "interval_sec": 30, "limit": 20, "timeout_sec": 10},
            "birdeye": {
                "enabled": True,
                "websocket": {"stale_after_sec": 60, "min_backoff_sec": 5, "max_backoff_sec": 300},
            },
            "filters": {"score_threshold": 75, "min_liq_usd": 5000, "min_holders": 50},
        }

    def load_config(self) -> None:
        """Load configuration from file or create with defaults"""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    self._config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_path}")
            else:
                self._config = self._defaults.copy()
                self.save_config()
                logger.info(f"Created default configuration at {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            self._config = self._defaults.copy()

    def save_config(self) -> None:
        """Save current configuration to file"""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'scanner.interval_sec')"""
        keys = key_path.split(".")
        value = self._config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key_path: str, value: Any) -> None:
        """Set configuration value using dot notation"""
        keys = key_path.split(".")
        config = self._config

        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the value
        config[keys[-1]] = value
        logger.info(f"Updated config: {key_path} = {value}")

    def update_scanner_settings(self, settings: dict[str, Any]) -> None:
        """Update scanner settings from provided dictionary"""
        if "scanner" in settings:
            scanner_config = self._config.setdefault("scanner", {})
            scanner_config.update(settings["scanner"])
            logger.info("Updated scanner settings")

        self.save_config()

    def get_scanner_config(self) -> dict[str, Any]:
        """Get complete scanner configuration"""
        return self._config.get("scanner", {})

    def get_interval(self, scanner_name: str) -> int:
        """Get scan interval for specific scanner"""
        return self.get(f"{scanner_name}.interval_sec", 30)

    def get_threshold(self) -> int:
        """Get score threshold for filtering"""
        return self.get("scanner.threshold", 75)

    def is_enabled(self, scanner_name: str) -> bool:
        """Check if specific scanner is enabled"""
        return self.get(f"{scanner_name}.enabled", True)

    def add_to_watchlist(self, mint_address: str) -> None:
        """Add token to watchlist"""
        watchlist = self.get("scanner.watchlist", [])
        if mint_address not in watchlist:
            watchlist.append(mint_address)
            self.set("scanner.watchlist", watchlist)
            self.save_config()
            logger.info(f"Added {mint_address} to watchlist")

    def remove_from_watchlist(self, mint_address: str) -> None:
        """Remove token from watchlist"""
        watchlist = self.get("scanner.watchlist", [])
        if mint_address in watchlist:
            watchlist.remove(mint_address)
            self.set("scanner.watchlist", watchlist)
            self.save_config()
            logger.info(f"Removed {mint_address} from watchlist")

    def get_watchlist(self) -> list:
        """Get current watchlist"""
        return self.get("scanner.watchlist", [])

    def mark_seen(self, mint_address: str) -> None:
        """Mark token as seen for deduplication"""
        seen_mints = self.get("scanner.seen_mints", [])
        if mint_address not in seen_mints:
            seen_mints.append(mint_address)
            # Keep only last 1000 entries to prevent unbounded growth
            if len(seen_mints) > 1000:
                seen_mints = seen_mints[-1000:]
            self.set("scanner.seen_mints", seen_mints)

    def is_seen(self, mint_address: str) -> bool:
        """Check if token was already seen"""
        seen_mints = self.get("scanner.seen_mints", [])
        return mint_address in seen_mints

    def get_filter_config(self) -> dict[str, Any]:
        """Get filtering configuration"""
        return self.get("filters", {})


# Global configuration instance
config = ConfigManager()


def get_config() -> ConfigManager:
    """Get global configuration manager instance"""
    return config
