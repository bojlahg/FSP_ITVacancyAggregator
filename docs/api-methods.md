# API: описание ключевых методов

Здесь подробно описаны методы основного сценария: вход, потребность работодателя, подборка, приглашение, ответ кандидата и тест на грейд. Каждый метод описан отдельным блоком по одной схеме: назначение, импорт (параметры запроса), экспорт (параметры ответа), алгоритм и ошибки. Полный список методов — в [справочнике эндпоинтов](api-endpoints.md), полные схемы — в Swagger `/api/docs`, общие правила (префикс `/api/v1`, аутентификация, формат ошибки `{"error": {"code", "message", "details"}}`) — в [API](api.md). Примеры собраны на демо-данных; токены заменены на `eyJ…`.

**Содержание**

1. [Демо-вход](#1-демо-вход) — `POST /api/v1/auth/demo-login`
2. [Разбор потребности из текста](#2-разбор-потребности-из-текста) — `POST /api/v1/needs/parse`
3. [Создание потребности](#3-создание-потребности) — `POST /api/v1/needs`
4. [Подборка по потребности](#4-подборка-по-потребности) — `GET /api/v1/needs/{need_id}/recommendations`
5. [Приглашение кандидата](#5-приглашение-кандидата) — `POST /api/v1/invitations`
6. [Принятие приглашения кандидатом](#6-принятие-приглашения-кандидатом) — `POST /api/v1/invitations/{invitation_id}/accept`
7. [Отказ кандидата от приглашения](#7-отказ-кандидата-от-приглашения) — `POST /api/v1/invitations/{invitation_id}/decline`
8. [Старт попытки теста](#8-старт-попытки-теста) — `POST /api/v1/tests/attempts`
9. [Ответ на задание теста](#9-ответ-на-задание-теста) — `POST /api/v1/tests/attempts/{attempt_id}/answer`

**Общие ошибки авторизации** встречаются во всех методах, кроме демо-входа:

| Статус | Код | Текст |
| --- | --- | --- |
| `401` | `unauthorized` | «Требуется вход» — нет заголовка `Authorization`; «Токен недействителен или истёк»; «Аккаунт удалён»; для `X-API-Key` — «API-ключ недействителен или отозван» |
| `403` | `forbidden` | «Недостаточно прав» — роль не подходит к методу |
| `403` | `email_not_verified` | «Подтвердите почту: перейдите по ссылке из письма, отправленного при регистрации» — только при `EMAIL_VERIFICATION_REQUIRED=true` |
| `422` | `validation_error` | «Ошибка валидации данных»; в `details` — список `{loc, msg, type}` по каждому полю |

---

## 1. Демо-вход

### Назначение

Выдаёт сессию подготовленного демо-аккаунта кандидата или работодателя без пароля. Нужен для показа жюри и e2e-проверок. Метод доступен только при `DEMO_MODE=true`.

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/auth/demo-login` |
| Авторизация | не требуется |
| Формат данных | `application/json` |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `persona` | body | `string` | да | Демо-аккаунт: `candidate` или `employer` |

**Пример запроса:**

```http
POST /api/v1/auth/demo-login
Content-Type: application/json
```

```json
{
  "persona": "employer"
}
```

### Экспорт — параметры ответа

**Успешный статус:** `200 OK`. Кроме тела, ответ ставит refresh-токен в cookie `itscout_refresh` (`HttpOnly`, `SameSite=Lax`, путь `/api/v1/auth`, срок 30 дней).

| Параметр | Тип | Описание |
| --- | --- | --- |
| `access_token` | `string` | Access JWT. Передаётся в заголовке `Authorization: Bearer …` |
| `token_type` | `string` | Всегда `bearer` |
| `expires_in` | `integer` | Срок жизни access-токена в секундах, по умолчанию 900 (15 минут) |
| `user` | `object` | Пользователь (`UserOut`) |
| `user.id` | `integer` | id пользователя |
| `user.email` | `string` | Email демо-аккаунта |
| `user.role` | `string` | `candidate` или `employer` |
| `user.email_verified` | `boolean` | Почта подтверждена (у демо-аккаунтов всегда `true`) |
| `user.email_verification_required` | `boolean` | Включено ли обязательное подтверждение почты на платформе |
| `user.email_notifications` | `boolean` | Включены ли письма о приглашениях и откликах |
| `user.created_at` | `string` (date-time) | Дата создания аккаунта |

**Пример успешного ответа:**

```json
{
  "access_token": "eyJ…",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": 602,
    "email": "demo-employer@itscout.ru",
    "role": "employer",
    "email_verified": true,
    "email_verification_required": false,
    "email_notifications": true,
    "created_at": "2026-07-10T20:46:41Z"
  }
}
```

### Алгоритм работы метода

1. Проверить `DEMO_MODE`. Если он выключен, вернуть 404: метод ведёт себя так, будто его нет.
2. Проверить ограничение частоты: не больше `DEMO_LOGIN_RATE_LIMIT` (300) запросов за скользящее окно 60 секунд на пару «IP + путь». Счётчик хранится в таблице `rate_limit_hits` и фиксируется сразу.
3. Проверить тело запроса: `persona` должна быть `candidate` или `employer`.
4. Найти пользователя с адресом `DEMO_CANDIDATE_EMAIL` или `DEMO_EMPLOYER_EMAIL`. Обычно его создаёт сид. Если сида не было, создать пустой аккаунт с подтверждённой почтой и пустой профиль; у работодателя — с названием компании «Демо Банк».
5. Создать refresh-токен (в БД хранится только его хеш, срок 30 дней) и зафиксировать транзакцию.
6. Выпустить access JWT (`sub`, `role`, срок 15 минут), поставить cookie и вернуть `TokenResponse`.

**При ошибке:** если исчерпан лимит частоты, учитывается только сам запрос, сессия не создаётся. Ответ — в едином формате ошибки.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `404` | `DEMO_MODE` выключен | `not_found` — «Не найдено» |
| `422` | `persona` отсутствует или имеет другое значение | `validation_error` — «Ошибка валидации данных», в `details` — `["body", "persona"]` |
| `429` | Превышен лимит запросов с одного IP | `too_many_requests` — «Слишком много запросов, попробуйте позже» |

---

## 2. Разбор потребности из текста

### Назначение

Превращает свободный текст потребности или вакансии в черновик формы: специализация, грейд, обязательные и желательные навыки, отрасль, формат, город, вилка. Сначала текст разбирается детерминированно по словарю. Затем LLM дополняет только пустые поля значениями из справочников. Метод ничего не сохраняет: работодатель правит черновик и создаёт потребность методом `POST /needs`.

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/needs/parse` |
| Авторизация | роль `employer`: `Authorization: Bearer <JWT>` или `X-API-Key: itsk_…` (ATS) |
| Формат данных | `application/json` |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `raw_text` | body | `string` | да | Текст потребности или вакансии, от 20 до 20 000 символов |

**Пример запроса:**

```http
POST /api/v1/needs/parse
Authorization: Bearer eyJ…
Content-Type: application/json
```

```json
{
  "raw_text": "Middle Python-разработчик (Backend) в платёжный сервис\nМы — финтех-команда, делаем платёжную платформу для банков.\nТребования: Python от 3 лет, FastAPI, PostgreSQL, Kafka, Docker.\nБудет плюсом: Kubernetes, ClickHouse.\nУсловия: удалённая работа, зарплата от 250 000 до 300 000 ₽ на руки."
}
```

### Экспорт — параметры ответа

**Успешный статус:** `200 OK`.

| Параметр | Тип | Описание |
| --- | --- | --- |
| `parser` | `string` | `dict` — всё нашёл словарь; `llm` — LLM дополнил хотя бы одно поле |
| `draft` | `object` | Черновик формы (`NeedDraft`); любое поле может быть пустым |
| `draft.title` | `string \| null` | Заголовок, собранный из грейда и специализации, например «Middle Backend-разработчик» |
| `draft.specialization` | `string \| null` | slug специализации из справочника (`backend`, `frontend`, `qa`, `devops`…) |
| `draft.grade` | `string \| null` | `intern`, `junior`, `middle`, `senior` |
| `draft.required_skills` | `array<string>` | id обязательных навыков из онтологии |
| `draft.optional_skills` | `array<string>` | id желательных навыков (блок «будет плюсом») |
| `draft.industry` | `string \| null` | slug отрасли |
| `draft.team_description` | `string \| null` | Описание команды, найденное в тексте |
| `draft.work_format` | `string \| null` | `office`, `hybrid`, `remote` |
| `draft.city` | `string \| null` | Город |
| `draft.salary_from`, `draft.salary_to` | `integer \| null` | Границы вилки в рублях; словарь главнее LLM |
| `unmapped_terms` | `array<string>` | Термины, которых нет в справочнике навыков («Не распознали: …») |
| `text_issues` | `array<object>` | Запрещённые требования в тексте: `rule`, `severity` (`block` мешает публикации, `warn` — подсказка), `label`, `message`, `fragment` |

**Пример успешного ответа:**

```json
{
  "parser": "dict",
  "draft": {
    "title": "Middle Backend-разработчик",
    "specialization": "backend",
    "grade": "middle",
    "required_skills": ["python", "fastapi", "postgresql", "kafka", "docker"],
    "optional_skills": ["kubernetes", "clickhouse"],
    "industry": "fintech",
    "team_description": "Мы — финтех-команда, делаем платёжную платформу для банков.",
    "work_format": "remote",
    "city": null,
    "salary_from": 250000,
    "salary_to": 300000
  },
  "unmapped_terms": [],
  "text_issues": []
}
```

### Алгоритм работы метода

1. Проверить роль работодателя (JWT или API-ключ) и длину `raw_text`.
2. Разобрать текст словарём (`parse_dict`): навыки по алиасам с учётом контекста и морфологии, деление на обязательные и желательные по секциям текста, специализация, грейд, вилка, формат, город, отрасль, описание команды, нераспознанные термины.
3. Вызвать LLM (Yandex AI Studio) со схемой ответа и допустимыми значениями справочников. Вызов пропускается, и LLM возвращает `null`, если LLM выключен, ответ есть в кэше, исчерпан часовой лимит пользователя или дневной бюджет токенов, произошла ошибка сети или ответ не является JSON.
4. Слить результаты (`merge_llm`). LLM заполняет только пустые поля и только значениями из справочников. Неизвестные навыки уходят в `unmapped_terms`. Вилку LLM ставит, только если словарь не нашёл ни одной границы.
5. Пересобрать заголовок по итоговым специализации и грейду и проверить текст правилами `content/need_text_rules.yaml`.
6. Вернуть черновик. В БД ничего не записывается.

**При ошибке:** сбой или недоступность LLM ошибкой не считаются: возвращается словарный разбор с `parser = "dict"`. Ошибки возможны только из-за доступа и валидации.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `401` | Нет токена, токен истёк, неверный API-ключ | `unauthorized` — «Требуется вход» / «Токен недействителен или истёк» / «API-ключ недействителен или отозван» |
| `403` | Роль не `employer` | `forbidden` — «Недостаточно прав» |
| `422` | `raw_text` короче 20 или длиннее 20 000 символов | `validation_error` — «Ошибка валидации данных», `details[0].msg` — «Слишком короткое значение» / «Слишком длинное значение» |

---

## 3. Создание потребности

### Назначение

Сохраняет потребность работодателя: категорию «специализация × грейд», стек, условия и обязательную вилку. Вокруг потребности строятся подборка, шорт-лист, приглашения, а после публикации — вакансия и отклики. Создаётся версия 1. Последующие правки через `PUT /needs/{need_id}` создают новые версии.

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/needs` |
| Авторизация | роль `employer`: `Authorization: Bearer <JWT>` или `X-API-Key: itsk_…` |
| Формат данных | `application/json` |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `title` | body | `string` | да | Название, от 1 до 200 символов |
| `specialization` | body | `string` | да | slug специализации из `GET /catalog/specializations` |
| `grade` | body | `string` | да | `intern`, `junior`, `middle`, `senior` |
| `salary_from` | body | `integer` | да | Нижняя граница вилки, ₽ на руки; больше 0, не больше 2 147 483 647 |
| `salary_to` | body | `integer` | да | Верхняя граница вилки, ₽ на руки; не меньше `salary_from` |
| `raw_text` | body | `string \| null` | нет | Исходный текст потребности, до 20 000 символов |
| `required_skills` | body | `array<string>` | нет | id обязательных навыков из `GET /catalog/skills`; по умолчанию `[]` |
| `optional_skills` | body | `array<string>` | нет | id желательных навыков; не должны пересекаться с обязательными |
| `industry` | body | `string \| null` | нет | slug отрасли из `GET /catalog/industries` |
| `team_description` | body | `string \| null` | нет | Описание команды, до 4000 символов |
| `work_format` | body | `string \| null` | нет | `office`, `hybrid`, `remote` |
| `city` | body | `string \| null` | нет | Город, до 100 символов (учитывается в условиях подбора, если формат не `remote`) |

**Пример запроса:**

```http
POST /api/v1/needs
Authorization: Bearer eyJ…
Content-Type: application/json
```

```json
{
  "title": "Middle Python-разработчик",
  "raw_text": "Ищем Middle Python-разработчика в финтех",
  "specialization": "backend",
  "grade": "middle",
  "required_skills": ["python", "postgresql"],
  "optional_skills": ["kafka"],
  "industry": "fintech",
  "work_format": "remote",
  "salary_from": 250000,
  "salary_to": 300000
}
```

### Экспорт — параметры ответа

**Успешный статус:** `201 Created`. Тело — `NeedOut`: все поля запроса плюс служебные.

| Параметр | Тип | Описание |
| --- | --- | --- |
| `id` | `integer` | id потребности (этой версии) |
| `version` | `integer` | Номер версии, у новой — `1` |
| `parent_id` | `integer \| null` | id предыдущей версии, у новой — `null` |
| `status` | `string` | `draft`, `active`, `closed`; новая — `active` |
| `published` | `boolean` | Опубликована ли как вакансия; новая — `false` |
| `published_at` | `string \| null` (date-time) | Когда опубликована |
| `category` | `object` | `specialization`, `grade`, `label` (например «Backend · Middle») |
| `stats` | `object` | `shortlisted`, `invitations_active`, `invitations_total`, `invitations_limit` (лимит активных приглашений, по умолчанию 15), `applications` |
| `text_issues` | `array<object>` | Запрещённые требования в `title`, `raw_text`, `team_description` (как в разборе) |
| `created_at` | `string` (date-time) | Дата создания |
| `title` … `city`, `salary_from`, `salary_to` | — | Сохранённые значения полей запроса |

**Пример успешного ответа:**

```json
{
  "id": 12,
  "version": 1,
  "parent_id": null,
  "status": "active",
  "published": false,
  "published_at": null,
  "title": "Middle Python-разработчик",
  "raw_text": "Ищем Middle Python-разработчика в финтех",
  "specialization": "backend",
  "grade": "middle",
  "required_skills": ["python", "postgresql"],
  "optional_skills": ["kafka"],
  "industry": "fintech",
  "team_description": null,
  "work_format": "remote",
  "city": null,
  "salary_from": 250000,
  "salary_to": 300000,
  "category": {"specialization": "backend", "grade": "middle", "label": "Backend · Middle"},
  "stats": {
    "shortlisted": 0,
    "invitations_active": 0,
    "invitations_total": 0,
    "invitations_limit": 15,
    "applications": 0
  },
  "text_issues": [],
  "created_at": "2026-10-09T10:15:00Z"
}
```

### Алгоритм работы метода

1. Проверить роль работодателя (JWT или API-ключ).
2. Проверить схему: обязательные поля, длины, перечисления и вилку. `salary_from` и `salary_to` больше 0, `salary_from ≤ salary_to`.
3. Сверить значения со справочниками (`validate_fields`): известная специализация, каждый навык есть в онтологии, обязательные и желательные навыки не пересекаются, известная отрасль. Все замечания собираются в один ответ 422.
4. Найти профиль работодателя текущего пользователя.
5. Создать строку `hiring_needs`: `version = 1`, `status = active`, `published = false`. Зафиксировать транзакцию. Вилку дополнительно защищает CHECK `salary_from > 0 AND salary_from <= salary_to`.
6. Посчитать `stats` и `text_issues` и вернуть `NeedOut`. Запрещённые требования в тексте на этом шаге только показываются: блокируется публикация (`POST /needs/{id}/publish`), а не создание.

**При ошибке:** до шага 5 в БД ничего не пишется. Ответ — в едином формате ошибки.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `401` | Нет токена или неверный API-ключ | `unauthorized` — «Требуется вход» / «API-ключ недействителен или отозван» |
| `403` | Роль не `employer` или нет профиля работодателя | `forbidden` — «Недостаточно прав» / «Профиль работодателя не найден» |
| `422` | Нет вилки, неверные типы или длины | `validation_error` — «Ошибка валидации данных», `details[].msg` — «Обязательное поле», «Слишком длинное значение» и т. п. |
| `422` | `salary_from > salary_to` | `validation_error`, `details[].msg` — «salary_from не может быть больше salary_to» |
| `422` | Значения вне справочников | `validation_error`, `details[]` с `type`: `unknown_specialization` («Неизвестная специализация»), `unknown_skill` («Неизвестный навык: <id>»), `unknown_industry` («Неизвестная отрасль»), `value_error` («Навык не может быть одновременно обязательным и желательным») |

---

## 4. Подборка по потребности

### Назначение

Главный экран работодателя. Метод возвращает рекомендованные категории «специализация × грейд» с покрытием вилки и кандидатов с score 0–100, компонентами score и объяснением. Объяснение собирается тем же кодом и из тех же компонентов, что и score. Отдельными блоками идут кандидаты, не прошедшие жёсткие условия (с причиной), шорт-лист и кандидаты без подтверждённого грейда. Контакты кандидатов в выдачу не входят.

| Свойство | Значение |
| --- | --- |
| Метод и путь | `GET /api/v1/needs/{need_id}/recommendations` |
| Авторизация | роль `employer`, только своя потребность: `Authorization: Bearer <JWT>` или `X-API-Key: itsk_…` |
| Формат данных | `application/json` (ответ) |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `need_id` | path | `integer` | да | id потребности (любой версии своей потребности) |
| `grade` | query | `string` | нет | Оставить только кандидатов этого грейда: `intern`, `junior`, `middle`, `senior` |
| `has_fsp` | query | `boolean` | нет | `true` — только с историей ФСП, `false` — только без неё; не задан — все |
| `verified_only` | query | `boolean` | нет | По умолчанию `false`. `true` — хотя бы один обязательный навык потребности проверен тестом |
| `salary_max` | query | `integer` | нет | Ожидания кандидата не выше этой суммы, ₽; от 1 до 2 147 483 647. Кандидаты со скрытыми ожиданиями проходят |
| `work_format` | query | `string` | нет | `office`, `hybrid`, `remote`: кандидат готов к этому формату (если указал форматы) |
| `city` | query | `string` | нет | Город кандидата совпадает или кандидат готов к переезду. Справочник — `GET /talent/cities` |
| `fresh_days` | query | `integer` | нет | Активность или результат теста не старше N дней |
| `apply_hard_filters` | query | `boolean` | нет | По умолчанию `true`: не прошедшие жёсткие условия потребности уходят в `out_of_filter`. `false` — остаются в общей выдаче |
| `group_by` | query | `string` | нет | `category` (по умолчанию): сначала точная категория, затем соседний грейд, смежная специализация и оба отличия; внутри — по score. `none` — единый список по score |
| `limit` | query | `integer` | нет | Сколько кандидатов вернуть в `candidates` и `unconfirmed`, от 1 до 200. По умолчанию — `recommendations.default_limit` из `content/matching.yaml` (50) |

**Пример запроса:**

```http
GET /api/v1/needs/1/recommendations?work_format=remote&limit=2
Authorization: Bearer eyJ…
```

### Экспорт — параметры ответа

**Успешный статус:** `200 OK`. Ниже описаны поля верхнего уровня и ключевые вложенные объекты. Полная схема `RecommendationsOut` — в Swagger.

| Параметр | Тип | Описание |
| --- | --- | --- |
| `need_id`, `need_version` | `integer` | Потребность и версия, по которой посчитана выдача |
| `categories` | `array<object>` | Рекомендованные категории (`CategoryRecommendation`): `category`, `fit` (`exact`, `adjacent_grade`, `adjacent_specialization`, `adjacent_both`), `candidates_count`, `with_fsp_count`, `salary_coverage` (доля кандидатов категории, чьи ожидания укладываются в `salary_to`; `null` — нет данных), `reason` |
| `candidates` | `array<object>` | Кандидаты с подтверждённой категорией (`CandidateMatch`), не больше `limit` |
| `total` | `integer` | Сколько всего кандидатов попало в `candidates` до обрезки по `limit` |
| `out_of_filter` | `array<object>` | Не прошли жёсткие условия потребности (не больше 20); причина — в `out_of_filter_reasons` |
| `shortlist` | `array<object>` | Закреплённые в шорт-листе кандидаты (`CandidateMatch`) — показываются независимо от фильтров |
| `shortlist_outside` | `array<object>` | Закреплены, но после правки потребности вне её категорий: карточка `CandidateBrief` без score |
| `unconfirmed` | `array<object>` | Специализация потребности, но грейд тестом не подтверждён: отдельный блок после всех подтверждённых. Пуст при `SHOW_UNCONFIRMED_CANDIDATES=false` |
| `unconfirmed_total` | `integer` | Размер блока `unconfirmed` до обрезки |
| `CandidateMatch.candidate` | `object` | Обезличенная карточка `CandidateBrief`: `id`, `display_name` (имя и первая буква фамилии), `category`, `specialization`, `grade_confirmed`, `percentile`, `vps` (сила профиля 0..1), `city`, `relocation`, `work_formats`, `salary_min` (`null`, если скрыто), `fsp` (`has_fsp`, `max_rank`, `achievements_count`), `verified_skills`, `declared_skills`, `last_activity_at`. Контактов нет |
| `CandidateMatch.score` | `integer` | 0–100: `round(100 × Σ weight·component)`; веса — `content/matching.yaml` (§8.3) |
| `CandidateMatch.components` | `object` | Компоненты score, каждый 0..1: `skills`, `strength`, `category`, `fsp`, `fresh`, `conditions` |
| `CandidateMatch.explanation.lines` | `array<object>` | Строки объяснения: `kind` (`positive`, `warning`, `neutral`), `source` (`category`, `test`, `skills`, `fsp`, `freshness`, `conditions`, `profile`), `text` |
| `CandidateMatch.acceptance` | `object \| null` | Вероятность, что кандидат примет приглашение: `probability`, `level` (`high`, `medium`, `low`), `text`, `affects_score` |
| `CandidateMatch.shortlisted` | `boolean` | Кандидат в шорт-листе этой потребности |
| `CandidateMatch.out_of_filter_reasons` | `array<string>` | Причины жёсткого фильтра, например «Не подходит формат работы» |
| `CandidateMatch.invitation_status` | `string \| null` | Статус последнего приглашения от вашей компании: `sent`, `viewed`, `accepted`, `declined`, `expired`, `withdrawn` |

**Пример успешного ответа** (реальный ответ демо-стенда, массивы сокращены до одного элемента):

```json
{
  "need_id": 1,
  "need_version": 1,
  "categories": [
    {
      "category": {"specialization": "backend", "grade": "middle", "label": "Backend · Middle"},
      "fit": "exact",
      "candidates_count": 65,
      "with_fsp_count": 30,
      "salary_coverage": 0.846,
      "reason": "Точное совпадение · ваша вилка покрывает ожидания 85%"
    }
  ],
  "candidates": [
    {
      "candidate": {
        "id": 4,
        "display_name": "Ульяна М.",
        "category": {"specialization": "backend", "grade": "middle", "label": "Backend · Middle"},
        "specialization": "backend",
        "grade_confirmed": true,
        "percentile": 0.6987,
        "vps": 0.715,
        "city": "Москва",
        "relocation": false,
        "work_formats": ["remote", "hybrid"],
        "salary_min": 170000,
        "fsp": {"has_fsp": true, "max_rank": "II", "achievements_count": 3},
        "verified_skills": ["HTTP", "PostgreSQL", "REST API", "SQL", "System Design", "Алгоритмы"],
        "declared_skills": ["ASP.NET Core", "C#", "Git", "Microsoft SQL Server", "RabbitMQ"],
        "last_activity_at": "2026-09-26T23:46:41Z"
      },
      "score": 67,
      "components": {
        "skills": 0.3472,
        "strength": 0.8497,
        "category": 1.0,
        "fsp": 0.7073,
        "fresh": 0.9121,
        "conditions": 1.0
      },
      "explanation": {
        "lines": [
          {"kind": "positive", "source": "category", "text": "Категория совпадает: Backend · Middle, подтверждено тестом (70-й перцентиль)"},
          {"kind": "positive", "source": "test", "text": "PostgreSQL — проверено тестом: 2 из 2 заданий"},
          {"kind": "neutral", "source": "skills", "text": "Apache Kafka — нет, есть близкий RabbitMQ (зачтено 25%)"},
          {"kind": "neutral", "source": "freshness", "text": "Свежий результат: 11 дн. назад"},
          {"kind": "warning", "source": "skills", "text": "Python — нет данных"}
        ]
      },
      "acceptance": {
        "probability": 0.948,
        "level": "high",
        "text": "Вероятность, что кандидат примет приглашение: высокая — вся вилка не ниже ожиданий, формат работы совпадает",
        "affects_score": false
      },
      "shortlisted": true,
      "out_of_filter_reasons": [],
      "invitation_status": null
    }
  ],
  "out_of_filter": [],
  "shortlist": [],
  "shortlist_outside": [],
  "total": 27,
  "unconfirmed": [],
  "unconfirmed_total": 2
}
```

### Алгоритм работы метода

1. Проверить роль работодателя и параметры запроса.
2. Найти потребность. Если её нет или она принадлежит другой компании, вернуть 404: чужая потребность неотличима от несуществующей.
3. Собрать пул кандидатов из индекса выдачи `candidate_search_index`. Берутся видимые кандидаты, которые не скрыли себя от этой компании, со специализацией потребности или смежной и с грейдом потребности ±1. Если `SHOW_UNCONFIRMED_CANDIDATES=true`, добавляются кандидаты без подтверждённого грейда.
4. Для каждого кандидата посчитать `scoring.evaluate`: компоненты, score, строки объяснения, причины жёстких фильтров и вероятность принятия (§8.3–8.4). Посчитанный пул кэшируется в памяти процесса на `RECOMMENDATIONS_CACHE_SECONDS` (60 с). Ключ кэша — потребность, её версия, работодатель и отметка изменения индекса, так что правка потребности или пересчёт индекса сбрасывают кэш.
5. Применить фильтры из query (`grade`, `has_fsp`, `verified_only`, `salary_max`, `work_format`, `city`, `fresh_days`). Не прошедшие фильтры не попадают ни в один блок, кроме `shortlist`.
6. Если `apply_hard_filters=true`, отправить в `out_of_filter` кандидатов с жёсткими условиями потребности: ожидания выше `salary_to` больше чем на `salary_tolerance` (30 %), не подходит формат, другой город без готовности к переезду. Остальных разложить на `candidates` (грейд подтверждён) и `unconfirmed`.
7. Отсортировать. При `group_by=category` сначала по типу совпадения категории, затем по score; при `none` — сразу по score. При равном score выше кандидат с большим компонентом ФСП, затем более свежий. Кандидаты без подтверждённого грейда всегда идут после подтверждённых.
8. Добавить шорт-лист, `shortlist_outside`, статусы последних приглашений компании и карточки категорий с покрытием вилки. Обрезать `candidates` и `unconfirmed` по `limit`, `out_of_filter` — до 20.
9. Вернуть `RecommendationsOut`. Метод только читает данные: в БД ничего не пишется.

**При ошибке:** изменений нет. Ответ — в едином формате ошибки.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `401` | Нет токена или неверный API-ключ | `unauthorized` — «Требуется вход» / «API-ключ недействителен или отозван» |
| `403` | Роль не `employer` или нет профиля работодателя | `forbidden` — «Недостаточно прав» / «Профиль работодателя не найден» |
| `404` | Потребности нет или она чужая | `not_found` — «Потребность не найдена» |
| `422` | Недопустимое значение фильтра (`grade`, `work_format`, `group_by`), `limit` вне 1–200, `salary_max ≤ 0` | `validation_error` — «Ошибка валидации данных», например `{"loc": ["query", "limit"], "msg": "Значение слишком маленькое", "type": "greater_than_equal"}` |

---

## 5. Приглашение кандидата

### Назначение

Работодатель приглашает найденного кандидата: название и описание предложения, обязательная вилка и способ связи с рекрутером. Кандидат видит приглашение во входящих вместе с блоком «Почему вы» — снимком объяснения на момент отправки. Контакты кандидата на этом шаге не раскрываются.

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/invitations` |
| Авторизация | роль `employer`: `Authorization: Bearer <JWT>` или `X-API-Key: itsk_…`; в профиле компании должно быть заполнено название |
| Формат данных | `application/json` |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `candidate_id` | body | `integer` | да | id кандидата из подборки или поиска |
| `need_id` | body | `integer \| null` | нет | Потребность или вакансия. Без неё приглашение не учитывается в лимите потребности, а «Почему вы» считается по категории кандидата |
| `title` | body | `string` | да | Название предложения, от 1 до 200 символов |
| `message` | body | `string` | да | Описание предложения, от 1 до 4000 символов |
| `salary_from` | body | `integer` | да | Нижняя граница вилки, ₽ на руки; больше 0, не больше 2 147 483 647 |
| `salary_to` | body | `integer` | да | Верхняя граница вилки, ₽ на руки; не меньше `salary_from` |
| `contact_method` | body | `object` | да | Как кандидату связаться с работодателем |
| `contact_method.name` | body | `string` | да | Контактное лицо, от 1 до 200 символов |
| `contact_method.email` | body | `string \| null` | нет* | Email рекрутера |
| `contact_method.telegram` | body | `string \| null` | нет* | Telegram, до 64 символов |
| `contact_method.phone` | body | `string \| null` | нет* | Телефон, до 32 символов |
| `expires_in_days` | body | `integer \| null` | нет | Срок действия, от 1 до 60 дней; по умолчанию `INVITATION_TTL_DAYS` (14) |

\* Нужен хотя бы один канал: `email`, `telegram` или `phone`.

**Пример запроса:**

```http
POST /api/v1/invitations
Authorization: Bearer eyJ…
Content-Type: application/json
```

```json
{
  "candidate_id": 57,
  "need_id": 12,
  "title": "Backend в платёжную команду",
  "message": "Пишем платёжный шлюз на Python",
  "salary_from": 250000,
  "salary_to": 300000,
  "contact_method": {"name": "Ольга, HR", "telegram": "@olga_hr"}
}
```

### Экспорт — параметры ответа

**Успешный статус:** `201 Created`. Тело — `InvitationForEmployer`.

| Параметр | Тип | Описание |
| --- | --- | --- |
| `id` | `integer` | id приглашения |
| `candidate` | `object` | Обезличенная карточка кандидата `CandidateBrief`, как в подборке |
| `need_id` | `integer \| null` | Последняя версия потребности, к которой привязано приглашение |
| `title`, `message` | `string` | Текст предложения |
| `salary_from`, `salary_to` | `integer` | Вилка, ₽ |
| `contact_method` | `object` | Способ связи с рекрутером, как в запросе |
| `match_snapshot` | `object \| null` | Снимок объяснения (`lines`) на момент отправки — его же кандидат видит как «Почему вы» |
| `status` | `string` | `sent` у нового приглашения; дальше `viewed`, `accepted`, `declined`, `expired`, `withdrawn` |
| `decline_reason`, `decline_comment` | `string \| null` | Причина и комментарий отказа; у нового — `null` |
| `contacts` | `object \| null` | Контакты кандидата (`full_name`, `email`, `phone`, `telegram`) — только если есть запись в `contact_unlocks`; у нового приглашения обычно `null` |
| `created_at`, `viewed_at`, `responded_at`, `expires_at` | `string` (date-time) | Даты жизненного цикла; `viewed_at` и `responded_at` у нового — `null` |

**Пример успешного ответа:**

```json
{
  "id": 31,
  "candidate": {
    "id": 57,
    "display_name": "Анна К.",
    "category": {"specialization": "backend", "grade": "middle", "label": "Backend · Middle"},
    "specialization": "backend",
    "grade_confirmed": true,
    "percentile": 0.7,
    "vps": 0.62,
    "city": "Москва",
    "relocation": false,
    "work_formats": ["remote"],
    "salary_min": 260000,
    "fsp": {"has_fsp": false, "max_rank": null, "achievements_count": 0},
    "verified_skills": [],
    "declared_skills": [],
    "last_activity_at": "2026-10-09T10:00:00Z"
  },
  "need_id": 12,
  "title": "Backend в платёжную команду",
  "message": "Пишем платёжный шлюз на Python",
  "salary_from": 250000,
  "salary_to": 300000,
  "contact_method": {"name": "Ольга, HR", "email": null, "telegram": "@olga_hr", "phone": null},
  "match_snapshot": {
    "lines": [
      {"kind": "positive", "source": "category", "text": "Категория совпадает: Backend · Middle, подтверждено тестом (70-й перцентиль)"}
    ]
  },
  "status": "sent",
  "decline_reason": null,
  "decline_comment": null,
  "contacts": null,
  "created_at": "2026-10-09T10:20:00Z",
  "viewed_at": null,
  "responded_at": null,
  "expires_at": "2026-10-23T10:20:00Z"
}
```

### Алгоритм работы метода

1. Проверить роль работодателя и тело запроса: вилку, длины полей и хотя бы один канал в `contact_method`.
2. Найти профиль компании и проверить, что заполнено название. Иначе вернуть 409 `company_profile_required`.
3. Проверить, что кандидат существует и доступен компании: виден ей в поиске или уже раскрыл ей контакты. Иначе вернуть 404: невидимый кандидат неотличим от несуществующего.
4. Общему демо-работодателю (`demo-login`) разрешено приглашать только демо-кандидатов из сида. Иначе вернуть 403 `demo_account`.
5. Заблокировать строку компании (`SELECT … FOR UPDATE`): отправки одной компании идут последовательно, и параллельные запросы не обходят проверки. Перевести просроченные приглашения в `expired`.
6. Если у кандидата уже есть активное (`sent` или `viewed`) приглашение от этой компании, вернуть 409 `already_invited`.
7. Если задан `need_id`, проверить, что потребность своя, и перейти на её последнюю версию. Посчитать активные приглашения по всей цепочке версий: при достижении `MAX_ACTIVE_INVITES_PER_NEED` (15) вернуть 409 `invitation_limit`.
8. Посчитать снимок «Почему вы» тем же `scoring.evaluate`, что и подборку. Если потребности нет или кандидат вне её категорий, снимок считается по категории кандидата.
9. Создать строку `invitations` со статусом `sent` и `expires_at = now + expires_in_days` и зафиксировать транзакцию. Вилку дополнительно защищает CHECK в БД.
10. После ответа поставить в фоновую отправку письмо кандидату о новом приглашении, если у него включены уведомления (§8.9). Вернуть `InvitationForEmployer`.

**При ошибке:** транзакция откатывается, приглашение не создаётся и письмо не отправляется. Ответ — в едином формате ошибки.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `401` | Нет токена или неверный API-ключ | `unauthorized` — «Требуется вход» / «API-ключ недействителен или отозван» |
| `403` | Роль не `employer` или нет профиля работодателя | `forbidden` — «Недостаточно прав» / «Профиль работодателя не найден» |
| `403` | Демо-работодатель приглашает не демо-кандидата | `demo_account` — «Демо-компания работает только с демо-кандидатами — зарегистрируйте свою компанию» |
| `404` | Кандидата нет или он не виден компании | `not_found` — «Кандидат не найден» |
| `404` | `need_id` чужой или не существует | `not_found` — «Потребность не найдена» |
| `409` | Не заполнено название компании | `company_profile_required` — «Заполните название компании в профиле перед отправкой приглашения» |
| `409` | Уже есть активное приглашение этому кандидату | `already_invited` — «У кандидата уже есть активное приглашение от вашей компании» |
| `409` | Достигнут лимит активных приглашений по потребности | `invitation_limit` — «По этой потребности уже максимум активных приглашений — дождитесь ответов» |
| `422` | Нет вилки или `salary_from > salary_to`, пустые `title`/`message`, нет канала связи, `expires_in_days` вне 1–60 | `validation_error` — «Ошибка валидации данных»; например, `details[].msg` — «salary_from не может быть больше salary_to» или «Нужен хотя бы один способ связи: email, telegram или телефон» |

---

## 6. Принятие приглашения кандидатом

### Назначение

Кандидат принимает приглашение. Это одна из двух точек, после которых работодатель видит контакты кандидата; вторая — отклик кандидата на вакансию. Принятие создаёт запись в `contact_unlocks`, а кандидат в ответ получает контакт рекрутера (`contact_method`).

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/invitations/{invitation_id}/accept` |
| Авторизация | роль `candidate`, `Authorization: Bearer <JWT>`; только своё приглашение |
| Формат данных | `application/json` (ответ); тела запроса нет |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `invitation_id` | path | `integer` | да | id приглашения из `GET /candidates/me/invitations` |

**Пример запроса:**

```http
POST /api/v1/invitations/31/accept
Authorization: Bearer eyJ…
```

### Экспорт — параметры ответа

**Успешный статус:** `200 OK`. Тело — `InvitationForCandidate`.

| Параметр | Тип | Описание |
| --- | --- | --- |
| `id` | `integer` | id приглашения |
| `company` | `object` | Компания (`CompanyPublic`): `id`, `company_name`, `industry`, `website`, `description`, `reputation` (`invitations_sent`, `acceptance_rate`, `withdrawn_rate`, `median_response_hours`) |
| `title`, `message` | `string` | Текст предложения |
| `salary_from`, `salary_to` | `integer` | Вилка, ₽ |
| `contact_method` | `object \| null` | Контакт рекрутера (`name`, `email`, `telegram`, `phone`). Заполнен только при статусе `accepted` |
| `why_you` | `object` | «Почему вы»: `lines` — тот же снимок, что видит работодатель в `match_snapshot` |
| `salary_market` | `object \| null` | Вилка против ожиданий категории кандидата: `verdict` (`ok`, `below_market`, `suspicious_high`, `unknown`), `coverage`, `median_expectation`, `message` |
| `status` | `string` | После успешного вызова — `accepted` |
| `created_at`, `viewed_at`, `responded_at`, `expires_at` | `string` (date-time) | Даты; `viewed_at` и `responded_at` заполнены |
| `warnings` | `array<object>` | Признаки мошенничества в тексте приглашения (`rule`, `label`, `message`, `fragment`) — только предупреждение |
| `report` | `object \| null` | Жалоба кандидата на приглашение, если подана |

**Пример успешного ответа:**

```json
{
  "id": 31,
  "company": {
    "id": 3,
    "company_name": "Тестовая компания",
    "industry": "fintech",
    "website": null,
    "description": null,
    "reputation": {
      "invitations_sent": 6,
      "acceptance_rate": 0.5,
      "withdrawn_rate": 0.0,
      "median_response_hours": 20.0
    }
  },
  "title": "Backend в платёжную команду",
  "message": "Пишем платёжный шлюз на Python",
  "salary_from": 250000,
  "salary_to": 300000,
  "contact_method": {"name": "Ольга, HR", "email": null, "telegram": "@olga_hr", "phone": null},
  "why_you": {
    "lines": [
      {"kind": "positive", "source": "category", "text": "Категория совпадает: Backend · Middle, подтверждено тестом (70-й перцентиль)"}
    ]
  },
  "salary_market": {
    "verdict": "ok",
    "coverage": 0.85,
    "median_expectation": 240000,
    "message": "Вилка в рынке: покрывает ожидания 85% кандидатов вашей категории."
  },
  "status": "accepted",
  "created_at": "2026-10-09T10:20:00Z",
  "viewed_at": "2026-10-09T11:02:00Z",
  "responded_at": "2026-10-09T11:05:00Z",
  "expires_at": "2026-10-23T10:20:00Z",
  "warnings": [],
  "report": null
}
```

### Алгоритм работы метода

1. Проверить роль кандидата и найти его профиль.
2. Перевести просроченные приглашения в `expired`, затем прочитать приглашение с блокировкой строки (`FOR UPDATE`): принятие и отзыв одного приглашения не могут пройти оба. Если приглашение не найдено или адресовано другому кандидату, вернуть 404.
3. Проверить статус: принять можно только `sent` или `viewed`. Иначе вернуть 409 `invitation_closed`; сюда относятся и уже принятые, отклонённые, отозванные и просроченные.
4. Установить `status = accepted`, `responded_at = now`; если `viewed_at` пуст, заполнить и его.
5. Раскрыть контакты (`unlock_contacts`). Если записи `contact_unlocks` для пары «компания — кандидат» ещё нет, добавить её с `source = invitation` и `source_id = id приглашения`. Параллельная запись (одновременный отклик) молча пропускается. В журнал аудита пишется действие `contacts.unlock`. С этого момента контакты кандидата видны работодателю в списке приглашений, карточке кандидата, JSON Resume и PDF.
6. Если у работодателя включён webhook, поставить в outbox событие `invitation.accepted` с теми же данными, что работодатель видит в API, уже с контактами.
7. Зафиксировать транзакцию: статус, раскрытие, аудит и событие сохраняются вместе.
8. После ответа в фоне отправить webhook'и из outbox и письмо работодателю о принятии (имя как в выдаче, без контактов). Вернуть `InvitationForCandidate` с раскрытым `contact_method`.

**При ошибке:** транзакция откатывается целиком: статус не меняется, контакты не раскрываются, события и письма не отправляются.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `401` | Нет токена или он истёк | `unauthorized` — «Требуется вход» / «Токен недействителен или истёк» |
| `403` | Роль не `candidate` или нет профиля кандидата | `forbidden` — «Недостаточно прав» / «Профиль кандидата не найден» |
| `403` | Общий демо-работодатель и не демо-кандидат (редкий случай: такое приглашение не создаётся) | `demo_account` — «Демо-компания работает только с демо-кандидатами — зарегистрируйте свою компанию» |
| `404` | Приглашения нет или оно адресовано другому кандидату | `not_found` — «Приглашение не найдено» |
| `409` | Приглашение уже не активно | `invitation_closed` — «Приглашение уже не активно» |
| `422` | `invitation_id` не число | `validation_error` — «Ошибка валидации данных» |

---

## 7. Отказ кандидата от приглашения

### Назначение

Кандидат отклоняет приглашение и указывает причину. Причины копятся в статистике отказов работодателя (`GET /employers/me/decline-stats`, например «3 из 5 отказов — зарплата») и влияют на оценку вероятности принятия. Контакты при отказе не раскрываются.

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/invitations/{invitation_id}/decline` |
| Авторизация | роль `candidate`, `Authorization: Bearer <JWT>`; только своё приглашение |
| Формат данных | `application/json` |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `invitation_id` | path | `integer` | да | id приглашения |
| `reason` | body | `string` | да | Причина: `salary`, `stack`, `work_format`, `company`, `not_looking`, `other` |
| `comment` | body | `string \| null` | нет | Комментарий, до 1000 символов |

**Пример запроса:**

```http
POST /api/v1/invitations/31/decline
Authorization: Bearer eyJ…
Content-Type: application/json
```

```json
{
  "reason": "salary",
  "comment": "Рассматриваю предложения от 320 000 ₽"
}
```

### Экспорт — параметры ответа

**Успешный статус:** `200 OK`. Тело — `InvitationForCandidate`: поля те же, что в [принятии приглашения](#6-принятие-приглашения-кандидатом).

| Параметр | Тип | Описание |
| --- | --- | --- |
| `status` | `string` | После успешного вызова — `declined` |
| `contact_method` | `object \| null` | Остаётся `null`: контакт рекрутера раскрывается только при принятии |
| `responded_at` | `string` (date-time) | Время отказа |
| остальные поля | — | Как у `InvitationForCandidate` выше; полная схема — в Swagger |

**Пример успешного ответа** (сокращён):

```json
{
  "id": 31,
  "company": {"id": 3, "company_name": "Тестовая компания", "industry": "fintech", "website": null, "description": null,
    "reputation": {"invitations_sent": 6, "acceptance_rate": 0.5, "withdrawn_rate": 0.0, "median_response_hours": 20.0}},
  "title": "Backend в платёжную команду",
  "message": "Пишем платёжный шлюз на Python",
  "salary_from": 250000,
  "salary_to": 300000,
  "contact_method": null,
  "why_you": {"lines": []},
  "salary_market": null,
  "status": "declined",
  "created_at": "2026-10-09T10:20:00Z",
  "viewed_at": "2026-10-09T11:02:00Z",
  "responded_at": "2026-10-09T11:06:00Z",
  "expires_at": "2026-10-23T10:20:00Z",
  "warnings": [],
  "report": null
}
```

### Алгоритм работы метода

1. Проверить роль кандидата и тело запроса (`reason` из перечня, `comment` до 1000 символов).
2. Перевести просроченные приглашения в `expired` и прочитать приглашение с блокировкой строки. Если приглашение не найдено или адресовано другому кандидату, вернуть 404.
3. Если статус не `sent` и не `viewed`, вернуть 409 `invitation_closed`.
4. Установить `status = declined`, `decline_reason`, `decline_comment`, `responded_at = now`; если `viewed_at` пуст, заполнить и его. В `contact_unlocks` ничего не пишется.
5. Если у работодателя включён webhook, поставить в outbox событие `invitation.declined` без контактов кандидата. Работодатель увидит комментарий с вычищенными контактами: их могли вписать в текст.
6. Зафиксировать транзакцию. После ответа в фоне отправить webhook'и и письмо работодателю с причиной отказа. Вернуть `InvitationForCandidate`.

**При ошибке:** транзакция откатывается, статус приглашения не меняется.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `401` | Нет токена или он истёк | `unauthorized` — «Требуется вход» |
| `403` | Роль не `candidate` или нет профиля кандидата | `forbidden` — «Недостаточно прав» / «Профиль кандидата не найден» |
| `404` | Приглашения нет или оно адресовано другому кандидату | `not_found` — «Приглашение не найдено» |
| `409` | Приглашение уже принято, отклонено, отозвано или просрочено | `invitation_closed` — «Приглашение уже не активно» |
| `422` | Нет `reason`, недопустимое значение или `comment` длиннее 1000 символов | `validation_error` — «Ошибка валидации данных», `details[].msg` — «Обязательное поле» / «Недопустимое значение» / «Слишком длинное значение» |

---

## 8. Старт попытки теста

### Назначение

Кандидат начинает адаптивный тест на грейд в своей специализации. Только тест определяет категорию «специализация × грейд». Метод создаёт попытку и проверяет правила смены грейда: интервалы, повтор после провала, текущий грейд. Задания по одному выдаёт `GET /tests/attempts/{attempt_id}/current`, ответы принимает [метод 9](#9-ответ-на-задание-теста).

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/tests/attempts` |
| Авторизация | роль `candidate`, `Authorization: Bearer <JWT>`; пройден опрос и выбрана специализация |
| Формат данных | `application/json` |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `specialization` | body | `string` | да | slug специализации; должен совпадать со специализацией кандидата |
| `grade_target` | body | `string` | да | Целевой грейд: `intern`, `junior`, `middle`, `senior` |
| `purpose` | body | `string` | нет | По умолчанию `calibration`. Учитывается только значение `express` (экспресс-тест без присвоения категории). Для остальных значений назначение (`calibration`, `upgrade`, `downgrade`) определяют правила грейда |

**Пример запроса:**

```http
POST /api/v1/tests/attempts
Authorization: Bearer eyJ…
Content-Type: application/json
```

```json
{
  "specialization": "backend",
  "grade_target": "middle"
}
```

### Экспорт — параметры ответа

**Успешный статус:** `201 Created`. Тело — `AttemptOut`.

| Параметр | Тип | Описание |
| --- | --- | --- |
| `id` | `integer` | id попытки — нужен для `/current`, `/answer`, `/result` |
| `specialization` | `string` | Специализация теста |
| `grade_target` | `string` | Целевой грейд |
| `purpose` | `string` | Назначение по правилам грейда: `calibration`, `upgrade`, `downgrade` или `express` |
| `status` | `string` | `in_progress` у новой попытки; дальше `completed`, `abandoned`, `expired` |
| `answered` | `integer` | Сколько заданий отвечено; у новой — `0` |
| `total_estimate` | `integer` | Ожидаемое число заданий без уточняющих у порога грейда |
| `total_max` | `integer` | Наибольшее число заданий с уточняющими у порога грейда |
| `started_at` | `string` (date-time) | Время старта (серверное) |
| `finished_at` | `string \| null` (date-time) | Время завершения; у новой — `null` |

**Пример успешного ответа:**

```json
{
  "id": 88,
  "specialization": "backend",
  "grade_target": "middle",
  "purpose": "calibration",
  "status": "in_progress",
  "answered": 0,
  "total_estimate": 20,
  "total_max": 24,
  "started_at": "2026-10-09T12:00:00Z",
  "finished_at": null
}
```

### Алгоритм работы метода

1. Проверить роль кандидата и найти его профиль.
2. Проверить онбординг: без выбранной специализации вернуть 409 `survey_required`. Если `specialization` не совпадает со специализацией кандидата — 409 `specialization_mismatch`. Если для специализации ещё нет теста — 400 `no_test_for_specialization`.
3. Заблокировать строку кандидата (`FOR UPDATE`), чтобы два параллельных старта не создали две попытки. Если есть незавершённая попытка, вернуть 409 `attempt_in_progress` с `details.attempt_id`.
4. Для экспресс-теста проверить, что он включён (`EXPRESS_TEST_ENABLED`) и не исчерпан дневной лимит `EXPRESS_TESTS_PER_DAY` (5); счётчик фиксируется сразу. Для обычного теста применить правила грейда (§6.3, `categories/rules.py`): калибровка без категории, повтор того же грейда после провала через `FAILED_GRADE_RETRY_DAYS`, смена грейда не чаще раза в `GRADE_CHANGE_COOLDOWN_DAYS`, один немедленный тест на грейд выше после уверенного прохода, перепроверка своего грейда только при `GRADE_RETEST_CAN_DOWNGRADE`. При запрете вернуть 409 с кодом правила и, если известно, `details.available_at`.
5. Собрать конфигурацию: режим теста (`full` или `short` по `TEST_MODE`, `express` для экспресса), модули стека из последнего ответа на опрос и случайный `seed`.
6. Создать строку `test_attempts` со статусом `in_progress` и зафиксировать транзакцию. Задания на этом шаге не создаются: первое появится при вызове `/current`.
7. Посчитать `total_estimate` и `total_max` по blueprint (`content/blueprints.yaml`) и вернуть `AttemptOut`.

**При ошибке:** попытка не создаётся. Ответ — в едином формате ошибки, у 409 причина указана в `code`.

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `400` | Для специализации ещё нет теста | `no_test_for_specialization` — «Для этой специализации тест появится позже» |
| `401` | Нет токена или он истёк | `unauthorized` — «Требуется вход» |
| `403` | Роль не `candidate` или нет профиля кандидата | `forbidden` — «Недостаточно прав» / «Профиль кандидата не найден» |
| `403` | Экспресс-тест выключен на платформе | `express_disabled` — «Экспресс-тест на платформе выключен» |
| `409` | Не пройден опрос, не выбрана специализация | `survey_required` — «Сначала пройдите опрос и выберите специализацию» |
| `409` | Специализация в запросе не совпадает со специализацией кандидата | `specialization_mismatch` — «Тест доступен по вашей специализации» |
| `409` | Есть незавершённая попытка | `attempt_in_progress` — «Есть незавершённый тест», `details: {"attempt_id": …}` |
| `409` | Действует интервал смены грейда или повтора после провала | `grade_cooldown` — «Сменить грейд можно не чаще раза в N дней» / «Повторная попытка на этот грейд — через N дней» / «Перепроверить грейд можно не чаще раза в N дней», `details: {"available_at": "…"}` |
| `409` | Тест на текущий грейд при выключенной перепроверке | `same_grade` — «Это ваш текущий грейд» |
| `422` | Нет обязательных полей или недопустимые `grade_target`, `purpose` | `validation_error` — «Ошибка валидации данных» |
| `429` | Исчерпан дневной лимит экспресс-тестов | `too_many_requests` — «Экспресс-тестов на сегодня больше нет — попробуйте завтра» |

---

## 9. Ответ на задание теста

### Назначение

Принимает ответ на текущее задание попытки. Время ответа считает сервер: момент показа задания фиксирует `/current`, а ответ после дедлайна засчитывается как неверный. Ключи ответов на фронт не уходят. После последнего задания метод завершает попытку и пересчитывает категорию и проверенные навыки.

| Свойство | Значение |
| --- | --- |
| Метод и путь | `POST /api/v1/tests/attempts/{attempt_id}/answer` |
| Авторизация | роль `candidate`, `Authorization: Bearer <JWT>`; только своя попытка |
| Формат данных | `application/json` |

### Импорт — параметры запроса

| Параметр | Где передаётся | Тип | Обязательный | Описание |
| --- | --- | --- | --- | --- |
| `attempt_id` | path | `integer` | да | id попытки |
| `item_id` | body | `integer` | да | id текущего задания из `GET /tests/attempts/{attempt_id}/current` |
| `response` | body | `object` | да | Ответ; заполняется поле, соответствующее виду задания (`kind`) |
| `response.choice_ids` | body | `array<string> \| null` | нет | id выбранных вариантов для `single_choice`, `multi_choice`, `code_output` |
| `response.number` | body | `number \| null` | нет | Число для `numeric` (сравнивается с допуском) |
| `response.order` | body | `array<string> \| null` | нет | id вариантов в нужном порядке для `ordering` |
| `response.text` | body | `string \| null` | нет | Текст до 1500 символов для открытого вопроса `open_approach` |
| `focus_lost_count` | body | `integer` | нет | Сколько раз уходили со вкладки во время задания, ≥ 0, по умолчанию `0`. Только сигнал, не штраф |

**Пример запроса:**

```http
POST /api/v1/tests/attempts/88/answer
Authorization: Bearer eyJ…
Content-Type: application/json
```

```json
{
  "item_id": 1204,
  "response": {"choice_ids": ["b"]},
  "focus_lost_count": 0
}
```

### Экспорт — параметры ответа

**Успешный статус:** `200 OK`. Тело — `AnswerAck`. Верный ли ответ, метод не сообщает: разбор по темам — в `GET /tests/attempts/{attempt_id}/result` после завершения.

| Параметр | Тип | Описание |
| --- | --- | --- |
| `accepted` | `boolean` | Ответ записан (всегда `true` при 200) |
| `late` | `boolean` | Ответ пришёл после дедлайна задания (с учётом `ANSWER_GRACE_SECONDS`) и засчитан как неверный; текст открытого ответа в этом случае не сохраняется |
| `finished` | `boolean` | `true` — заданий больше нет, попытка завершена, результат — в `/result` |

**Пример успешного ответа:**

```json
{
  "accepted": true,
  "late": false,
  "finished": false
}
```

### Алгоритм работы метода

1. Проверить роль кандидата и тело запроса.
2. Прочитать попытку с блокировкой строки (`FOR UPDATE`): ответы и выдача заданий одной попытки идут строго по очереди. Если попытка не найдена или чужая, вернуть 404.
3. Если попытка не `in_progress`, вернуть 409 `attempt_finished`. Если `item_id` не совпадает с текущим неотвеченным заданием (уже отвечено, пропущено по времени или чужое), вернуть 409 `not_current_item`. Вернуться к прошлому заданию нельзя.
4. Определить опоздание по серверному времени: `now > shown_at + time_limit_sec + ANSWER_GRACE_SECONDS`.
5. Записать ответ: `response`, `answered_at`, `time_ms` и балл. Балл считается по ключу, который хранится только на сервере. Для выборов и порядка нужно точное совпадение, для числа — совпадение с допуском. Опоздавший ответ получает 0. Открытый ответ в балл не входит.
6. Для открытого вопроса (если не опоздал) LLM по чек-листу отмечает выполненные критерии (§10.5). Доля отмеченных сохраняется как `approach_score` и в θ̂ не входит. Если LLM недоступен, ответ остаётся без оценки.
7. Обновить статистику показов и верных ответов шаблона и прибавить `focus_lost_count` к флагам попытки.
8. Спросить планировщик адаптивного теста (MST, §10.3), есть ли следующее задание. Если нет, завершить попытку (`_finalize`): посчитать θ̂, SE и результат по грейду, баллы по темам и навыкам, сигналы честности; поставить `status = completed`. Для обычного теста дополнительно присвоить или снять категорию, перезаписать навыки «проверено тестом», пересчитать индекс выдачи и перцентили категорий. Экспресс-тест категорию и выдачу не меняет.
9. Зафиксировать транзакцию и вернуть `AnswerAck`.

**При ошибке:** транзакция откатывается, ответ не записывается, текущее задание остаётся прежним (если его время не вышло).

### Ошибки

| Статус | Причина | Ответ системы |
| --- | --- | --- |
| `401` | Нет токена или он истёк | `unauthorized` — «Требуется вход» |
| `403` | Роль не `candidate` или нет профиля кандидата | `forbidden` — «Недостаточно прав» / «Профиль кандидата не найден» |
| `404` | Попытки нет или она чужая | `not_found` — «Попытка не найдена» |
| `409` | Попытка уже завершена, прервана или просрочена | `attempt_finished` — «Тест уже завершён» |
| `409` | `item_id` — не текущее задание | `not_current_item` — «Это задание уже не текущее» |
| `422` | Нет `item_id` или `response`, `text` длиннее 1500 символов, `focus_lost_count < 0` | `validation_error` — «Ошибка валидации данных» |
