<!-- Сгенерировано `cd docs/pdf && npm run gen` (docs/pdf/gen.mjs). Не править руками. -->

# Библиотеки и компоненты с версиями

Прямые зависимости каждой части и версии, зафиксированные в lock-файлах (транзитивные зависимости — в самих lock-файлах). Сборки воспроизводимы: `uv sync --frozen` и `npm ci` ставят ровно эти версии. Лицензия проекта — MIT.

## Платформа и образы

| Компонент | Где используется |
|---|---|
| Python 3.12 | backend, fsp-mock, validation |
| uv>=0.12,<0.13 (менеджер пакетов Python) | backend/Dockerfile, CI |
| Node.js 22 | сборка frontend, e2e, PDF документации |
| PostgreSQL 16 | основная БД |
| `postgres:16-alpine` | compose |
| `boky/postfix:5.1.0` | compose |
| `postgres:16-alpine` | compose |
| `axllent/mailpit:latest` | compose (dev) |
| `python:3.12-slim` | backend |
| `python:3.12-slim` | fsp-mock |
| `node:22-alpine` | frontend + Caddy |
| `caddy:2-alpine` | frontend + Caddy |
| `quay.io/keycloak/keycloak:26.4` | мок ФСП ID |

## Backend (Python 3.12, `backend/uv.lock`)

| Пакет | Версия | Тип |
|---|---|---|
| `alembic` | 1.20.0 | runtime |
| `argon2-cffi` | 25.1.0 | runtime |
| `cryptography` | 50.0.2 | runtime |
| `email-validator` | 2.3.0 | runtime |
| `fastapi` | 0.142.2 | runtime |
| `httpx` | 0.28.1 | runtime |
| `jinja2` | 3.1.6 | runtime |
| `numpy` | 2.5.3 | runtime |
| `pdfplumber` | 0.11.10 | runtime |
| `psycopg` | 3.3.6 | runtime |
| `pydantic-settings` | 2.15.0 | runtime |
| `pyjwt` | 2.15.1 | runtime |
| `python-multipart` | 0.0.32 | runtime |
| `pyyaml` | 6.0.3 | runtime |
| `scipy` | 1.18.1 | runtime |
| `segno` | 1.6.6 | runtime |
| `sqlalchemy` | 2.1.3 | runtime |
| `weasyprint` | 70.0 | runtime |
| `matplotlib` | 3.11.2 | dev |
| `pytest` | 9.1.1 | dev |
| `pytest-asyncio` | 1.4.0 | dev |
| `ruff` | 0.16.10 | dev |

## Мок реестра ФСП (`fsp-mock/uv.lock`)

| Пакет | Версия | Тип |
|---|---|---|
| `fastapi` | 0.142.2 | runtime |
| `pydantic-settings` | 2.15.0 | runtime |
| `ruff` | 0.16.10 | dev |

## Frontend (`frontend/package-lock.json`)

| Пакет | Версия | Тип |
|---|---|---|
| `@fontsource-variable/inter` | 5.3.0 | runtime |
| `@fontsource/jetbrains-mono` | 5.3.0 | runtime |
| `@hookform/resolvers` | 5.9.1 | runtime |
| `@radix-ui/react-dialog` | 1.1.23 | runtime |
| `@radix-ui/react-slot` | 1.3.3 | runtime |
| `@radix-ui/react-tabs` | 1.1.21 | runtime |
| `@tanstack/react-query` | 5.104.1 | runtime |
| `class-variance-authority` | 0.7.1 | runtime |
| `clsx` | 2.1.1 | runtime |
| `lucide-react` | 1.52.0 | runtime |
| `openapi-fetch` | 0.17.0 | runtime |
| `react` | 19.3.0 | runtime |
| `react-dom` | 19.3.0 | runtime |
| `react-hook-form` | 7.89.0 | runtime |
| `react-router` | 7.18.4 | runtime |
| `recharts` | 3.10.1 | runtime |
| `tailwind-merge` | 3.7.0 | runtime |
| `zod` | 4.6.5 | runtime |
| `@eslint/js` | 10.0.1 | dev |
| `@tailwindcss/vite` | 4.3.3 | dev |
| `@types/node` | 22.20.5 | dev |
| `@types/react` | 19.3.0 | dev |
| `@types/react-dom` | 19.3.0 | dev |
| `@vitejs/plugin-react` | 6.1.1 | dev |
| `eslint` | 10.12.0 | dev |
| `eslint-plugin-react-hooks` | 7.1.1 | dev |
| `eslint-plugin-react-refresh` | 0.5.7 | dev |
| `globals` | 17.13.0 | dev |
| `openapi-typescript` | 7.13.0 | dev |
| `tailwindcss` | 4.3.3 | dev |
| `tw-animate-css` | 1.4.0 | dev |
| `typescript` | 5.9.3 | dev |
| `typescript-eslint` | 8.71.0 | dev |
| `vite` | 8.3.2 | dev |

## e2e (`e2e/package-lock.json`)

| Пакет | Версия | Тип |
|---|---|---|
| `@axe-core/playwright` | 4.13.0 | dev |
| `@playwright/test` | 1.63.0 | dev |
| `@types/node` | 22.20.5 | dev |
| `typescript` | 5.9.3 | dev |

## Сборка PDF документации (`docs/pdf/package-lock.json`)

| Пакет | Версия | Тип |
|---|---|---|
| `marked` | 16.4.2 | dev |
| `mermaid` | 11.17.2 | dev |
| `playwright-core` | 1.63.0 | dev |
| `smol-toml` | 1.9.0 | dev |

