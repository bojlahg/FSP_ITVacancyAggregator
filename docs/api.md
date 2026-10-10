# API

Все методы описаны в спецификации **OpenAPI 3.1**: [`backend/openapi.json`](../backend/openapi.json) генерируется из кода (Pydantic-схемы и роутеры FastAPI — источник контракта), CI проверяет, что файл и клиент фронта актуальны. Интерактивная документация — **Swagger UI https://itscout.ru/api/docs** (локально — http://localhost:8000/api/docs). Таблица всех операций с кодами ответов — [api-endpoints.md](api-endpoints.md).

## 1. Общие правила

| Что | Как |
|---|---|
| Префикс | `/api/v1` |
| Формат | JSON, UTF-8; загрузка резюме — `multipart/form-data`; PDF-профиль — `application/pdf` |
| Аутентификация | `Authorization: Bearer <access JWT>` (живёт 15 минут). Refresh-токен — httpOnly cookie `itscout_refresh` на `/api/v1/auth`, обновление — `POST /auth/refresh` с ротацией. Для ATS — `X-API-Key: itsk_…` на методах работодателя (ключ выпускается в профиле компании), события — подписанные webhook'и (см. [anti-fraud-ats.md](anti-fraud-ats.md)) |
| Роли | `candidate`, `employer`, `admin`; эндпоинты кабинета доступны только своей роли (иначе 403) |
| Доступ к объектам | кандидат видит только свои приглашения, отклики и задания, работодатель — только свои потребности, приглашения и задания; чужой объект → 404 (не раскрываем факт существования) или 403 |
| Ошибки | единый формат, см. ниже |
| Ограничение частоты | `/auth/*` — 20 запросов в минуту на IP и путь, сверх — 429 |

**Формат ошибки:**

```json
{
  "error": {
    "code": "invitation_limit",
    "message": "По этой потребности уже максимум активных приглашений — дождитесь ответов",
    "details": null
  }
}
```

| HTTP | Когда | Примеры `code` |
|---|---|---|
| 400 | некорректный запрос, неверный или просроченный токен | `bad_request`, `invalid_token` |
| 401 | нет или истёк access-токен, неверный пароль | `unauthorized`, `invalid_credentials` |
| 403 | не та роль, нет прав | `forbidden` |
| 404 | объект не найден или чужой | `not_found` |
| 409 | конфликт состояния | `grade_cooldown`, `already_invited`, `invitation_limit`, `already_applied`, `category_required`, `fsp_id_taken`, `consent_required` |
| 422 | ошибка валидации данных (в `details` — поля) | `validation_error`, `file_too_large`, `not_pdf`, `invalid_pdf`, `survey_invalid` |
| 429 | превышен лимит запросов | `too_many_requests` |

## 2. Группы эндпоинтов

141 операция в 27 группах (теги Swagger):

| Группа | Основные операции |
|---|---|
| service | `GET /health`; `POST /admin/reseed` (роль admin, только `DEMO_MODE`) |
| auth | регистрация с согласиями, подтверждение почты, вход, refresh, выход, демо-вход, `GET /me` |
| catalog | специализации, грейды, навыки (поиск по алиасам), отрасли, софт-скиллы, роли |
| candidate: profile | профиль, приватность, согласия, статус поиска, удаление аккаунта, резюме → предзаполнение, PDF-профиль |
| candidate: onboarding | вопросы опроса, ответы → рекомендованные специализации, выбор специализации, статус грейда |
| candidate: testing | создание попытки, текущее задание (без ключа), ответ, результат |
| candidate: fsp | профиль ФСП, ручная привязка, OIDC (`/fsp/oidc/start`, `/fsp/oidc/callback`), отвязка |
| candidate: invitations | входящие приглашения, просмотр, принять, отклонить с причиной |
| candidate: vacancies | вакансии с сортировкой по совпадению, отклик, мои отклики |
| candidate: tasks | регулярные задания, решение, пропуск |
| candidate: challenges | челленджи компаний по категории, старт (одна попытка), текущий вопрос без ключа, ответ, результат |
| candidate: market | рынок своей категории: потребности, вилки, востребованные навыки |
| employer: company | профиль компании, статистика отказов |
| employer: needs & matching | разбор текста, потребности и версии, подборка с объяснениями, покрытие вилки, шорт-лист |
| employer: talent pool | поиск по базе, каталог категорий, карточка кандидата, PDF карточки |
| employer: invitations | создать, список со статусами, отозвать |
| employer: vacancies | публикация, отклики по вакансии, просмотр, принять, отклонить |
| employer: vacancy test preview | предпросмотр теста под вакансию, демо-вакансии |
| employer: tasks | задания, шаблоны под потребность, решения, оценка решения |
| employer: challenges | черновик со своими вопросами, правка, публикация, закрытие, решившие по результату |
| employer: integrations | API-ключи ATS, webhook: адрес, секрет подписи, тестовое событие, журнал и повтор доставок |
| public: test explainer | «Как работает тест»: шкала грейдов и параметры MST, информационная функция, шаблоны IRT без ключей, экземпляры и их разнообразие |
| public: legal | юридические документы: политика, согласия, правила рекомендаций |
| expert | разметка пар «потребность — кандидат» 0–3 и метрики подбора; Modified Angoff: оценки, раунд 2, Hofstee, итог |
| admin: reports | жалобы кандидатов на приглашения, закрытие с описанием мер |
| admin: appeals | обращения кандидатов по грейду, ответ (категорию не меняет) |
| debug | статус раздела, сброс ограничений и своих попыток, тестовое письмо, reseed; только при `DEBUG_TOOLS=true`, иначе 404 |

## 3. Пример: сквозной сценарий через API

```bash
API=https://itscout.ru/api/v1

# Кандидат: демо-вход и текущий статус категории
TOKEN=$(curl -s -X POST $API/auth/demo-login -H 'Content-Type: application/json' \
  -d '{"persona":"candidate"}' | jq -r .access_token)
curl -s $API/candidates/me/grade-status -H "Authorization: Bearer $TOKEN"

# Работодатель: разбор потребности из текста
ETOKEN=$(curl -s -X POST $API/auth/demo-login -H 'Content-Type: application/json' \
  -d '{"persona":"employer"}' | jq -r .access_token)
curl -s -X POST $API/needs/parse -H "Authorization: Bearer $ETOKEN" -H 'Content-Type: application/json' \
  -d '{"raw_text":"Ищем Middle Python-разработчика: FastAPI, PostgreSQL, Docker. Удалёнка, 220–260 тыс. ₽"}'

# Подборка по существующей потребности: категории, кандидаты и объяснения
curl -s "$API/needs/1/recommendations" -H "Authorization: Bearer $ETOKEN"
```

Попытка теста: `POST /tests/attempts {specialization, grade_target, purpose}` → цикл `GET /tests/attempts/{id}/current` (задание без ключа и с лимитом времени) и `POST /tests/attempts/{id}/answer {item_id, response}` → `GET /tests/attempts/{id}/result`. Время ответа считает сервер; ответ на не текущее задание или после срока не засчитывается.

## 4. API мока реестра ФСП

Отдельный сервис, префикс `/fsp-api/v1`, заголовок `X-Api-Key`: участник, результаты с данными соревнований, разряды, соревнования. Подробнее — [fsp-integration.md](fsp-integration.md).

## 5. Клиент фронта

Типы генерируются из `openapi.json` (`npm run gen:api` → `frontend/src/api/schema.d.ts`), запросы идут через `openapi-fetch`. После изменения схемы backend: `make openapi` (выгрузить `openapi.json` и перегенерировать клиент).
