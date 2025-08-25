#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
export PIP_CONFIG_FILE=/dev/null
unset PIP_USER PIP_TARGET PIP_REQUIRE_VIRTUALENV
pre-commit clean || true
pre-commit run --all-files
