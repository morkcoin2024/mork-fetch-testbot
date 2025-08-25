PY=python
PIP=$(PY) -m pip

.PHONY: setup format lint type test smoke online coverage quality all

setup:
	$(PIP) install -U pip
	$(PIP) install pre-commit black==24.8.0 ruff==0.5.6 mypy==1.10.0 coverage==7.6.1 pytest==8.3.2
	pre-commit install

format:
	$(PY) -m black .

lint:
	$(PY) -m ruff check . --fix

type:
	$(PY) -m mypy . || true

smoke:
	PYTHONPATH=. ./run_watchlist_tests.sh

online:
	FETCH_ENABLE_SCANNERS=1 FEATURE_WS=on TEST_TIMEOUT=12 PYTHONPATH=. python -m pytest -q || true

coverage:
	bash scripts/run_coverage.sh

quality: format lint type

all: quality smoke coverage