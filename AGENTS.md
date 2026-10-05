# AGENTS.md — ITScout

Инструкции для coding agents (Claude Code, Codex, Cursor и др.) в этом репозитории. `CLAUDE.md` только подключает этот файл: правила пишем здесь.

## Проект

**ITScout** (`itscout.ru`) — решение спецтрека ФСП хакатона «Лидеры цифровой трансформации 2026». Это платформа ИТ-подбора с обратной механикой: кандидат проходит тест и получает категорию «специализация × грейд», работодатель сам находит кандидата и отправляет приглашение с вилкой зарплаты.

**Сдача: 11.10.2026.** Сначала работающий демо-сценарий, потом всё остальное.

| Документ | Зачем |
|---|---|
| `docs/implementation.md` | **ТЗ на реализацию — главный источник истины**: механики, формулы, модель данных, API, план, задачи T01–T22 |
| `docs/ФСП спец. трек ТЗ.pdf` | исходное ТЗ организаторов |
| `docs/brandook/` | брендбук ФСП: логотипы SVG, шрифт JetBrains Mono, цвета |
| `docs/early/` | устаревшие ранние оценки, только для истории — **не использовать как требования** |

Перед задачей прочитай раздел `docs/implementation.md`, к которому она относится. Если код расходится с ТЗ на реализацию — скажи об этом, а не исправляй молча одно под другое.

## Git: обязательный цикл каждой задачи

Работаем прямо в `master`, без веток и PR (хакатон). Параллельно могут работать несколько агентов.

1. **Перед началом работы:**
   ```bash
   git pull --rebase --autostash
   ```
2. Делаешь задачу и прогоняешь проверки (см. «Готово, когда»).
3. **После выполнения** — коммит и пуш:
   ```bash
   git add <конкретные файлы>
   git commit -m "<область>: что сделано"
   git pull --rebase --autostash
   git push
   ```
4. **Если push отклонён:** снова `git pull --rebase`, разреши конфликты, прогони тесты затронутой части и повтори push.

Правила коммитов:
- Одна содержательная строка, без пунктов и абзацев. Служебные трейлеры инструмента (например, `Co-Authored-By`) допустимы. Области: `backend`, `frontend`, `testing`, `matching`, `content`, `fsp-mock`, `validation`, `infra`, `docs`. Пример: `testing: MST assembly with exposure control`.
- Один логический шаг — один коммит. Большая задача = несколько коммитов, каждый с зелёными тестами.
- Добавляй файлы явно. Не используй `git add -A` вслепую: в коммит не должны попасть `.env`, дампы, артефакты сборки.

Запрещено:
- `git push --force`, `git reset --hard` по чужим коммитам, переписывание истории `master`;
- `--no-verify`.

**Секреты не коммитить никогда.** Репозиторий приватный, но перед сдачей станет публичным вместе со всей историей. Ключи и пароли хранятся только в `.env` (в `.gitignore`) и в GitHub Secrets. Если секрет всё-таки попал в коммит — сразу скажи пользователю: ключ нужно перевыпустить.

**Git LFS:** `*.png`, `*.ttf`, `*.pdf`, `*.pptx` хранятся в LFS (`.gitattributes`). Для веба используй SVG и WOFF2. В CI checkout делается с `lfs: true`.

## Стек

| Часть | Технологии |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async) + psycopg 3, Alembic, Pydantic v2; numpy/scipy для IRT; менеджер пакетов `uv` |
| Frontend | React 19 + Vite + TypeScript (strict), React Router, TanStack Query, react-hook-form + zod, Tailwind + shadcn/ui, Recharts |
| Хранение и инфраструктура | PostgreSQL 16; Docker Compose + Caddy |
| LLM | Yandex AI Studio |
| Тесты | pytest, Playwright |

## Структура

```text
backend/app/core/            config, db, security, deps, errors, llm, mail
backend/app/modules/<name>/  router.py · service.py · models.py · schemas.py
backend/app/modules/testing/engine/   движок тестирования — чистый Python, без БД и FastAPI
backend/content/             YAML: справочники, blueprints, шаблоны заданий, демо-вакансии
backend/migrations/  seed/  tests/
fsp-mock/                    mock реестра ФСП (отдельный сервис)
frontend/src/api/            сгенерированный клиент — руками не править
validation/                  симуляция и отчёт валидации
e2e/                         Playwright: демо-сценарий §18 против прода
infra/                       compose, Caddyfile, keycloak realm, заглушка
```

## Команды

Цели `Makefile` — для Linux, WSL и CI. На Windows-машине разработчика `make` нет, а `uv` вызывается как `python -m uv` — используй прямые команды из скобок. Если меняешь или добавляешь цель — обнови таблицу.

| Действие | Команда |
|---|---|
| Поднять всё локально | `make up` (`docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d`) |
| Тесты backend | `make test` (`cd backend && uv run pytest`) |
| Линт и формат backend | `make lint` (`cd backend && uv run ruff check . ../validation && uv run ruff format --check . ../validation`) |
| Фронт: проверка и сборка | `cd frontend && npm run lint && npm run typecheck && npm run build` |
| Обновить OpenAPI и клиент | `make openapi` (выгрузить `openapi.json` → `npm run gen:api`) |
| Миграция | `cd backend && uv run alembic revision --autogenerate -m "..."` |
| Проверка миграции | `uv run alembic upgrade head && uv run alembic check` (нужен Postgres, см. ниже) |
| Демо-данные | `make reseed` |
| Валидация (отчёт в `docs/validation/`, ~7–8 мин) | `make validate` (`cd backend && uv run python ../validation/run.py`; размер и seed — `--size`, `--seed`) |
| Документация в PDF (`docs/ITScout-docs.pdf`; версии и эндпоинты генерируются) | `make docs-pdf` (`cd docs/pdf && npm ci && npm run build`; Chromium — `CHROMIUM_PATH`) |
| Нагрузочный тест (10/30/50 пользователей по 60 с, только чтение, нужен `DEMO_MODE=true`) | `make loadtest LOADTEST_URL=<адрес>` (`cd loadtest && uv run python run.py --base-url <адрес>`; уровни и длительность — `--users`, `--duration`) |
| e2e (демо-сценарий против прода) | `make e2e` (`cd e2e && npm ci && npx playwright install chromium && npx playwright test`; другой стенд — `E2E_BASE_URL=<адрес>`) |

## Правила кода

**Общие:**
- Идентификаторы — на английском. Тексты интерфейса и ошибок для пользователя — на русском.
- Комментарии — редко, только «почему». Обязательны там, где ТЗ требует пояснить сложное: формулы IRT, скоринг, matching, правила грейда. Там нужна одна строка со ссылкой на раздел, например `# см. docs/implementation.md §10.4`.
- Минимальное изменение, которое решает задачу. Без абстракций «на будущее» и без правок соседнего кода, не относящегося к задаче.
- Числа (веса, пороги, интервалы, лимиты) не зашиваются в код, а берутся из `content/*.yaml` или настроек (`core/config.py`, env).

**Backend:**
- Роутер тонкий: валидация, зависимости, вызов `service`. Бизнес-логика — в `service.py`. Модули вызывают чужие `service`, а не чужие модели.
- Ошибки — через доменные исключения, они превращаются в единый формат `{error: {code, message, details}}` (см. `docs/implementation.md §15`).
- У каждого эндпоинта есть `response_model`, `summary` и описанные коды ошибок — Swagger является частью сдачи.
- Аннотации типов везде. Формат и линт — `ruff`.
- Изменение моделей → миграция Alembic в том же коммите. После autogenerate просмотри файл миграции глазами.
- Enum-колонки — только через `enum_type()` из `app/core/types.py`: это VARCHAR, а ровно один CHECK на колонку добавляет `add_enum_checks()`. Встроенный CHECK у `sa.Enum` не включай: Alembic его дублирует.
- Новую модель импортируй в `app/models.py`, иначе Alembic её не увидит.
- `testing/engine` детерминирован по seed и не импортирует БД и FastAPI: его использует `validation/`.

**Frontend:**
- Типы API только из сгенерированного клиента (`openapi-typescript`), не описывать их руками.
- Серверное состояние — TanStack Query. Формы — react-hook-form + zod.
- Цвета и шрифты — только через токены темы, сделанные по брендбуку: `#402FFF` основной, `#EC1D35` точечный акцент, `#1B1C21` тёмный, `#EDEDED`/`#C8C9CA` серые, JetBrains Mono для заголовков и цифр, Inter для основного текста. Произвольные hex в компонентах запрещены.
- У каждого экрана должны быть состояния загрузки, пустого списка и ошибки.

**Контракт API:**
- Pydantic-схемы и роутеры — источник контракта. Поменял схему → в том же коммите `make openapi` и обновлённый клиент на фронте.
- Не меняй чужой контракт, если задача этого не требует.

## Инварианты продукта (нарушение — баг)

- Грейд и категорию определяет только тест, а не резюме и не LLM. LLM разбирает текст и оценивает открытые ответы по чек-листу, но **не выставляет score и не решает, кого показывать**.
- Score и объяснение выдачи считаются одним кодом из одних и тех же компонентов.
- Вилка от–до в рублях обязательна в потребности, вакансии и приглашении: проверка в схеме и CHECK в БД.
- Контакты кандидата не отдаются работодателю без записи в `contact_unlocks` (принятое приглашение или отклик кандидата). Это касается любых эндпоинтов, в том числе PDF.
- Кандидат видит только свои приглашения и отклики, работодатель — только свои потребности и приглашения. На каждое такое правило есть тест.
- Ключи ответов на тест никогда не уходят на фронт. Время ответа считает сервер.
- Профиль без истории ФСП полностью работоспособен; ФСП только добавляет к профилю и не штрафует.

## Готово, когда

1. `git pull --rebase` сделан до начала работы.
2. Тесты и линт затронутой части проходят. Для backend — новые тесты на новую логику: для формул — golden-кейсы, для доступа — тест «чужое → 403».
3. Если менялся контракт — обновлены `openapi.json` и клиент.
4. Если менялось поведение — обновлены `docs/implementation.md` и `docs/` (ТЗ на реализацию должно соответствовать коду).
5. Коммит и push сделаны.
6. Если менялось то, что видно в демо, — после деплоя проверено на проде: `curl https://itscout.ru/api/v1/health` и ручной проход изменённого места.

Если какой-то пункт выполнить нельзя — прямо напиши об этом в ответе пользователю.

## Сервер

- Прод: `ssh itscout` (root@94.103.87.151, Ubuntu 26.04, 4 vCPU, 7,25 ГБ RAM + своп 2 ГБ). Приложение — `/opt/itscout/app` (туда rsync'ает CI), секреты — `/opt/itscout/app/.env` (права 600, в git нет).
- Docker Hub с сервера работает только через зеркало `mirror.gcr.io` (настроено в `/etc/docker/daemon.json`).
- **Без SSH (облачные сессии):** операции с продом — через workflow `Server ops` на ключе деплоя из GitHub Secrets: `gh workflow run server-ops.yml -f action=status|logs|reseed|restart|swap|llm-check [-f service=backend] [-f lines=200]`, результат — `gh run watch <id>` и `gh run view <id> --log`. Произвольных команд там нет намеренно. После того как репозиторий станет публичным, логи Actions видны всем — `logs` запускай только при необходимости.
- Тесты с БД без доступа к серверу: локальный Postgres 16 в песочнице (`DATABASE_URL=postgresql+psycopg://...`), у каждой параллельной задачи своя база — тесты делают drop_all/create_all.
- Деплой — только через CI/CD или файлы из `infra/`. Ручные правки на сервере не делаем: следующий деплой их затрёт. Если без ручного вмешательства не обойтись — повтори его в `infra/` и в `docs/deploy.md`.
- Не выполнять на проде без подтверждения пользователя: удаление volume'ов и БД, `docker system prune`, изменение `ufw` и `sshd_config`.
- Демо-режим `DEMO_MODE=true` даёт `POST /admin/reseed` и сброс ограничений. Перед показом жюри — `make reseed`.

## Среда разработки

Машина разработчика — Windows с Git Bash и PowerShell, сервер — Linux. Docker Desktop локально может быть не запущен. Тогда для миграций и тестов с БД поднимай временный Postgres на сервере, доступный только через SSH-туннель:

```bash
ssh itscout 'docker run -d --rm --name itscout-devpg -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=dev -p 127.0.0.1:55432:5432 postgres:16-alpine'
ssh -N -L 55432:127.0.0.1:55432 itscout   # в фоне
DATABASE_URL=postgresql+psycopg://dev:dev@127.0.0.1:55432/dev python -m uv run alembic upgrade head
```

После работы останови контейнер: `ssh itscout docker stop itscout-devpg`. psycopg в async-режиме на Windows требует SelectorEventLoop: в `migrations/env.py` это уже учтено.

Окончания строк в репозитории — LF (`.gitattributes`). Пути в скриптах — с прямыми слешами. Shell-скрипты должны работать в Linux-контейнере.
