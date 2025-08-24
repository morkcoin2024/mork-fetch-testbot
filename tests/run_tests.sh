#!/bin/bash
set -euo pipefail

echo "🎯 Mork F.E.T.C.H Bot - Enterprise Watchlist Test Suite"
echo "=" * 60

# Set environment for comprehensive testing
export FETCH_ENABLE_SCANNERS=1
export PYTHONPATH=.
export TEST_TIMEOUT=8

echo "⚙️ Configuration:"
echo "   - Scanners: Enabled"
echo "   - Timeout: ${TEST_TIMEOUT}s"
echo "   - Mode: Production validation"
echo ""

cd "$(dirname "$0")/.."

echo "🚀 Running enterprise watchlist optimization tests..."
python tests/test_watchlist.py

echo ""
echo "✅ All tests completed successfully!"
echo "🏆 Enterprise-grade watchlist system validated"