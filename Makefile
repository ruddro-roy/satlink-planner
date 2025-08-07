# Makefile for SatLink Planner project

.PHONY: db-init run-api

# -----------------------------------------------------------------------------
# Database initialisation helpers
# -----------------------------------------------------------------------------
# Create all tables when ENV=dev, otherwise run Alembic migrations up to *head*.
# -----------------------------------------------------------------------------

db-init:
	@echo "[db] Initialising database …"
	ENV=$${ENV:-dev} PYTHONPATH=apps/api \
	./venv/bin/python3.11 -c "import os,sys; sys.path.append('apps/api'); from core import db as _db; env=os.getenv('ENV','dev'); print(f'[db] ENV={env}'); (_db.create_all() if env=='dev' else _db.run_migrations())"
	@echo "[db] Done."

# -----------------------------------------------------------------------------
# Developer target to run API with auto-reload (ENV=dev by default)
# -----------------------------------------------------------------------------
run-api:
	ENV=$${ENV:-dev} PYTHONPATH=apps/api uvicorn apps.api.main:app --reload --port 8000
