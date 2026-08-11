.PHONY: install test lint format up down logs ps airflow-cli generate ci

# Load .env (if present) and export every variable from it to every recipe
# below, so `make up` etc. don't require the developer to separately
# `source .env` first. Safe to run with no .env present (e.g. in CI, which
# supplies these as real environment variables instead) since `-include`
# does not fail when the file is missing.
-include .env
export

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v --cov=pipeline --cov=api

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

airflow-cli:
	docker compose exec airflow-scheduler airflow $(ARGS)

generate:
	python -m scripts.run_generators

ci: lint test
