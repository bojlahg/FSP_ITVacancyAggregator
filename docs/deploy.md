# Сборка, развёртывание и локальный запуск

Решение запускается одним `docker compose` на любой ОС с Docker (Linux, macOS, Windows с WSL 2) и на недорогом VDS: весь стенд занимает около 1,1 ГБ RAM.

| Способ | Для чего | Раздел |
|---|---|---|
| Весь стенд в Docker | проверить решение локально так, как оно работает на проде | 2 |
| Режим разработки | backend с hot reload + Vite dev server | 3 |
| Без Docker | только Python, Node.js и PostgreSQL | 4 |
| Прод | сервер, домен, HTTPS, CI/CD | 5 |

## 1. Требования

| Что | Версия | Нужно для |
|---|---|---|
| Docker Engine + Compose v2 | 24+ | разделы 2, 3, 5 |
| Git (+ Git LFS — только для PDF, шрифтов брендбука и PNG отчёта) | любая | все |
| Python + [uv](https://docs.astral.sh/uv/) | 3.12, uv 0.12 | разделы 3, 4, тесты, валидация |
| Node.js + npm | 22 | разделы 3, 4, e2e, сборка PDF документации |
| PostgreSQL | 16 | раздел 4 |
| Свободная память | ~2 ГБ (из них Keycloak до 1 ГБ) | весь стенд |

## 2. Весь стенд локально в Docker

```bash
git clone https://github.com/bojlahg/FSP_ITVacancyAggregator.git itscout
cd itscout
cp .env.example .env
```

В `.env` поменять четыре строки (остальное подходит как есть):

```bash
PUBLIC_BASE_URL=http://localhost
CORS_ORIGINS=["http://localhost"]
POSTGRES_PASSWORD=<любая строка>
KEYCLOAK_ADMIN_PASSWORD=<любая строка>
```

Собрать и поднять все сервисы (первая сборка — 5–10 минут), затем загрузить демо-данные:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker-compose.yml ps            # все сервисы Up, db и keycloak — healthy
docker compose --env-file .env -f infra/docker-compose.yml exec backend python -m seed.generate
```

Готово:

| Адрес | Что |
|---|---|
| http://localhost | приложение; «Вход» → «Демо-вход» → «Кандидат» или «Работодатель» |
| http://localhost/api/docs | Swagger UI |
| http://localhost/api/v1/health | `{"status":"ok","db":true}` |
| http://localhost/fsp-id/realms/fsp | мок ФСП ID (кнопка «Войти через ФСП ID» в настройках кандидата) |

Генератор демо-данных создаёт 600 кандидатов, проходящих тест через настоящий движок, 12 работодателей, 40 соревнований ФСП в моке реестра, приглашения и отклики во всех статусах (около минуты). Повторный запуск возвращает данные к исходному состоянию.

Замечания:
- Миграции БД применяются автоматически при старте backend.
- Письма подтверждения при `EMAIL_BACKEND=console` пишутся в лог backend (`docker compose ... logs backend`), подтверждение почты при `EMAIL_VERIFICATION_REQUIRED=false` не обязательно. Контейнер `mail` нужен только на проде.
- Caddy пытается выпустить сертификат для `itscout.ru` и пишет об этом ошибки в лог — локально это не мешает, сайт работает по HTTP на `localhost`.
- Если Docker Hub отвечает `429 Too Many Requests`, добавьте зеркало в `/etc/docker/daemon.json`: `{"registry-mirrors": ["https://mirror.gcr.io"]}` и перезапустите Docker.
- Остановить: `docker compose --env-file .env -f infra/docker-compose.yml down` (с `-v` — удалить и данные).

## 3. Режим разработки

```bash
make up                        # db, backend (hot reload, :8000), fsp-mock (:8001), mailpit (:8025)
docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml exec backend python -m seed.generate
cd frontend && npm ci && npm run dev    # http://localhost:5173, /api проксируется на :8000
```

Без `make` (Windows): `docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d --build db backend fsp-mock mailpit`. Письма видны в Mailpit: http://localhost:8025. Для `.env` подходят значения из `.env.example` как есть.

## 4. Без Docker

```bash
# 1. PostgreSQL 16: база и пользователь
createuser -P itscout && createdb -O itscout itscout

# 2. Мок реестра ФСП
cd fsp-mock && uv sync --frozen
FSP_DATA_PATH=../.data/fsp.json uv run uvicorn app.main:app --port 8001 &

# 3. Backend
cd ../backend && uv sync --frozen
export DATABASE_URL=postgresql+psycopg://itscout:<пароль>@localhost:5432/itscout
export FSP_API_URL=http://localhost:8001/fsp-api/v1 FSP_DATA_PATH=../.data/fsp.json UPLOAD_DIR=../.data/uploads
uv run alembic upgrade head
uv run python -m seed.generate
uv run uvicorn app.main:app --port 8000 &

# 4. Frontend
cd ../frontend && npm ci && npm run dev     # http://localhost:5173
```

PDF-профиль требует системных библиотек WeasyPrint (Pango, HarfBuzz): в Debian/Ubuntu — `apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`. Привязка через ФСП ID в этом режиме недоступна (нужен Keycloak), ручная привязка работает.

## 5. Прод

### 5.1. Сервер

1. VDS с Ubuntu, от 2 vCPU и 3 ГБ RAM. Установить Docker Engine и Compose plugin. Если Docker Hub недоступен — зеркало в `/etc/docker/daemon.json` (см. раздел 2). Своп 2 ГБ как подстраховка от OOM — `infra/scripts/setup-swap.sh` (идемпотентный; без SSH — `gh workflow run server-ops.yml -f action=swap`).
2. DNS: A-записи `itscout.ru` и `www.itscout.ru` → IP сервера. Caddy сам выпустит сертификат Let's Encrypt при первом запросе.
3. Для писем: открыть исходящий порт 25 у провайдера, в DNS — SPF `v=spf1 ip4:<IP> -all`, DKIM (`mail._domainkey`, ключ генерирует контейнер `mail` в volume `dkim`), DMARC; PTR IP → домен.
4. Каталог приложения `/opt/itscout/app`, в нём `.env` с правами 600:

```bash
APP_ENV=prod
DEMO_MODE=true                         # демо-вход и сброс демо-данных для жюри
PUBLIC_BASE_URL=https://itscout.ru
CORS_ORIGINS=["https://itscout.ru"]
COOKIE_SECURE=true
JWT_SECRET=<openssl rand -hex 32>
POSTGRES_PASSWORD=<openssl rand -hex 24>
KEYCLOAK_ADMIN_PASSWORD=<openssl rand -hex 24>
FSP_API_KEY=<openssl rand -hex 24>
DEMO_ADMIN_PASSWORD=<пароль демо-админа для POST /admin/reseed>
EMAIL_BACKEND=smtp
SMTP_HOST=mail
SMTP_PORT=25
SMTP_SECURITY=none
EMAIL_VERIFICATION_REQUIRED=false      # true — после проверки доставляемости писем
LLM_PROVIDER=none                      # yandex + YANDEX_API_KEY, YANDEX_FOLDER_ID — включить LLM
```

### 5.2. CI/CD

Деплой — push в `master` (`.github/workflows/ci.yml`):

1. **backend**: `ruff check` и `ruff format --check`, миграции с нуля + `alembic check`, `pytest` (с PostgreSQL 16 в service-контейнере), актуальность `openapi.json`;
2. **fsp-mock**: ruff;
3. **frontend**: eslint, `tsc`, актуальность сгенерированного клиента API, `vite build`;
4. **deploy** (после зелёных проверок): rsync репозитория на сервер в `/opt/itscout/app` (без `.env`) → `docker compose up -d --build --remove-orphans` → smoke-тест `/api/v1/health`;
5. **e2e**: Playwright (Chromium) проходит демо-сценарий против `https://itscout.ru`; при падении в артефакт уходят отчёт, трейсы, скриншоты и видео.

Единственный секрет GitHub — `DEPLOY_SSH_KEY` (отдельный ключ деплоя). Ручные правки на сервере не делаются: следующий деплой их затрёт.

### 5.3. Обслуживание без SSH

Workflow «Server ops» (`.github/workflows/server-ops.yml`) выполняет фиксированный набор действий на ключе деплоя:

```bash
gh workflow run server-ops.yml -f action=status                     # docker compose ps и health
gh workflow run server-ops.yml -f action=logs -f service=backend -f lines=200
gh workflow run server-ops.yml -f action=reseed                     # демо-данные заново
gh workflow run server-ops.yml -f action=restart -f service=backend
gh workflow run server-ops.yml -f action=swap                       # своп 2 ГБ (идемпотентно)
gh workflow run server-ops.yml -f action=llm-check                  # все сценарии LLM на настоящем провайдере
gh run watch <id> && gh run view <id> --log
```

С SSH: `cd /opt/itscout/app && make reseed` (или `docker compose --env-file .env -f infra/docker-compose.yml exec -T backend python -m seed.generate`). Демо-данные можно сбросить и через API: `POST /api/v1/admin/reseed` от демо-админа.

## 6. Проверки

| Что | Команда |
|---|---|
| Тесты backend (нужен PostgreSQL, `DATABASE_URL`) | `make test` или `cd backend && uv run pytest` |
| Линт и формат | `make lint` |
| Фронт | `cd frontend && npm run lint && npm run typecheck && npm run build` |
| Актуальность OpenAPI и клиента | `make openapi` → `git diff` пустой |
| Валидация (отчёт в `docs/validation/`, ~7–8 мин) | `make validate` |
| e2e против стенда | `make e2e` (другой стенд — `E2E_BASE_URL=http://localhost make e2e`) |
| Сборка PDF документации | `make docs-pdf` (`cd docs/pdf && npm ci && npm run build`) → `docs/ITScout-docs.pdf`; путь к Chromium — `CHROMIUM_PATH`, иначе браузер Playwright |

## 7. Переменные окружения

Полный список с комментариями — `.env.example` и `backend/app/core/config.py`. Основные:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `APP_ENV` | `dev` | `prod` требует собственный `JWT_SECRET` |
| `DEMO_MODE` | `true` | демо-вход, сброс демо-данных и ограничений смены грейда |
| `TEST_MODE` | `full` | `short` — сокращённый тест для показа (8–10 заданий) |
| `PUBLIC_BASE_URL`, `CORS_ORIGINS` | localhost:5173 | адрес фронта для ссылок в письмах, OIDC и CORS |
| `POSTGRES_*` | `itscout` | БД |
| `JWT_SECRET`, `COOKIE_SECURE` | dev-секрет, `false` | сессии |
| `EMAIL_BACKEND`, `EMAIL_VERIFICATION_REQUIRED` | `console`, `false` | отправка писем и обязательность подтверждения |
| `LLM_PROVIDER`, `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` | `none` | LLM для разбора текста и чек-листов; без него всё работает на словаре |
| `FSP_API_URL`, `FSP_API_KEY` | мок в compose | реестр ФСП |
| `FSP_OIDC_*` | Keycloak в compose | ФСП ID |
| `GRADE_CHANGE_COOLDOWN_DAYS`, `FAILED_GRADE_RETRY_DAYS`, `MAX_ACTIVE_INVITES_PER_NEED` | 90, 30, 15 | правила продукта |
