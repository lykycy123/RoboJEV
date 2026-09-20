#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$PROJECT_ROOT"
if conda run -n jev-vla-sim python -c 'import sys; assert sys.version_info[:2] == (3, 11)' >/dev/null 2>&1; then
    conda env update -n jev-vla-sim -f environment.yml
else
    conda env create -f environment.yml
fi
conda run -n jev-vla-sim python -m pip install --no-deps --no-build-isolation -e .
conda run -n jev-vla-sim python scripts/fetch_panda.py
conda run -n jev-vla-sim python -m pytest -q
conda run -n jev-vla-sim ruff check src tests scripts
conda run -n jev-vla-sim python scripts/check_environment.py
