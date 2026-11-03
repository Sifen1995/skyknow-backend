.PHONY: help dev up down build logs migrate seed test lint clean

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
	@echo "  make test         - Run pytest integration and unit tests"
	@echo "  make lint         - Run Ruff, Mypy, and import-linter locally"
	@echo "  make clean        - Remove python cache, build files, and temporary artifacts"

# --- Docker Environment Management ---
dev:
	docker compose up -d
	@echo "Services started. FastAPI is running on http://localhost:8000"

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

# --- Testing & Code Quality ---
test:
	docker compose exec api pytest -v --cov=app

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


# fix:
    
#     uv run --locked --no-sync ruff format
# 	uv run --locked --no-sync ruff check --fix