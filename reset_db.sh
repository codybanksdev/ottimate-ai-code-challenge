#!/usr/bin/env bash
# Deletes the local database and rebuilds it from the ERP data.
set -euo pipefail
cd "$(dirname "$0")/backend"
rm -f db.sqlite3
../.venv/bin/python manage.py migrate --verbosity 0
../.venv/bin/python manage.py seed_data
../.venv/bin/python manage.py import_vendors --source simulated_erp/data/vendors.json
