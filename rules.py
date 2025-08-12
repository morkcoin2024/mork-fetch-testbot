# rules.py
import logging, yaml
from pathlib import Path
from typing import Dict, Any, Tuple

RULES_PATH = Path("rules.yaml")
_cache: Dict[str, Any] = {"data": None, "mtime": None, "version": None}

DEFAULT_RULES = """version: 1
updated_at: "2025-08-10T00:00:00Z"
network: solana
sources: [pump.fun, dexscreener, jup.ag]
scan:
  max_age_minutes: 180
  holders_min: 75
  holders_max: 5000
  mcap_min_usd: 50000
  mcap_max_usd: 2000000
  liquidity_min_usd: 10000
  renounced_mint_auth: true
  renounced_freeze_auth: true
  blacklist_contracts: []
  include_keywords: []
  exclude_keywords: [rug, scam]
risk:
  max_score: 70
  weights: {age: 0.2, holders: 0.2, liquidity: 0.25, mcap: 0.25, renounce: 0.1}
output:
  max_results: 10
  columns: [symbol, name, holders, mcap_usd, liquidity_usd, age_min, risk]
"""

def ensure_default_rules():
    if not RULES_PATH.exists():
        RULES_PATH.write_text(DEFAULT_RULES, encoding="utf-8")
        logging.info("[RULES] Created default rules.yaml")

def _validate(d: Dict[str, Any]) -> Tuple[bool, str]:
    # Support both old format (version, network, scan, risk, output) and new simplified format
    if "version" in d and "network" in d:
        # Old format validation
        for k in ["version", "network", "scan", "risk", "output"]:
            if k not in d:
                return False, f"Missing key: {k}"
    else:
        # New simplified format validation
        required_keys = ["min_liq_usd", "min_holders", "max_age_min", "min_mcap_usd", "risk"]
        for k in required_keys:
            if k not in d:
                return False, f"Missing key: {k}"
        # Validate risk sub-object
        if not isinstance(d.get("risk"), dict):
            return False, "risk must be an object"
    return True, "ok"

def load_rules(force: bool=False) -> Dict[str, Any]:
    ensure_default_rules()
    m = RULES_PATH.stat().st_mtime
    if not force and _cache["data"] is not None and _cache["mtime"] == m:
        return _cache["data"]
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    ok, msg = _validate(data)
    if not ok:
        raise ValueError(f"rules.yaml invalid: {msg}")
    
    # Normalize data format for backward compatibility
    if "version" not in data:
        # Convert new simplified format to expected structure
        normalized = {
            "version": "simplified",
            "network": "solana",
            "scan": {
                "max_age_minutes": data.get("max_age_min", 60),
                "holders_min": data.get("min_holders", 50),
                "mcap_min_usd": data.get("min_mcap_usd", 10000),
                "liquidity_min_usd": data.get("min_liq_usd", 5000),
                "renounced_mint_auth": not data.get("risk", {}).get("allow_mint", True),
                "renounced_freeze_auth": not data.get("risk", {}).get("allow_freeze", True),
            },
            "risk": data.get("risk", {}),
            "output": {"max_results": 10}
        }
        data = normalized
    
    _cache.update({"data": data, "mtime": m, "version": data.get("version")})
    logging.info("[RULES] Loaded (v%s)", data.get("version"))
    return data

def render_rules() -> str:
    try:
        txt = RULES_PATH.read_text(encoding="utf-8")
        return txt if len(txt) < 3800 else txt[:3700] + "\n…(truncated)…"
    except Exception as e:
        return f"# rules.yaml read error: {e}"

def get_rules_version() -> str:
    if _cache["version"] is None:
        load_rules()
    return str(_cache["version"])