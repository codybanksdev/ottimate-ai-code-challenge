#!/usr/bin/env bash
# One-time setup: Python venv, backend deps, database, seed + ERP import,
# frontend deps. Safe to run again; it never deletes your database
# (use ./reset_db.sh for that).
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements.txt

(
  cd backend
  ../.venv/bin/python manage.py migrate --verbosity 0
  ../.venv/bin/python manage.py seed_data
  ../.venv/bin/python manage.py import_vendors --source simulated_erp/data/vendors.json
)

(cd frontend && npm install --no-audit --no-fund)

echo "Setup complete. Run ./start.sh"
