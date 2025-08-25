#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH=.
rm -f .coverage* coverage.xml || true

coverage run -p tests/test_watchlist.py
coverage run -p tests/test_watchlist_edge.py
coverage run -p tests/test_watch_remove.py
coverage run -p tests/test_watchlist_scale.py

coverage combine
coverage xml
coverage report -m
