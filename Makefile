# Mork F.E.T.C.H Bot - Enterprise Development Makefile

.PHONY: test-watchlist test-watchlist-strict test-watchlist-lenient test-all help

# Enterprise Watchlist Tests
test-watchlist:
	STRICT?=1 TEST_TIMEOUT?=8 python3 tests/test_watchlist.py

test-watchlist-strict:
	STRICT=1 TEST_TIMEOUT=8 python3 tests/test_watchlist.py

test-watchlist-lenient:
	STRICT=0 TEST_TIMEOUT=8 python3 tests/test_watchlist.py

test-all: test-watchlist-strict test-watchlist-lenient
	@echo "✅ All enterprise watchlist tests completed"

# Development helpers
install:
	python3 -m pip install -e .

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

help:
	@echo "Mork F.E.T.C.H Bot - Available targets:"
	@echo "  test-watchlist        Run enterprise watchlist tests (default: strict mode)"
	@echo "  test-watchlist-strict Run strict mode tests (requires real data)"
	@echo "  test-watchlist-lenient Run lenient mode tests (allows '?' values)"
	@echo "  test-all              Run both strict and lenient test modes"
	@echo "  install               Install project dependencies"
	@echo "  clean                 Remove Python cache files"
	@echo "  help                  Show this help message"

# Default target
.DEFAULT_GOAL := help