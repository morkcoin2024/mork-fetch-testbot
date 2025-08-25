#!/usr/bin/env bash
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
set -euo pipefail

echo "== Smoke (scanners OFF) =="
python3 tests/test_watchlist.py
python3 tests/test_watchlist_edge.py

echo
echo "== Full (scanners ON) =="
FETCH_ENABLE_SCANNERS=1 FEATURE_WS=on TEST_TIMEOUT=12 python3 tests/test_watchlist.py
FETCH_ENABLE_SCANNERS=1 FEATURE_WS=on TEST_TIMEOUT=12 python3 tests/test_watchlist_edge.py

echo
echo "✓ All watchlist tests passed"
