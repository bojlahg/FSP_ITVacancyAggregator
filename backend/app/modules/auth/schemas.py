from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from app.core.enums import Role
from app.core.schemas import ApiModel


class RegisterRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["candidate", "employer"]
    consent_pd_processing: bool = Field(description="Согласие на обработку ПДн — обязательно")
    consent_profile_publication: bool = Field(
        default=False, description="Согласие на публикацию профиля работодателям (для кандидата)"
    )


class RegisterExpertRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=1, max_length=128, description="Код-приглашение от команды")
    consent_pd_processing: bool = Field(description="Согласие на обработку ПДн — обязательно")


class LoginRequest(ApiModel):
    email: EmailStr
    password: str


class DemoLoginRequest(ApiModel):
    persona: Literal["candidate", "employer"] = Field(description="Подготовленный демо-аккаунт")


class VerifyEmailRequest(ApiModel):
    token: str


class UserOut(ApiModel):
    id: int
    email: EmailStr
    role: Role
    email_verified: bool
    email_verification_required: bool = Field(
        description="EMAIL_VERIFICATION_REQUIRED: без подтверждённой почты API — 403 email_not_verified"
    )
    email_notifications: bool = Field(description="Письма о приглашениях и откликах (§8.9)")
    created_at: datetime


class NotificationSettings(ApiModel):
    email_notifications: bool = Field(description="Присылать письма о приглашениях и откликах")


class TokenResponse(ApiModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Срок жизни access-токена, секунд")
    user: UserOut
