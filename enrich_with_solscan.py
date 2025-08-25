"""
Solscan enrichment utility for token data
Provides enrichment functions for adding Solscan trending data to tokens
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def enrich_with_solscan(tokens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Enrich a list of tokens with Solscan trending data

    Args:
        tokens: List of token dictionaries with at least 'mint' or 'address' field

    Returns:
        List of enriched tokens with Solscan data added
    """
    try:
        from app import SCANNERS

        solscan_scanner = SCANNERS.get("solscan")

        if not solscan_scanner or not solscan_scanner.enabled:
            log.info("[ENRICH] Solscan scanner not available, skipping enrichment")
            return tokens

        enriched_count = 0

        for token in tokens:
            mint = token.get("mint") or token.get("address") or ""
            if mint:
                enrichment = solscan_scanner.enrich_token(mint)
                if enrichment:
                    # Add enrichment data to token
                    token.update(enrichment)
                    # Add Solscan score bonus to risk calculation
                    solscan_bonus = enrichment.get("solscan_score", 0)
                    current_risk = token.get("risk", 100)
                    token["risk"] = max(0, current_risk - solscan_bonus)
                    enriched_count += 1

        log.info(
            "[ENRICH] Solscan enrichment complete: %d/%d tokens enriched",
            enriched_count,
            len(tokens),
        )
        return tokens

    except Exception as e:
        log.warning("[ENRICH] Solscan enrichment failed: %r", e)
        return tokens


def get_solscan_badge(token: dict[str, Any]) -> str:
    """
    Generate a Solscan badge string for a token

    Args:
        token: Token dictionary with potential Solscan enrichment data

    Returns:
        Badge string for display
    """
    if token.get("solscan_trending_rank"):
        return f"trending #{token.get('solscan_trending_rank')}"
    elif token.get("solscan_trending"):
        return "trending"
    else:
        return "-"


def test_enrichment(limit: int = 5) -> dict[str, Any]:
    """
    Test Solscan enrichment with sample tokens

    Args:
        limit: Number of test tokens to process

    Returns:
        Test results dictionary
    """
    try:
        from data_fetcher import fetch_candidates_from_pumpfun

        # Get sample tokens
        sample_tokens = fetch_candidates_from_pumpfun(limit=limit, offset=0)
        if not sample_tokens:
            return {"error": "No sample tokens available"}

        # Test enrichment
        enriched_tokens = enrich_with_solscan(sample_tokens)

        enriched_count = sum(1 for t in enriched_tokens if t.get("solscan_trending"))

        results = {
            "total_tokens": len(sample_tokens),
            "enriched_tokens": enriched_count,
            "enrichment_rate": (
                f"{(enriched_count/len(sample_tokens)*100):.1f}%" if sample_tokens else "0%"
            ),
            "sample_enriched": [],
        }

        # Add samples of enriched tokens
        for token in enriched_tokens:
            if token.get("solscan_trending_rank"):
                results["sample_enriched"].append(
                    {
                        "symbol": token.get("symbol", "?"),
                        "name": token.get("name", "?"),
                        "rank": token.get("solscan_trending_rank"),
                        "badge": get_solscan_badge(token),
                    }
                )

        return results

    except Exception as e:
        return {"error": str(e)}
