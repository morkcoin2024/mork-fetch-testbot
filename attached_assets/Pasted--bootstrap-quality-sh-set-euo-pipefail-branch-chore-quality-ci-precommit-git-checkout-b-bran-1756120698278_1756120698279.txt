# bootstrap_quality.sh
set -euo pipefail

branch="chore/quality-ci-precommit"
git checkout -b "$branch" || git checkout "$branch"

mkdir -p .github/workflows

# --- .pre-commit-config.yaml ---
cat > .pre-commit-config.yaml <<'YAML'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.7
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.1
    hooks:
      - id: mypy
        args: [--ignore-missing-imports, --install-types, --non-interactive]
YAML

# --- pyproject.toml sections (create or append) ---
if [[ ! -f pyproject.toml ]]; then
  cat > pyproject.toml <<'TOML'
[tool.black]
line-length = 100
extend-exclude = '''(^birdeye_ws_backup\.py$)'''

[tool.ruff]
line-length = 100
extend-exclude = ["birdeye_ws_backup.py"]

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
exclude = '(?x)(^birdeye_ws_backup\.py$)'
TOML
else
  # Append (idempotent-ish). If you already have these sections, merge manually later.
  cat >> pyproject.toml <<'TOML'

[tool.black]
line-length = 100
extend-exclude = '''(^birdeye_ws_backup\.py$)'''

[tool.ruff]
line-length = 100
extend-exclude = ["birdeye_ws_backup.py"]

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
exclude = '(?x)(^birdeye_ws_backup\.py$)'
TOML
fi

# --- CODEOWNERS (edit handles to your org/team) ---
mkdir -p .github
cat > .github/CODEOWNERS <<'TXT'
*                       @your-org/maintainers
/tests/                 @your-org/qa-team
/app.py                 @your-handle
/telegram_polling.py    @your-handle
TXT

# --- Dependabot ---
cat > .github/dependabot.yml <<'YAML'
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule: { interval: "weekly" }
    open-pull-requests-limit: 5
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
YAML

# --- CI: PR quality ---
cat > .github/workflows/quality.yml <<'YAML'
name: quality
on:
  pull_request:
  push:
    branches: [ main ]
jobs:
  lint-and-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install tools
        run: |
          python -m pip install --upgrade pip
          pip install pre-commit pytest
      - name: Run pre-commit (black/ruff/mypy)
        run: pre-commit run --all-files
      - name: Targeted watchlist tests (offline)
        env:
          PYTHONPATH: .
          FETCH_ENABLE_SCANNERS: "0"
          FEATURE_WS: "off"
        run: |
          python -m pytest -q tests/test_watchlist*.py tests/test_watch*.py
YAML

# --- CI: nightly smoke (online) ---
cat > .github/workflows/nightly-smoke.yml <<'YAML'
name: nightly-smoke
on:
  schedule:
    - cron: "17 3 * * *"
  workflow_dispatch:
jobs:
  smoke:
    if: github.repository_owner == 'YOUR_ORG_OR_USER'
    runs-on: ubuntu-latest
    timeout-minutes: 40
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt || true
          pip install pytest coverage
      - name: Watchlist suite (offline + online)
        env:
          PYTHONPATH: .
          FEATURE_WS: "on"
          FETCH_ENABLE_SCANNERS: "1"
          SOLSCAN_API_KEY: ${{ secrets.SOLSCAN_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_ADMIN_ID: ${{ secrets.TELEGRAM_ADMIN_ID }}
        run: |
          ./run_watchlist_tests.sh
          bash scripts/run_coverage.sh || echo "coverage non-blocking"
      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: nightly-artifacts
          path: |
            coverage.xml
            .coverage*
            **/pytest-*.log
            **/test-output*.log
YAML

# Install & mass-fix locally
python -m pip install --upgrade pip
pip install pre-commit black ruff
pre-commit install
black .
ruff check . --fix

git add -A
git commit -m "chore: quality pipeline + pre-commit; format codebase (exclude birdeye_ws_backup.py)"
echo "Branch ready: $branch"
