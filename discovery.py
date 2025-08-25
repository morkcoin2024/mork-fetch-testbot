"""
Token Discovery System for Mork F.E.T.C.H Bot
Discovers new Pump.fun tokens and validates they are bonded & routable
"""

import logging
import time

import requests

from jupiter_engine import jupiter_engine

logger = logging.getLogger(__name__)


class TokenDiscovery:
    """Discovers and validates new Pump.fun tokens"""

    def __init__(self):
        self.pumpfun_api = "https://frontend-api.pump.fun"
        self.min_market_cap = 10000  # $10k minimum
        self.max_market_cap = 100000  # $100k maximum
        self.min_age_hours = 0.5  # At least 30 minutes old

    def scan_new_tokens(self, limit: int = 50) -> list[dict]:
        """Scan Pump.fun for new tokens meeting criteria"""
        try:
            # Try multiple API endpoints
            endpoints = [
                f"{self.pumpfun_api}/coins?sort=created_timestamp&order=DESC&limit={limit}",
                f"{self.pumpfun_api}/coins?sort=market_cap&order=DESC&limit={limit}",
            ]

            all_tokens = []
            for endpoint in endpoints:
                try:
                    response = requests.get(endpoint, timeout=10)
                    if response.status_code == 200:
                        tokens = response.json()
                        all_tokens.extend(tokens)
                        logger.info(f"Retrieved {len(tokens)} tokens from API")
                        break
                except Exception as e:
                    logger.warning(f"API endpoint failed: {e}")
                    continue

            return self._filter_suitable_tokens(all_tokens)

        except Exception as e:
            logger.error(f"Token scan failed: {e}")
            return []

    def _filter_suitable_tokens(self, tokens: list[dict]) -> list[dict]:
        """Filter tokens based on safety and trading criteria"""
        suitable = []
        current_time = time.time()

        for token in tokens:
            try:
                mint = token.get("mint", "")
                symbol = token.get("symbol", "UNKNOWN")
                market_cap = token.get("usd_market_cap", 0)
                created = token.get("created_timestamp", 0)

                # Basic validation
                if not mint or not symbol:
                    continue

                # Market cap filter
                if not (self.min_market_cap <= market_cap <= self.max_market_cap):
                    continue

                # Age filter
                if created > 0:
                    age_hours = (current_time - created) / 3600
                    if age_hours < self.min_age_hours:
                        continue
                else:
                    age_hours = 999  # Unknown age

                # Symbol quality filter
                if len(symbol) > 10 or len(symbol) < 1:
                    continue

                suitable.append(
                    {
                        "mint": mint,
                        "symbol": symbol,
                        "market_cap": market_cap,
                        "age_hours": age_hours,
                        "created": created,
                    }
                )

            except Exception as e:
                logger.debug(f"Token filter error: {e}")
                continue

        # Sort by market cap descending
        suitable.sort(key=lambda x: x["market_cap"], reverse=True)
        return suitable[:20]  # Return top 20

    def validate_token_for_trading(
        self, mint: str, test_amount: float = 0.001
    ) -> tuple[bool, str, dict]:
        """Comprehensive validation that token is ready for trading"""

        try:
            # Check if token is bonded and routable
            is_routable, route_msg = jupiter_engine.check_token_routable(mint, test_amount)

            if not is_routable:
                return False, f"Not routable: {route_msg}", {}

            # Extract expected tokens from route message
            try:
                if "tokens expected" in route_msg:
                    expected_str = route_msg.split(" tokens expected")[0].split(" - ")[-1]
                    expected_tokens = int(expected_str.replace(",", ""))
                else:
                    expected_tokens = 0
            except:
                expected_tokens = 0

            validation_data = {
                "mint": mint,
                "routable": True,
                "expected_tokens_per_sol": (
                    expected_tokens / test_amount if expected_tokens > 0 else 0
                ),
                "liquidity_check": "passed",
                "validation_time": time.time(),
            }

            return True, f"Ready for trading: {route_msg}", validation_data

        except Exception as e:
            return False, f"Validation failed: {e}", {}

    def find_tradeable_token(self) -> dict | None:
        """Find one good token ready for immediate trading"""

        logger.info("Scanning for tradeable tokens...")
        tokens = self.scan_new_tokens(50)

        if not tokens:
            logger.warning("No tokens found from scan")
            return None

        logger.info(f"Evaluating {len(tokens)} candidate tokens...")

        for token in tokens:
            mint = token["mint"]
            symbol = token["symbol"]

            # Validate for trading
            is_valid, msg, validation_data = self.validate_token_for_trading(mint)

            if is_valid:
                logger.info(f"Found tradeable token: {symbol} ({mint[:8]}...)")
                token.update(validation_data)
                return token
            else:
                logger.debug(f"Token {symbol} failed validation: {msg}")

        logger.warning("No tradeable tokens found in current scan")
        return None

    def get_token_info(self, mint: str) -> dict | None:
        """Get detailed information about a specific token"""
        try:
            # Try to get token info from Pump.fun API
            response = requests.get(f"{self.pumpfun_api}/coins/{mint}", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Token info not found for {mint}")
                return None
        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return None


# Global instance
discovery = TokenDiscovery()
