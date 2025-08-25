"""
Advanced Token Filter and Scoring Engine for Mork Fetch Bot
Implements rules-based filtering and scoring for Solana/Pump.fun tokens
"""

import logging
from datetime import datetime
from typing import Any

from rules_loader import Rules

logger = logging.getLogger(__name__)


class TokenFilter:
    """Advanced token filtering and scoring engine"""

    def __init__(self, rules_path: str = "rules.yaml"):
        self.rules = Rules(rules_path)
        self.current_profile = None

    def reload_rules(self) -> bool:
        """Reload rules from configuration file"""
        return self.rules.reload()

    def set_profile(self, profile_name: str) -> bool:
        """Set active filtering profile"""
        if self.rules.set_profile(profile_name):
            self.current_profile = profile_name
            logger.info(f"Switched to profile: {profile_name}")
            return True
        logger.warning(f"Profile not found: {profile_name}")
        return False

    def get_current_profile(self) -> str:
        """Get current active profile name"""
        return self.current_profile or self.rules.meta.get("default_profile", "conservative")

    def filter_and_score_tokens(
        self, tokens: list[dict[str, Any]], profile_name: str | None = None
    ) -> dict[str, Any]:
        """
        Main entry point: filter and score a batch of tokens
        Returns filtered, scored, and ranked results
        """
        profile_name = profile_name or self.get_current_profile()

        logger.info(f"Processing {len(tokens)} tokens with profile: {profile_name}")

        results = {
            "profile_used": profile_name,
            "input_count": len(tokens),
            "passed_filters": 0,
            "failed_filters": 0,
            "returned_count": 0,
            "tokens": [],
            "filter_summary": {},
            "processing_time": None,
        }

        start_time = datetime.now()
        filter_failures = {}

        # Step 1: Apply hard filters
        filtered_tokens = []
        for token in tokens:
            passes, reasons = self.rules.apply_hard_filters(token, profile_name)

            if passes:
                filtered_tokens.append(token)
                results["passed_filters"] += 1
            else:
                results["failed_filters"] += 1
                # Track failure reasons for summary
                for reason in reasons:
                    filter_failures[reason] = filter_failures.get(reason, 0) + 1

        logger.info(
            f"Hard filters: {results['passed_filters']} passed, {results['failed_filters']} failed"
        )

        # Step 2: Score remaining tokens
        scored_tokens = []
        for token in filtered_tokens:
            score_data = self.rules.calculate_score(token, profile_name)

            # Enhance token data with scoring
            enhanced_token = token.copy()
            enhanced_token["score_total"] = score_data["total"]
            enhanced_token["score_breakdown"] = score_data["breakdown"]

            scored_tokens.append(enhanced_token)

        # Step 3: Apply minimum score threshold
        output_config = self.rules.get_output_limits()
        min_score = output_config.get("min_score", 70)
        top_n = output_config.get("top_n", 10)

        qualifying_tokens = [t for t in scored_tokens if t["score_total"] >= min_score]

        # Step 4: Sort by score and limit results
        qualifying_tokens.sort(key=lambda x: x["score_total"], reverse=True)
        final_tokens = qualifying_tokens[:top_n]

        # Populate results
        results["returned_count"] = len(final_tokens)
        results["tokens"] = final_tokens
        results["filter_summary"] = filter_failures
        results["processing_time"] = (datetime.now() - start_time).total_seconds()

        logger.info(f"Final results: {len(final_tokens)} tokens returned (min_score: {min_score})")

        return results

    def get_token_analysis(
        self, token_data: dict[str, Any], profile_name: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze a single token in detail
        Returns comprehensive analysis including filter results and scoring breakdown
        """
        profile_name = profile_name or self.get_current_profile()

        # Apply filters
        passes_filters, filter_reasons = self.rules.apply_hard_filters(token_data, profile_name)

        # Calculate score regardless of filter result
        score_data = self.rules.calculate_score(token_data, profile_name)

        # Get profile configuration
        filters = self.rules.get_filters(profile_name)
        weights = self.rules.get_weights(profile_name)

        analysis = {
            "token_address": token_data.get("token_address", ""),
            "symbol": token_data.get("symbol", ""),
            "name": token_data.get("name", ""),
            "profile_used": profile_name,
            "passes_filters": passes_filters,
            "filter_failures": filter_reasons,
            "score_total": score_data["total"],
            "score_breakdown": score_data["breakdown"],
            "meets_minimum": score_data["total"] >= self.rules.output.get("min_score", 70),
            "profile_config": {"filters": filters, "weights": weights},
            "recommendations": self._generate_recommendations(
                token_data, score_data, filter_reasons
            ),
        }

        return analysis

    def _generate_recommendations(
        self, token_data: dict[str, Any], score_data: dict[str, Any], filter_failures: list[str]
    ) -> list[str]:
        """Generate improvement recommendations for token"""
        recommendations = []

        # Filter-based recommendations
        if filter_failures:
            recommendations.append("Address filter failures to qualify for trading")
            for failure in filter_failures[:3]:  # Top 3 issues
                recommendations.append(f"• {failure}")

        # Score-based recommendations
        breakdown = score_data.get("breakdown", {})
        low_categories = []

        for category, data in breakdown.items():
            if data["score"] < 50:  # Low score threshold
                low_categories.append(category)

        if low_categories:
            recommendations.append("Improve scores in weak categories:")
            for category in low_categories[:3]:
                recommendations.append(
                    f"• {category.title()}: {breakdown[category]['score']:.1f}/100"
                )

        if not recommendations:
            recommendations.append("Token shows strong metrics across all categories")

        return recommendations

    def get_profile_summary(self, profile_name: str | None = None) -> dict[str, Any]:
        """Get summary of profile configuration"""
        profile_name = profile_name or self.get_current_profile()

        filters = self.rules.get_filters(profile_name)
        weights = self.rules.get_weights(profile_name)
        output_config = self.rules.get_output_limits()

        return {
            "profile_name": profile_name,
            "description": f"Token filtering profile: {profile_name}",
            "key_filters": {
                "min_liquidity_usd": filters.get("min_liquidity_usd", 0),
                "min_holders": filters.get("min_holders", 0),
                "max_dev_holdings_pct": filters.get("max_dev_holdings_pct", 100),
                "min_age_minutes": filters.get("min_age_minutes", 0),
                "max_age_minutes": filters.get("max_age_minutes", 1440),
            },
            "scoring_weights": weights,
            "output_limits": output_config,
            "total_filters": len(filters),
            "available_profiles": list(self.rules.profiles.keys()),
        }

    def validate_token_data(self, token_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate that token data contains required fields"""
        required_fields = self.rules.fields
        missing_fields = []

        for field in required_fields:
            if field not in token_data:
                missing_fields.append(field)

        return len(missing_fields) == 0, missing_fields

    def export_results_summary(self, results: dict[str, Any]) -> str:
        """Export results as formatted summary text"""
        tokens = results.get("tokens", [])
        profile = results.get("profile_used", "unknown")

        summary_lines = [
            f"🎯 **Token Discovery Results - {profile.title()} Profile**",
            "",
            "📊 **Summary:**",
            f"• Input: {results.get('input_count', 0)} tokens",
            f"• Passed filters: {results.get('passed_filters', 0)}",
            f"• Failed filters: {results.get('failed_filters', 0)}",
            f"• Returned: {results.get('returned_count', 0)}",
            f"• Processing time: {results.get('processing_time', 0):.2f}s",
            "",
        ]

        if tokens:
            summary_lines.append("🏆 **Top Tokens:**")
            for i, token in enumerate(tokens[:5], 1):
                score = token.get("score_total", 0)
                symbol = token.get("symbol", "Unknown")
                liquidity = token.get("pool_liquidity_usd", 0)
                holders = token.get("holders_total", 0)

                summary_lines.append(f"{i}. **{symbol}** - Score: {score:.1f}/100")
                summary_lines.append(f"   Liquidity: ${liquidity:,.0f} | Holders: {holders:,}")

        # Filter failure summary
        failures = results.get("filter_summary", {})
        if failures:
            summary_lines.extend(["", "❌ **Common Filter Failures:**"])
            for reason, count in sorted(failures.items(), key=lambda x: x[1], reverse=True)[:5]:
                summary_lines.append(f"• {reason}: {count} tokens")

        return "\n".join(summary_lines)


# Utility functions for integration
def create_filter_engine(rules_path: str = "rules.yaml") -> TokenFilter:
    """Create and return configured token filter engine"""
    return TokenFilter(rules_path)


def quick_filter(
    tokens: list[dict[str, Any]], profile: str = "conservative"
) -> list[dict[str, Any]]:
    """Quick filtering function for simple use cases"""
    filter_engine = create_filter_engine()
    results = filter_engine.filter_and_score_tokens(tokens, profile)
    return results["tokens"]
