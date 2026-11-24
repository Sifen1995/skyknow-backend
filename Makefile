.PHONY: help dev down build logs migrate seed seed-super-super-admin test test-newman test-api lint clean

# Default target when you just run 'make'
help:
	@echo "SkyKnow Enterprise Knowledge Platform - Makefile Commands"
	@echo "--------------------------------------------------------"
	@echo "  make dev          - Start local Docker Compose services"
	@echo "  make down         - Stop and remove Docker Compose containers"
	@echo "  make build        - Rebuild all Docker containers"
	@echo "  make logs         - Tail Docker container logs"
	@echo "  make migrate      - Run database migrations via Alembic"
	@echo "  make migration    - Create a new Alembic migration (usage: make migration msg='description')"
	@echo "  make seed         - Seed users (SEED_USER_PASSWORD must be 8+ characters)"
	@echo "  make seed-super-super-admin - Seed the configured platform super-super admin"
	@echo "  make test         - Run pytest integration and unit tests"
	@echo "  make test-newman  - Run automated Postman integration test suite via Docker"
	@echo "  make test-api     - Alias for make test-newman"
	@echo "  make lint         - Run Ruff, Mypy, and import-linter locally"
	@echo "  make clean        - Remove python cache, build files, and temporary artifacts"

# --- Docker Environment Management ---
dev:
	@docker compose up -d --build --wait || { echo "\n[ERROR] Service startup failed! Recent logs from api:"; docker compose logs api --tail 50; exit 1; }
	@echo "Services started successfully and API is healthy. FastAPI is running on http://localhost:8000"

down:
	docker compose down

build:
	docker compose build --no-cache

logs:
	docker compose logs -f

# --- Database & Migrations ---
migrate:
	docker compose exec api alembic upgrade head

migration:
	@read -p "Enter migration description: " desc; \
	docker compose exec api alembic revision --autogenerate -m "$$desc"

seed:
	docker compose exec -e SEED_USER_PASSWORD api python -m scripts.seed.seed

seed-super-super-admin:
	docker compose exec api python -m scripts.seed.super_super_admin

# --- Testing & Code Quality ---
test:
	docker compose exec api pytest -v --cov=app

test-newman:
	@if command -v newman >/dev/null 2>&1; then \
		echo "Running Postman test suite with local newman..."; \
		newman run postman/collections/skyknow_api.postman_collection.json -e postman/environments/skyknow_api.postman_environment.json --reporters cli; \
	else \
		echo "Running Postman test suite via container (postman/newman:alpine)..."; \
		docker run --rm --network host -v "$$(pwd):/workspace" -w /workspace postman/newman:alpine run postman/collections/skyknow_api.postman_collection.json -e postman/environments/skyknow_api.postman_environment.json --reporters cli; \
	fi

test-api: test-newman

lint:
	uv sync --locked --all-groups
	uv run --locked --no-sync ruff check .
	uv run --locked --no-sync ruff format --check .
	uv run --locked --no-sync mypy app
	uv run --locked --no-sync lint-imports

# --- Cleanup ---
clean:
	@if find . -type f -name "*.pyc" -delete 2>/dev/null && \
		find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" \) -prune -exec rm -rf -- {} + 2>/dev/null; then \
		:; \
	else \
		echo "Some cache files are not writable; retrying cleanup with sudo."; \
		sudo sh -c 'find . -type f -name "*.pyc" -delete && find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" \) -prune -exec rm -rf -- {} +'; \
	fi
	@echo "Cleaned temporary Python cache files."


# format:
# 	uv run --locked --no-sync ruff check --fix .
# 	uv run --locked --no-sync ruff format .