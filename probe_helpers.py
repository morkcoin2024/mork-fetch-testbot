# --- PROBE HELPERS -----------------------------------------------------------
import datetime as _dt
import os
import time

import httpx

PUMPFUN_FALLBACK = os.getenv("PUMPFUN_FALLBACK", "").strip()  # optional CF worker
PUMPFUN_DIRECT = "https://frontend-api.pump.fun/coins/created"
PUMPFUN_APIORG = "https://api.pumpfunapi.org/pumpfun/new/tokens"  # community API
HEL_RPC = os.getenv("SOLANA_RPC_HTTP", "").strip()
PUMPFUN_PROGRAM_ID = os.getenv("PUMPFUN_PROGRAM_ID", "PumpFun7fRPrLkM7hJwXcV34yM7ZLkSjt1eVgpo1S8f")


def _now_iso():
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def probe_pumpfun_sources(limit: int = 50) -> dict:
    """
    Try 3 routes quickly (first that returns 200 with JSON wins):
      1) Cloudflare Worker (if provided via PUMPFUN_FALLBACK)
      2) Direct Pump.fun (likely CDN/DNS blocks)
      3) pumpfunapi.org (community API)
    Also does a very light Solana RPC check to verify we can reach mainnet.
    Returns a dict with timings, status codes, and up to 3 sample rows.
    """
    results = {"at": _now_iso(), "limit": limit, "sources": []}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://pump.fun/",
        "Origin": "https://pump.fun",
    }

    def _try(label, url, params):
        t0 = time.time()
        code, n, samples, err = None, 0, [], None
        try:
            with httpx.Client(timeout=8.0) as c:
                r = c.get(url, params=params, headers=headers)
                code = r.status_code
                if r.status_code == 200:
                    data = r.json()
                    # normalise to list-ish
                    items = (
                        data
                        if isinstance(data, list)
                        else data.get("tokens") or data.get("data") or []
                    )
                    n = len(items)
                    # keep first 3 light samples
                    for it in items[:3]:
                        samples.append(
                            {
                                k: it.get(k)
                                for k in (
                                    "symbol",
                                    "name",
                                    "mint",
                                    "market_cap",
                                    "liquidity",
                                    "created_timestamp",
                                )
                                if k in it
                            }
                        )
                else:
                    err = f"HTTP {r.status_code}"
        except Exception as e:
            err = str(e)
        dt = round((time.time() - t0) * 1000)
        results["sources"].append(
            {
                "label": label,
                "url": url,
                "ms": dt,
                "status": code,
                "count": n,
                "error": err,
                "samples": samples,
            }
        )

    # 1) Worker (if set)
    if PUMPFUN_FALLBACK:
        _try(
            "pumpfun-via-worker",
            PUMPFUN_FALLBACK.rstrip("/") + "/pf/coins/created",
            {"limit": limit, "offset": 0},
        )

    # 2) Direct
    _try("pumpfun-direct", PUMPFUN_DIRECT, {"limit": limit, "offset": 0})

    # 3) Community API
    _try("pumpfunapi-org", PUMPFUN_APIORG, {"limit": limit})

    # 4) Very light Solana RPC reachability (no decode; just version)
    rpc = {
        "label": "solana-rpc",
        "url": HEL_RPC or "(unset)",
        "ok": False,
        "ms": None,
        "error": None,
    }
    if HEL_RPC:
        t0 = time.time()
        try:
            with httpx.Client(timeout=6.0) as c:
                r = c.post(HEL_RPC, json={"jsonrpc": "2.0", "id": 1, "method": "getVersion"})
                rpc["ms"] = round((time.time() - t0) * 1000)
                rpc["ok"] = r.status_code == 200
                if r.status_code != 200:
                    rpc["error"] = f"HTTP {r.status_code}"
        except Exception as e:
            rpc["ms"] = round((time.time() - t0) * 1000)
            rpc["error"] = str(e)
    results["rpc"] = rpc
    return results
