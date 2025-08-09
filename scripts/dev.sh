#!/usr/bin/env bash
set -euo pipefail

# Run backend and frontend concurrently

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Start backend (apps/api)
(
  . "$PROJECT_ROOT"/.venv/bin/activate
  cd "$PROJECT_ROOT"/apps/api
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) &
BACK_PID=$!

# Start frontend (apps/satlink-pro)
(
  cd "$PROJECT_ROOT"/apps/satlink-pro
  npm run dev
) &
FRONT_PID=$!

trap 'echo "Stopping..."; kill $BACK_PID $FRONT_PID 2>/dev/null || true' INT TERM

wait $BACK_PID $FRONT_PID
