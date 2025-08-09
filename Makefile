# Makefile for SatLink Planner project

# Variables
PY ?= python3
PIP ?= pip3
VENV ?= .venv
UVICORN ?= uvicorn
# New app paths
API_DIR ?= apps/api
API_APP ?= main:app
FRONTEND_DIR ?= apps/satlink-pro
API_REQ ?= $(API_DIR)/requirements.txt

.PHONY: venv deps frontend-deps dev run build-frontend run-backend run-frontend clean test export

venv:
	@test -d $(VENV) || $(PY) -m venv $(VENV)
	@. $(VENV)/bin/activate; $(PIP) install --upgrade pip

deps: venv
	@. $(VENV)/bin/activate; \
	if [ -f requirements.txt ]; then $(PIP) install -r requirements.txt; fi; \
	if [ -f $(API_REQ) ]; then $(PIP) install -r $(API_REQ); fi

frontend-deps:
	@cd $(FRONTEND_DIR) && npm install

build-frontend:
	@cd $(FRONTEND_DIR) && npm run build

run-backend:
	@. $(VENV)/bin/activate; cd $(API_DIR) && $(UVICORN) $(API_APP) --host 0.0.0.0 --port 8000 --reload

run-frontend:
	@cd $(FRONTEND_DIR) && npm run dev

# Run both API and FE for local dev
# Press Ctrl+C to stop both
dev: deps frontend-deps
	@echo "Starting backend and frontend..."
	@bash scripts/dev.sh

# Production-ish run (serves frontend separately). Adjust if you later serve static from API.
run: deps build-frontend
	@. $(VENV)/bin/activate; cd $(API_DIR) && $(UVICORN) $(API_APP) --host 0.0.0.0 --port 8000

# Very light tests placeholder
test: deps
	@. $(VENV)/bin/activate; pytest -q || echo "No tests found or tests failed"

# Export build artifacts (frontend dist)
export: build-frontend
	@mkdir -p exports
	@cp -r $(FRONTEND_DIR)/.next exports/next-build || true

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist exports
