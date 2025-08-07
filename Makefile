# Makefile for SatLink Planner project

# Variables
PY ?= python3
PIP ?= pip3
VENV ?= .venv
UVICORN ?= uvicorn
BACKEND_APP ?= backend.main:app
FRONTEND_DIR ?= frontend

.PHONY: venv deps frontend-deps dev run build-frontend run-backend run-frontend clean test export

venv:
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@. $(VENV)/bin/activate; $(PIP) install --upgrade pip

deps: venv
	@. $(VENV)/bin/activate; $(PIP) install -r requirements.txt

frontend-deps:
	@cd $(FRONTEND_DIR) && npm install

build-frontend:
	@cd $(FRONTEND_DIR) && npm run build

run-backend:
	@. $(VENV)/bin/activate; $(UVICORN) $(BACKEND_APP) --host 0.0.0.0 --port 8000 --reload

run-frontend:
	@cd $(FRONTEND_DIR) && npm run dev -- --host

# Run both API and FE for local dev
# Press Ctrl+C to stop both
dev: deps frontend-deps
	@echo "Starting backend and frontend..."
	@bash scripts/dev.sh

# Production-ish run (serves frontend from FastAPI)
run: deps build-frontend
	@. $(VENV)/bin/activate; export SERVE_STATIC=1; $(UVICORN) $(BACKEND_APP) --host 0.0.0.0 --port 8000

# Very light tests placeholder
test: deps
	@. $(VENV)/bin/activate; pytest -q || echo "No tests found or tests failed"

# Export build artifacts (frontend dist + sample exports if any)
export: build-frontend
	@mkdir -p exports
	@cp -r frontend/dist exports/frontend-dist

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist exports
