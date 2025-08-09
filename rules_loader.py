"""
Rules Loader for Mork Fetch Bot
Loads and manages token filtering and scoring rules from YAML configuration
"""

import yaml
import os
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class Rules:
    """Token filtering and scoring rules manager"""
    
    def __init__(self, path: str = "rules.yaml"):
        self.path = path
        self.raw = {}
        self.meta = {}
        self.output = {}
        self.profiles = {}
        self.score_model = {}
        self.fields = []
        self.load()
    
    def load(self):
        """Load rules from YAML file"""
        try:
            if not os.path.exists(self.path):
                logger.error(f"Rules file not found: {self.path}")
                return False
                
            with open(self.path, "r", encoding="utf-8") as f:
                self.raw = yaml.safe_load(f)
            
            self.meta = self.raw.get("meta", {})
            self.output = self.raw.get("output", {})
            self.profiles = self.raw.get("profiles", {})
            self.score_model = self.raw.get("score_model", {})
            self.fields = self.raw.get("fields", [])
            
            logger.info(f"Loaded rules v{self.meta.get('version', 'unknown')} from {self.path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load rules from {self.path}: {e}")
            return False
    
    def reload(self) -> bool:
        """Reload rules from file"""
        return self.load()
    
    def profile(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Get profile configuration by name"""
        if not name:
            name = self.meta.get("default_profile", "conservative")
        
        if name not in self.profiles:
            logger.warning(f"Profile '{name}' not found, using conservative")
            name = "conservative"
            
        return self.profiles.get(name, {})
    
    def get_filters(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        """Get filter configuration for profile"""
        profile = self.profile(profile_name)
        return profile.get("filters", {})
    
    def get_weights(self, profile_name: Optional[str] = None) -> Dict[str, float]:
        """Get scoring weights for profile"""
        profile = self.profile(profile_name)
        weights = profile.get("weights", {})
        
        # Normalize weights to sum to 100
        total = sum(weights.values())
        if total > 0:
            return {k: (v / total) * 100 for k, v in weights.items()}
        return weights
    
    def get_output_limits(self) -> Dict[str, Any]:
        """Get output configuration"""
        return self.output
    
    def apply_hard_filters(self, token_data: Dict[str, Any], profile_name: Optional[str] = None) -> tuple[bool, List[str]]:
        """
        Apply hard filters to token data
        Returns (passes_filters, failed_reasons)
        """
        filters = self.get_filters(profile_name)
        failed_reasons = []
        
        # Age filters
        age_minutes = token_data.get("age_minutes", 0)
        if age_minutes < filters.get("min_age_minutes", 0):
            failed_reasons.append(f"Too young: {age_minutes}m < {filters['min_age_minutes']}m")
        if age_minutes > filters.get("max_age_minutes", float('inf')):
            failed_reasons.append(f"Too old: {age_minutes}m > {filters['max_age_minutes']}m")
        
        # Liquidity filters
        liquidity = token_data.get("pool_liquidity_usd", 0)
        min_liquidity = filters.get("min_liquidity_usd", 0)
        if liquidity < min_liquidity:
            failed_reasons.append(f"Low liquidity: ${liquidity:,.0f} < ${min_liquidity:,.0f}")
        
        # LP lock filters
        lp_locked_pct = token_data.get("lp_locked_pct", 0)
        min_lp_locked = filters.get("min_lp_locked_pct", 0)
        if lp_locked_pct < min_lp_locked:
            failed_reasons.append(f"LP not locked: {lp_locked_pct}% < {min_lp_locked}%")
        
        # Ownership filters
        dev_holdings = token_data.get("dev_holdings_pct", 100)
        max_dev_holdings = filters.get("max_dev_holdings_pct", 100)
        if dev_holdings > max_dev_holdings:
            failed_reasons.append(f"High dev holdings: {dev_holdings}% > {max_dev_holdings}%")
        
        top10_holdings = token_data.get("top10_holders_pct", 100)
        max_top10 = filters.get("max_top10_holders_pct", 100)
        if top10_holdings > max_top10:
            failed_reasons.append(f"High concentration: {top10_holdings}% > {max_top10}%")
        
        # Authority filters
        if filters.get("mint_revoked", False) and not token_data.get("mint_revoked", False):
            failed_reasons.append("Mint authority not revoked")
        if filters.get("freeze_revoked", False) and not token_data.get("freeze_revoked", False):
            failed_reasons.append("Freeze authority not revoked")
        
        # Volume filters
        volume_5m = token_data.get("volume_5m_usd", 0)
        min_volume_5m = filters.get("min_5m_volume_usd", 0)
        if volume_5m < min_volume_5m:
            failed_reasons.append(f"Low 5m volume: ${volume_5m:,.0f} < ${min_volume_5m:,.0f}")
        
        # Holder filters
        holders = token_data.get("holders_total", 0)
        min_holders = filters.get("min_holders", 0)
        if holders < min_holders:
            failed_reasons.append(f"Few holders: {holders} < {min_holders}")
        
        # Tax filters
        buy_tax = token_data.get("taxes_buy_pct", 0)
        max_buy_tax = filters.get("max_tax_buy_pct", 100)
        if buy_tax > max_buy_tax:
            failed_reasons.append(f"High buy tax: {buy_tax}% > {max_buy_tax}%")
        
        sell_tax = token_data.get("taxes_sell_pct", 0)
        max_sell_tax = filters.get("max_tax_sell_pct", 100)
        if sell_tax > max_sell_tax:
            failed_reasons.append(f"High sell tax: {sell_tax}% > {max_sell_tax}%")
        
        # Blocklist check
        blocklist_terms = filters.get("blocklist_terms", [])
        token_name = token_data.get("name", "").lower()
        token_symbol = token_data.get("symbol", "").lower()
        for term in blocklist_terms:
            if term.lower() in token_name or term.lower() in token_symbol:
                failed_reasons.append(f"Blocklisted term: {term}")
        
        return len(failed_reasons) == 0, failed_reasons
    
    def calculate_score(self, token_data: Dict[str, Any], profile_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive token score
        Returns score breakdown and total
        """
        weights = self.get_weights(profile_name)
        score_breakdown = {}
        total_score = 0.0
        
        # Calculate each category score
        for category, weight in weights.items():
            if category in self.score_model:
                category_score = self._calculate_category_score(token_data, category)
                score_breakdown[category] = {
                    "score": category_score,
                    "weight": weight,
                    "weighted": category_score * weight / 100
                }
                total_score += category_score * weight / 100
        
        return {
            "total": min(100.0, max(0.0, total_score)),
            "breakdown": score_breakdown
        }
    
    def _calculate_category_score(self, token_data: Dict[str, Any], category: str) -> float:
        """Calculate score for a specific category"""
        if category not in self.score_model:
            return 0.0
        
        metrics = self.score_model[category]
        scores = []
        
        for metric, config in metrics.items():
            score = self._calculate_metric_score(token_data, metric, config)
            scores.append(score)
        
        # Average all metric scores in category
        return sum(scores) / len(scores) * 100 if scores else 0.0
    
    def _calculate_metric_score(self, token_data: Dict[str, Any], metric: str, config: Dict) -> float:
        """Calculate score for a specific metric"""
        value = token_data.get(metric, 0)
        
        if "thresholds" in config:
            # Higher is better
            thresholds = config["thresholds"]
            return self._threshold_score(value, thresholds)
        
        elif "inverse_thresholds" in config:
            # Lower is better
            thresholds = config["inverse_thresholds"]
            return self._inverse_threshold_score(value, thresholds)
        
        elif isinstance(config, dict) and "true" in config:
            # Boolean mapping
            return config.get(str(value).lower(), 0.0)
        
        elif isinstance(config, dict):
            # Direct value mapping
            return config.get(value, 0.0)
        
        return 0.0
    
    def _threshold_score(self, value: float, thresholds: List[float]) -> float:
        """Score based on threshold buckets (higher is better)"""
        for i, threshold in enumerate(thresholds):
            if value <= threshold:
                return i / len(thresholds)
        return 1.0
    
    def _inverse_threshold_score(self, value: float, thresholds: List[float]) -> float:
        """Score based on inverse threshold buckets (lower is better)"""
        for i, threshold in enumerate(thresholds):
            if value >= threshold:
                return 1.0 - (i / len(thresholds))
        return 1.0
    
    def set_profile(self, profile_name: str) -> bool:
        """Set default profile"""
        if profile_name in self.profiles:
            self.meta["default_profile"] = profile_name
            return True
        return False
    
    def update_filter(self, profile_name: str, filter_key: str, value: Any) -> bool:
        """Update a filter value"""
        if profile_name in self.profiles:
            if "filters" not in self.profiles[profile_name]:
                self.profiles[profile_name]["filters"] = {}
            self.profiles[profile_name]["filters"][filter_key] = value
            return True
        return False
    
    def save(self) -> bool:
        """Save current rules back to YAML file"""
        try:
            # Update raw dict with current state
            self.raw["meta"] = self.meta
            self.raw["output"] = self.output
            self.raw["profiles"] = self.profiles
            self.raw["score_model"] = self.score_model
            self.raw["fields"] = self.fields
            
            with open(self.path, "w", encoding="utf-8") as f:
                yaml.dump(self.raw, f, default_flow_style=False, indent=2)
            
            logger.info(f"Saved rules to {self.path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save rules to {self.path}: {e}")
            return False