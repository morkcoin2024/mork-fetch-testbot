#!/usr/bin/env bash
set -euo pipefail

# Prefer local venv if present
if [ -d ".venv/bin" ]; then
  export PATH="$PWD/.venv/bin:$PATH"
fi

# Ensure pip will not try a user install inside a venv
export PIP_CONFIG_FILE=/dev/null
export PIP_NO_USER=1
set -euo pipefail
export PYTHONPATH="${PYTHONPATH:-.}"

echo "== Smoke (scanners OFF) =="
python3 tests/test_watch_remove.py
python3 tests/test_watchlist_scale.py
python3 tests/test_watchlist.py
python3 tests/test_watchlist_edge.py

echo
echo "== Full (scanners ON) =="
FETCH_ENABLE_SCANNERS=1 FEATURE_WS=on TEST_TIMEOUT=12 python3 tests/test_watch_remove.py
FETCH_ENABLE_SCANNERS=1 FEATURE_WS=on TEST_TIMEOUT=12 python3 tests/test_watchlist_scale.py
FETCH_ENABLE_SCANNERS=1 FEATURE_WS=on TEST_TIMEOUT=12 python3 tests/test_watchlist.py
FETCH_ENABLE_SCANNERS=1 FEATURE_WS=on TEST_TIMEOUT=12 python3 tests/test_watchlist_edge.py

echo
echo "✓ All watchlist tests passed"
