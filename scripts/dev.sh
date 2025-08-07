#!/usr/bin/env bash
set -euo pipefail

# Run backend and frontend concurrently

# Start backend
(. .venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload) &
BACK_PID=$!

# Start frontend
(cd frontend && npm run dev -- --host) &
FRONT_PID=$!

trap 'echo "Stopping..."; kill $BACK_PID $FRONT_PID 2>/dev/null || true' INT TERM

wait $BACK_PID $FRONT_PID
