.PHONY: install up down clean build run test test-integration test-all lint format refresh dev

# ---------- Docker ----------

# Build and start the container (frontend on :3001)
up:
	docker compose up -d --build

# Stop the container (keep data)
down:
	docker compose down

# Stop and wipe all data
clean:
	docker compose down -v

# Tail container logs
logs:
	docker compose logs -f

# ---------- Local dev ----------

# Install all dependencies (backend + frontend)
install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	cd frontend && npm install

# Run backend + frontend locally with hot reload
dev:
	@echo "Starting API on :8000 and frontend on :8080..."
	@echo "Open http://localhost:8080"
	@trap 'kill 0' EXIT; \
		.venv/bin/uvicorn fpl.api.app:app --port 8000 --reload & \
		cd frontend && npm run dev &  \
		wait

# Build frontend for production
build:
	cd frontend && npm run build

# Serve production build locally
run: build
	@echo "Serving at http://localhost:8000"
	.venv/bin/uvicorn fpl.api.app:app --port 8000

# Refresh FPL data
refresh:
	.venv/bin/fpl data refresh

# ---------- Testing ----------

test:
	.venv/bin/pytest tests/ -v -m "not integration"

test-integration:
	.venv/bin/pytest tests/test_integration/ -v -m integration

test-all:
	.venv/bin/pytest tests/ -v

# ---------- Code quality ----------

lint:
	.venv/bin/black --check src/ tests/
	.venv/bin/ruff check src/ tests/
	.venv/bin/mypy src/

format:
	.venv/bin/black src/ tests/
	.venv/bin/ruff check --fix src/ tests/
