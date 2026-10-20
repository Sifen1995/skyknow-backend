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
	@echo "  make seed         - Seed database with initial data"
	@echo "  make test         - Run pytest integration and unit tests"
	@echo "  make lint         - Run ruff linter and mypy type checking"
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
	docker compose exec api python -m scripts.seed_data

# --- Testing & Code Quality ---
test:
	docker compose exec api pytest -v --cov=app

lint:
	docker compose exec api ruff check .
	docker compose exec api ruff format --check .
	docker compose exec api mypy app

# --- Cleanup ---
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name ".ruff_cache" -delete
	@echo "Cleaned temporary Python cache files."