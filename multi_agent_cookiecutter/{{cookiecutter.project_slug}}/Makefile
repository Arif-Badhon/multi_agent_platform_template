.PHONY: help install run dev docker-build docker-up docker-down test lint clean

help:
	@echo "Available commands:"
	@echo "  install      Install dependencies using uv"
	@echo "  run          Run the FastAPI server"
	@echo "  dev          Run the FastAPI server with hot reload"
	@echo "  docker-build Build the Docker image"
	@echo "  docker-up    Start the services using Docker Compose"
	@echo "  docker-down  Stop the Docker Compose services"
	@echo "  test         Run tests using pytest"
	@echo "  lint         Run linters (ruff, mypy)"
	@echo "  clean        Remove __pycache__ and build artifacts"

install:
	uv pip install -e ".[dev]"

run:
	uv run uvicorn src.backend.main:app --host 0.0.0.0 --port 8000

dev:
	uv run uvicorn src.backend.main:app --reload --host 127.0.0.0 --port 8000

docker-build:
	docker build -t voice_ai_api:latest .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

test:
	uv run pytest tests/

lint:
	uv run ruff check .
	uv run mypy src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
