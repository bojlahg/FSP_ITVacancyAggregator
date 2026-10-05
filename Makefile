# Цели для Linux/macOS/WSL и CI. На Windows без make — прямые команды из AGENTS.md.
DC     = docker compose --env-file .env -f infra/docker-compose.yml
DC_DEV = $(DC) -f infra/docker-compose.dev.yml

.PHONY: up down logs test lint format openapi migration reseed validate loadtest bank-review e2e docs-pdf prod-up

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

bank-review:   ## HTML-отчёт для ревью банка заданий с ключами → bank-review/<спец>.html (в git не попадает)
	cd backend && uv run python -m app.scripts.bank_review $(ARGS)

LOADTEST_URL ?= http://localhost:8000

loadtest:      ## нагрузка 10/30/50 пользователей по 60 с, только чтение; стенд с DEMO_MODE=true — LOADTEST_URL=..., ключи — ARGS="..."
	cd loadtest && uv run python run.py --base-url $(LOADTEST_URL) $(ARGS)

e2e:           ## демо-сценарий §18 в Playwright против прода (другой стенд — E2E_BASE_URL=...)
	cd e2e && npm ci && npx playwright install chromium && npx playwright test

docs-pdf:      ## версии и эндпоинты из lock-файлов и openapi.json, затем docs/ITScout-docs.pdf (Chromium — CHROMIUM_PATH)
	cd docs/pdf && npm ci && npm run build

prod-up:       ## на сервере: собрать и поднять всё
	$(DC) up -d --build --remove-orphans
