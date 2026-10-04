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

    email_backend: Literal["console", "smtp", "unisender"] = "console"
    email_verification_required: bool = False
    email_from: str = "noreply@itscout.ru"
    email_from_name: str = "ITScout"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    # none — Mailpit в dev; ssl — порт 465; starttls — порт 587
    smtp_security: Literal["none", "ssl", "starttls"] = "none"
    smtp_user: str = ""
    smtp_password: str = ""
    unisender_api_url: str = ""
    unisender_api_key: str = ""

    llm_provider: Literal["none", "yandex"] = "none"
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_model: str = "yandexgpt/latest"

    fsp_api_url: str = "http://fsp-mock:8001/fsp-api/v1"
    fsp_api_key: str = "dev-fsp-key"

    upload_dir: str = "/data/uploads"

    # full — полный тест (§10.3), short — сокращённый для демо жюри
    test_mode: Literal["full", "short"] = "full"
    answer_grace_seconds: int = 5

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
