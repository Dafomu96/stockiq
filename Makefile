# StockIQ — Makefile
# Usage: make <target>
# Requires: Python 3.11+, Node 20+, Git

.PHONY: setup install test lint format typecheck docker clean help

# ── Setup ─────────────────────────────────────────────────────────────────────

setup: ## Full project setup — creates venv, installs all deps, copies .env
	@echo "→ Creating Python virtual environment..."
	python -m venv .venv
	@echo "→ Installing Python dependencies..."
	.venv/bin/pip install --upgrade pip -q
	.venv/bin/pip install -r requirements.txt -q
	@echo "→ Installing frontend dependencies..."
	cd frontend && npm install --silent
	@echo "→ Copying .env file..."
	@[ -f .env ] || cp .env.example .env
	@echo ""
	@echo "✅ Setup complete. Next steps:"
	@echo "   source .venv/bin/activate"
	@echo "   make test"
	@echo "   make run-api     # FastAPI on :8000"
	@echo "   make run-app     # Streamlit on :8501"

install: ## Install/update Python dependencies only
	.venv/bin/pip install -r requirements.txt -q
	@echo "✅ Dependencies installed"

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run full test suite with coverage
	.venv/bin/pytest tests/ -q

test-verbose: ## Run tests with verbose output
	.venv/bin/pytest tests/ -v

test-api: ## Run only API integration tests
	.venv/bin/pytest tests/test_api.py -v

test-watch: ## Re-run tests on file changes (requires pytest-watch)
	.venv/bin/ptw tests/ --runner "pytest -q"

# ── Code quality ──────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	.venv/bin/ruff check .

format: ## Format code with black
	.venv/bin/black .

format-check: ## Check formatting without modifying files
	.venv/bin/black --check .

typecheck: ## Run mypy type checker
	.venv/bin/mypy config/ data/ analysis/ simulation/ backend/ --ignore-missing-imports

quality: lint format-check typecheck ## Run all quality checks (mirrors CI)

# ── Running services ──────────────────────────────────────────────────────────

run-api: ## Start FastAPI backend on :8000
	.venv/bin/uvicorn backend.main:app --reload --port 8000

run-app: ## Start Streamlit MVP on :8501
	.venv/bin/streamlit run app/streamlit_app.py

run-frontend: ## Start React dev server on :5173 (requires API on :8000)
	cd frontend && npm run dev

# ── Docker ────────────────────────────────────────────────────────────────────

docker: ## Build and start all services via Docker Compose
	docker compose up --build

docker-api: ## Build and start API + React only
	docker compose up --build api frontend

docker-down: ## Stop all Docker services
	docker compose down

docker-logs: ## Tail logs from all services
	docker compose logs -f

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean: ## Remove build artefacts, cache, compiled files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage coverage.xml htmlcov .mypy_cache
	rm -rf frontend/dist frontend/node_modules/.cache
	@echo "✅ Cleaned"

# ── Help ──────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
