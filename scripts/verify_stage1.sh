#!/usr/bin/env bash
set -euo pipefail

python -m compileall -q .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
pytest -q
ruff check .
