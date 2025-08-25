.PHONY: init lint fmt typecheck precommit smoke

init:
	python3 -m pip install -U pip
	test -f requirements-dev.txt || printf "black==24.8.0\nruff==0.5.7\nmypy==1.10.0\npre-commit==3.7.1\n" > requirements-dev.txt
	pip install -r requirements-dev.txt
	pre-commit install

lint:
	ruff check .

fmt:
	black .

typecheck:
	mypy .

precommit:
	pre-commit run --all-files || true

smoke:
	PYTHONPATH=. ./run_watchlist_tests.sh ; \
	bash scripts/run_coverage.sh || true
