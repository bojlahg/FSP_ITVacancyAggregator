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
	cd backend && uv run ruff check . ../validation && uv run ruff format --check . ../validation
	cd fsp-mock && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

format:
	cd backend && uv run ruff check --fix . ../validation && uv run ruff format . ../validation
	cd fsp-mock && uv run ruff check --fix . && uv run ruff format .

openapi:       ## выгрузить backend/openapi.json и перегенерировать клиент фронта
	cd backend && uv run python -m app.scripts.export_openapi
	cd frontend && npm run gen:api

migration:     ## make migration m="описание"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

reseed:        ## демо-данные заново (на сервере: в контейнере backend)
	$(DC) exec -T backend python -m seed.generate

validate:      ## симуляционная валидация (§12) → docs/validation/report.md, metrics.json, PNG
	cd backend && uv run python ../validation/run.py

e2e:           ## демо-сценарий §18 в Playwright против прода (другой стенд — E2E_BASE_URL=...)
	cd e2e && npm ci && npx playwright install chromium && npx playwright test

prod-up:       ## на сервере: собрать и поднять всё
	$(DC) up -d --build --remove-orphans
