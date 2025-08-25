set -euo pipefail
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate

export PIP_CONFIG_FILE=/dev/null
export PYTHONPATH=.

python -m pip install -U pip setuptools wheel >/dev/null
python -m pip install -U "ruff==0.5.7" "black==24.8.0" "mypy==1.10.0" >/dev/null

echo "== Lint (Ruff, safe fixes) =="
ruff check . --force-exclude --fix || true

echo
echo "== Format (Black) =="
black --check . --extend-exclude '^(birdeye_ws_backup\.py|final_.*\.py|simple_.*\.py|demo_.*\.py|live_.*\.py|.*_example\.py|.*_demo\.py|standalone_.*\.py|production_.*\.py|direct_.*\.py|working_.*\.py|scripts/.*)$' \
  || black . --extend-exclude '^(birdeye_ws_backup\.py|final_.*\.py|simple_.*\.py|demo_.*\.py|live_.*\.py|.*_example\.py|.*_demo\.py|standalone_.*\.py|production_.*\.py|direct_.*\.py|working_.*\.py|scripts/.*)$'

echo
echo "== Types (mypy, trimmed scope) =="
mypy --ignore-missing-imports \
  --exclude '(birdeye_ws_backup\.py|final_.*\.py|simple_.*\.py|demo_.*\.py|live_.*\.py|.*_example\.py|.*_demo\.py|standalone_.*\.py|production_.*\.py|direct_.*\.py|working_.*\.py|scripts/.*)' || true

echo
echo "== Watchlist tests =="
PYTHONPATH=. ./run_watchlist_tests.sh

echo
echo "✅ Quality gate complete."
