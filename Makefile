# Цели для Linux/macOS/WSL и CI. На Windows без make — прямые команды из AGENTS.md.
DC     = docker compose --env-file .env -f infra/docker-compose.yml
DC_DEV = $(DC) -f infra/docker-compose.dev.yml

.PHONY: up down logs test lint format openapi migration reseed validate e2e prod-up

up:            ## локально: БД, backend (reload), fsp-mock, mailpit
	$(DC_DEV) up -d --build db backend fsp-mock mailpit

down:
	$(DC_DEV) down

logs:
	$(DC_DEV) logs -f backend

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd fsp-mock && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

format:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd fsp-mock && uv run ruff check --fix . && uv run ruff format .

openapi:       ## выгрузить backend/openapi.json и перегенерировать клиент фронта
	cd backend && uv run python -m app.scripts.export_openapi
	cd frontend && npm run gen:api

migration:     ## make migration m="описание"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

reseed:
	@echo "TODO(T07): генератор демо-данных"

validate:
	@echo "TODO(T19): процедура валидации"

e2e:
	@echo "TODO(T14): Playwright"

prod-up:       ## на сервере: собрать и поднять всё
	$(DC) up -d --build --remove-orphans
