from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-jwt-secret-change-me-0000"


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
    policy_version: str = "2026-10-05"

    # Ограничение частоты на /auth/*: запросов в окне на один IP
    auth_rate_limit: int = 20
    auth_rate_window_seconds: int = 60

    demo_candidate_email: str = "demo-candidate@itscout.ru"
    demo_employer_email: str = "demo-employer@itscout.ru"
    # Демо-админ (сброс демо-данных) создаётся генератором, только если пароль задан в .env
    demo_admin_email: str = "admin@itscout.ru"
    demo_admin_password: str | None = None
    # Код-приглашение для регистрации экспертов разметки (§12.2); пусто — регистрация экспертов выключена
    expert_invite_code: str = ""

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

    # Публичная страница «Как работает тест»: лимиты, чтобы запросы без входа оставались дешёвыми
    explainer_max_seeds: int = 6
    explainer_max_sample: int = 200
    explainer_leak_size: int = 50
    explainer_simulations: int = 30

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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
