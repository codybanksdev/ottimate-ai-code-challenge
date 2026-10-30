#!/usr/bin/env bash
# Backend on http://127.0.0.1:8009, frontend on http://localhost:3009.
cd "$(dirname "$0")"

cleanup() {
    kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT

(cd backend && ../.venv/bin/python manage.py runserver 127.0.0.1:8009) &
# The two host settings let the dev server work behind a forwarded port
# (Codespaces, Dev Containers), where the hostname is not localhost.
(cd frontend && BROWSER=none PORT=3009 DANGEROUSLY_DISABLE_HOST_CHECK=true WDS_SOCKET_PORT=0 npm start) &

wait
