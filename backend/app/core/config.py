from functools import lru_cache
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me-0000"


class TeamAccount(BaseModel):
    """Участник команды: генератор демо-данных создаёт ему админа, кандидата и работодателя."""

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,31}$", description="латиница: ivan, maria")
    password: str = Field(min_length=8)
    # Своя почта: адреса будут ivan+admin@gmail.com и т. д. — уведомления приходят на неё
    email: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    demo_mode: bool = True
    public_base_url: str = "http://localhost:5173"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    database_url: str = "postgresql+psycopg://itscout:itscout@localhost:5432/itscout"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30
    refresh_cookie_name: str = "itscout_refresh"
    # Secure-cookie включаем, когда прод работает по HTTPS
    cookie_secure: bool = False
    email_token_ttl_hours: int = 24
    # Версия юридических документов (backend/content/legal): пишется в consents.policy_version
    policy_version: str = "2026-10-06"
    # Оператор ПДн и контакт для обращений — подставляются в тексты документов (§13.1)
    legal_operator: str = "Команда ITScout (оператор будет указан при запуске)"
    legal_contact_email: str = "privacy@itscout.ru"

    # Ограничение частоты на /auth/*: запросов в окне на один IP
    auth_rate_limit: int = 20
    auth_rate_window_seconds: int = 60
    # Демо-вход без пароля: перебирать нечего, а жюри в одном зале выходит в сеть с одного IP
    demo_login_rate_limit: int = 300
    # Вход по одному email со всех адресов — против перебора пароля из разных сетей
    login_email_rate_limit: int = 10
    # «Проверка под вакансию» показывает настоящие задания банка — не больше стольких предпросмотров
    # в сутки на работодателя (§10.6)
    vacancy_preview_per_day: int = 30

    demo_candidate_email: str = "demo-candidate@itscout.ru"
    demo_employer_email: str = "demo-employer@itscout.ru"
    # Демо-админ (сброс демо-данных) создаётся генератором, только если пароль задан в .env
    # Каталог запросов к сервису backup: reseed ждёт свежий бэкап (docs/deploy.md §5.4); пусто — без бэкапа
    backup_requests_dir: str | None = None
    backup_request_timeout_seconds: int = 300
    demo_admin_email: str = "admin@itscout.ru"
    demo_admin_password: str | None = None
    # Пароль сид-аккаунтов; пусто — случайный при каждом reseed (вход в них — только демо-кнопками)
    demo_seed_password: str = ""
    # Пароль служебного кандидата e2e; пусто — пароль сид-аккаунтов. В CI — секрет E2E_CANDIDATE_PASSWORD
    e2e_candidate_password: str = ""
    # Аккаунты команды, JSON: [{"name": "ivan", "password": "...", "email": "ivan@gmail.com"}]
    team_accounts: list[TeamAccount] = []
    team_accounts_domain: str = "team.itscout.ru"
    # Отладочный раздел в кабинетах (сброс ограничений, теста, reseed); выключен — эндпоинты отвечают 404
    debug_tools: bool = False
    # Код-приглашение для регистрации экспертов разметки (§12.2); пусто — регистрация экспертов выключена
    expert_invite_code: str = ""
    # Кэш оценок подборки в памяти процесса (docs/performance.md); 0 — выключен
    recommendations_cache_seconds: int = 60
    recommendations_cache_size: int = 64
    # Интеграция с ATS: API-ключи работодателя и исходящие webhook'и (docs/anti-fraud-ats.md §2)
    api_keys_per_employer: int = 5
    api_key_touch_seconds: int = 60
    webhook_timeout_seconds: float = 5.0
    webhook_retry_delays_seconds: list[int] = [30, 300, 1800]
    webhook_worker_interval_seconds: int = 30
    webhook_batch_size: int = 20
    # Аренда пачки на отправку: больше, чем batch × timeout, чтобы строку не взял другой процесс
    webhook_lease_seconds: int = 180
    webhook_retention_days: int = 30
    webhook_manual_per_hour: int = 20
    webhook_allow_private_hosts: bool = False

    email_backend: Literal["console", "smtp"] = "console"
    email_verification_required: bool = False
    email_from: str = "noreply@itscout.ru"
    email_from_name: str = "ITScout"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    # none — Mailpit в dev; ssl — порт 465; starttls — порт 587
    smtp_security: Literal["none", "ssl", "starttls"] = "none"
    smtp_user: str = ""
    smtp_password: str = ""
    # Письма о событиях подбора (docs/implementation.md §8.9): общий выключатель. Адресатам из этих
    # доменов и из списка не пишем, чтобы сид, e2e и демо-аккаунты не слали почту на несуществующие ящики
    notifications_enabled: bool = True
    notifications_skip_domains: list[str] = [
        "example",
        "test",
        "invalid",
        "localhost",
        "example.com",
        "example.net",
        "example.org",
        "demo.itscout.ru",
        "team.itscout.ru",
    ]
    notifications_skip_emails: list[str] = ["e2e-candidate@itscout.ru"]

    llm_provider: Literal["none", "yandex"] = "none"
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_model: str = "yandexgpt/latest"
    # Бюджет LLM: при app_env=test сеть не вызывается никогда; выключатель — LLM_PROVIDER=none
    llm_max_input_chars: int = 6000
    llm_max_output_tokens: int = 800
    llm_daily_call_limit: int = 40
    llm_daily_token_limit: int = 60000
    llm_user_hourly_limit: int = 5
    llm_state_dir: str = "/data/uploads/llm"

    fsp_api_url: str = "http://fsp-mock:8001/fsp-api/v1"
    fsp_api_key: str = "dev-fsp-key"
    # Файл данных fsp-mock; генератор демо-данных пишет его в общий volume
    fsp_data_path: str = "/data/fsp/fsp.json"
    # Ручная привязка по номеру ФСП ID не доказывает владение: достижения видны с пометкой «не подтверждено»,
    # но в score, силу профиля и статус навыков «подтверждено ФСП» не идут. true — учитывать как через ФСП ID
    fsp_manual_link_counts: bool = False

    # Привязка через ФСП ID по OIDC (§9.3). Discovery читаем по внутреннему адресу IdP: issuer и
    # authorization_endpoint в нём публичные, token и jwks — внутренние (Keycloak с KC_HOSTNAME).
    fsp_oidc_discovery_url: str = "http://keycloak:8080/fsp-id/realms/fsp/.well-known/openid-configuration"
    fsp_oidc_client_id: str = "itscout"
    # Пусто — публичный клиент с PKCE; для конфиденциального клиента секрет только в .env
    fsp_oidc_client_secret: str = ""
    # Пусто — {public_base_url}/api/v1/fsp/oidc/callback
    fsp_oidc_redirect_uri: str = ""
    fsp_oidc_return_path: str = "/candidate/settings"
    fsp_oidc_state_ttl_seconds: int = 600
    fsp_oidc_cookie_name: str = "itscout_fsp_oidc"

    upload_dir: str = "/data/uploads"
    # Резюме (§7): PDF до 5 МБ; меньше символов текста — считаем сканом без текстового слоя
    resume_max_bytes: int = 5 * 1024 * 1024
    resume_max_pages: int = 10
    resume_min_text_chars: int = 40

    # full — полный тест (§10.3), short — сокращённый для демо жюри
    test_mode: Literal["full", "short"] = "full"
    answer_grace_seconds: int = 5
    # Сигналы честности попытки (§10.9): пометка работодателю «стоит перепроверить», на грейд не влияет.
    # false — сигналы не считаются, не сохраняются и нигде не показываются
    integrity_signals_enabled: bool = True

    # Публичная страница «Как работает тест»: лимиты, чтобы запросы без входа оставались дешёвыми
    explainer_max_seeds: int = 6
    explainer_max_sample: int = 200
    explainer_leak_size: int = 50
    explainer_simulations: int = 30

    # Проверка текста потребности на запрещённые требования (content/need_text_rules.yaml):
    # off — не проверять; warn — только подсказки; block — правила с severity=block запрещают публикацию
    need_text_check: Literal["off", "warn", "block"] = "block"
    # Предупреждение кандидату о признаках мошенничества в приглашении (content/invitation_scam_rules.yaml)
    invitation_scam_check: bool = True

    # Правила грейда и подбора — см. docs/implementation.md §6.3, §8.6
    grade_change_cooldown_days: int = 90
    failed_grade_retry_days: int = 30
    category_valid_days: int = 365
    max_active_invites_per_need: int = 15
    invitation_ttl_days: int = 14

    @model_validator(mode="after")
    def check_prod_secrets(self) -> Self:
        if self.app_env == "prod" and (self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32):
            raise ValueError("В prod нужен собственный JWT_SECRET длиной от 32 символов")
        if self.app_env == "prod" and not self.cookie_secure:
            raise ValueError("В prod refresh-cookie должна быть Secure: COOKIE_SECURE=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
