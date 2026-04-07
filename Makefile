.PHONY: install dev dev-api dev-frontend build run test lint clean refresh

# Install all dependencies (backend + frontend)
install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	cd frontend && npm install

# Development: run both backend and frontend with hot reload
dev:
	@echo "Starting API on :8000 and frontend on :8080..."
	@echo "Open http://localhost:8080"
	@trap 'kill 0' EXIT; \
		.venv/bin/uvicorn fpl.api.app:app --port 8000 --reload & \
		cd frontend && npm run dev &  \
		wait

# Run just the API (backend only)
dev-api:
	.venv/bin/uvicorn fpl.api.app:app --port 8000 --reload

# Run just the frontend dev server
dev-frontend:
	cd frontend && npm run dev

# Build frontend for production
build:
	cd frontend && npm run build

# Production: serve everything from FastAPI (build frontend first)
run: build
	@echo "Serving at http://localhost:8000"
	.venv/bin/uvicorn fpl.api.app:app --port 8000

# Refresh FPL data
refresh:
	.venv/bin/fpl data refresh

# Run tests
test:
	.venv/bin/pytest tests/ -v -m "not integration"

test-integration:
	.venv/bin/pytest tests/test_integration/ -v -m integration

test-all:
	.venv/bin/pytest tests/ -v

# Code quality
lint:
	.venv/bin/black --check src/ tests/
	.venv/bin/ruff check src/ tests/
	.venv/bin/mypy src/

format:
	.venv/bin/black src/ tests/
	.venv/bin/ruff check --fix src/ tests/

# Clean build artifacts
clean:
	rm -rf frontend/dist frontend/node_modules/.vite
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
