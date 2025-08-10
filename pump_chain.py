# pump_chain.py
# Lightweight on-chain watcher for Pump.fun launches.
# Notes:
# - Requires a Solana RPC endpoint (WebSocket recommended; HTTP fallback works).
# - Program ID is configurable so we're not locked to a guess.
# - Returns a normalized list with minimal fields and source='pumpfun-chain'.

from __future__ import annotations
import os, time, math, json, logging, datetime
import httpx

# Import event publishing for on-chain monitoring
try:
    from eventbus import publish
except ImportError:
    def publish(event_type, data):
        pass  # Fallback if eventbus not available

PUMPFUN_PROGRAM_ID = os.environ.get("PUMPFUN_PROGRAM_ID", "").strip()  # e.g., set in Replit Secrets
SOLANA_RPC_HTTP = os.environ.get("SOLANA_RPC_HTTP", "").strip()        # https URL from Helius/QuickNode/etc.

def _now_utc():
    return datetime.datetime.utcnow()

def _age_minutes(ts_utc: datetime.datetime) -> int:
    return max(0, int((_now_utc() - ts_utc).total_seconds() // 60))

def _json_rpc(client: httpx.Client, method: str, params: list, timeout=15):
    r = client.post(
        SOLANA_RPC_HTTP,
        json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
        timeout=timeout,
    )
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]

def fetch_recent_pumpfun_mints(max_minutes: int = 60, limit: int = 50) -> list[dict]:
    """
    HTTP fallback (portable) using getSignaturesForAddress on the Pump.fun program,
    then sampling recent confirmed transactions within the last `max_minutes`.
    This is a heuristic seed (fast & robust). For production you can upgrade to
    logsSubscribe (WebSocket) later without changing call sites.
    """
    if not PUMPFUN_PROGRAM_ID or not SOLANA_RPC_HTTP:
        logging.warning("[CHAIN] Missing PUMPFUN_PROGRAM_ID or SOLANA_RPC_HTTP")
        # Publish configuration failure event
        publish("fetch.onchain.status", {"status": "fail", "code": "missing_config"})
        return []

    try:
        headers = {"Content-Type":"application/json"}
        with httpx.Client(headers=headers) as c:
            sigs = _json_rpc(c, "getSignaturesForAddress", [PUMPFUN_PROGRAM_ID, {"limit": limit}])
            out = []
            now = _now_utc()
            for s in sigs:
                # s: { "signature": "...", "blockTime": 171..., "slot": ..., ... }
                bt = s.get("blockTime")
                if not bt:
                    continue
                ts = datetime.datetime.utcfromtimestamp(bt)
                age_min = int((now - ts).total_seconds() // 60)
                if age_min > max_minutes:
                    continue

                # We don't fetch full tx here (fast path). This is a NEW-CANDIDATE seed row.
                out.append({
                    "source": "pumpfun-chain",
                    "symbol": None,   # unknown at this stage
                    "name": None,     # unknown at this stage
                    "mint": None,     # can be filled if you later parse the tx meta
                    "holders": None,  # unknown (too new)
                    "mcap_usd": None, # unknown (until Dexscreener enrichment)
                    "liquidity_usd": None,
                    "age_min": age_min,
                })
            logging.info("[CHAIN] pumpfun-chain yielded %d seed rows (<=%dmin)", len(out), max_minutes)
            # Publish successful on-chain fetch event
            publish("fetch.onchain.status", {"status": "ok", "n": len(out), "max_minutes": max_minutes})
            return out
    except Exception as e:
        logging.exception("[CHAIN] pumpfun-chain fetch error")
        # Publish on-chain fetch failure event
        publish("fetch.onchain.status", {"status": "fail", "code": "rpc_error", "error": str(e)})
        return []