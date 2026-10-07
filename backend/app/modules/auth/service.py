import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mail_templates
from app.core.audit import audit
from app.core.config import get_settings
from app.core.enums import ConsentKind, EmailTokenPurpose, Role
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.mail import Mail, is_skipped_address
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from app.modules.auth.models import Consent, EmailToken, RefreshToken, User
from app.modules.auth.schemas import (
    NotificationSettings,
    RegisterExpertRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.modules.candidates import service as candidates_service
from app.modules.employers import service as employers_service


class InvalidTokenError(AppError):
    status_code = 400
    code = "invalid_token"
    message = "Ссылка недействительна или устарела"


@dataclass(frozen=True)
class Session:
    """Результат входа: тело ответа и refresh-токен для httpOnly cookie."""

    response: TokenResponse
    refresh_token: str
    verification_mail: Mail | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        email_verified=user.email_verified_at is not None,
        email_verification_required=get_settings().email_verification_required,
        email_notifications=user.email_notifications,
        created_at=user.created_at,
    )


async def _issue_session(db: AsyncSession, user: User, verification_mail: Mail | None = None) -> Session:
    settings = get_settings()
    refresh_token, refresh_hash = new_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=_now() + timedelta(days=settings.refresh_ttl_days),
        )
    )
    await db.commit()
    access_token, expires_in = create_access_token(user.id, user.role.value)
    response = TokenResponse(access_token=access_token, expires_in=expires_in, user=_user_out(user))
    return Session(response=response, refresh_token=refresh_token, verification_mail=verification_mail)


async def _verification_mail(db: AsyncSession, user: User) -> Mail:
    settings = get_settings()
    token, token_hash = new_opaque_token()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=EmailTokenPurpose.verify,
            token_hash=token_hash,
            expires_at=_now() + timedelta(hours=settings.email_token_ttl_hours),
        )
    )
    return mail_templates.verification(
        user.email, f"/verify-email?token={token}", settings.email_token_ttl_hours
    )


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(func.lower(User.email) == email.lower()))


async def register(db: AsyncSession, body: RegisterRequest) -> Session:
    if not body.consent_pd_processing:
        raise AppError(
            "Без согласия на обработку персональных данных регистрация невозможна",
            code="consent_required",
            details=[{"loc": ["body", "consent_pd_processing"], "msg": "required", "type": "consent"}],
        )
    if await _get_user_by_email(db, body.email):
        raise ConflictError("Этот email уже зарегистрирован", code="email_taken")

    settings = get_settings()
    role = Role(body.role)
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role=role)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Этот email уже зарегистрирован", code="email_taken") from exc

    if role == Role.candidate:
        candidates_service.create_empty_profile(db, user.id)
    else:
        employers_service.create_empty_profile(db, user.id)

    kinds = [ConsentKind.pd_processing]
    if role == Role.candidate and body.consent_profile_publication:
        kinds.append(ConsentKind.profile_publication)
    for kind in kinds:
        db.add(Consent(user_id=user.id, kind=kind, policy_version=settings.policy_version))
        audit(
            db,
            actor_user_id=user.id,
            action="consent.granted",
            object_type="user",
            object_id=user.id,
            meta={"kind": kind.value, "policy_version": settings.policy_version},
        )

    mail = await _verification_mail(db, user)
    return await _issue_session(db, user, verification_mail=mail)


async def register_expert(db: AsyncSession, body: RegisterExpertRequest) -> Session:
    """Эксперт разметки (§12.2) регистрируется сам по коду-приглашению; без кода функция выключена."""
    settings = get_settings()
    if not settings.expert_invite_code:
        raise NotFoundError("Регистрация экспертов выключена")
    if not secrets.compare_digest(body.code.strip(), settings.expert_invite_code):
        raise ForbiddenError("Неверный код-приглашение", code="invalid_invite_code")
    if not body.consent_pd_processing:
        raise AppError(
            "Без согласия на обработку персональных данных регистрация невозможна", code="consent_required"
        )
    if await _get_user_by_email(db, body.email):
        raise ConflictError("Этот email уже зарегистрирован", code="email_taken")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role=Role.expert,
        email_verified_at=_now(),  # адрес подтверждает код-приглашение, письмо не нужно
    )
    db.add(user)
    await db.flush()
    db.add(Consent(user_id=user.id, kind=ConsentKind.pd_processing, policy_version=settings.policy_version))
    audit(
        db, actor_user_id=user.id, action="expert.registered", object_type="user", object_id=user.id, meta={}
    )
    return await _issue_session(db, user)


async def login(db: AsyncSession, email: str, password: str) -> Session:
    user = await _get_user_by_email(db, email)
    if user is None or user.deleted_at is not None or not verify_password(user.password_hash, password):
        raise UnauthorizedError("Неверный email или пароль", code="invalid_credentials")
    return await _issue_session(db, user)


async def demo_login(db: AsyncSession, persona: str) -> Session:
    """Демо-аккаунты создаёт seed (T07); если его ещё не было — заводим пустой аккаунт, чтобы вход работал."""
    settings = get_settings()
    email = settings.demo_candidate_email if persona == "candidate" else settings.demo_employer_email
    user = await _get_user_by_email(db, email)
    if user is None:
        role = Role.candidate if persona == "candidate" else Role.employer
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role=role,
            email_verified_at=_now(),
            seeded=True,
        )
        db.add(user)
        await db.flush()
        if role == Role.candidate:
            candidates_service.create_empty_profile(db, user.id)
        else:
            employers_service.create_empty_profile(db, user.id, company_name="Демо Банк")
    return await _issue_session(db, user)


async def refresh(db: AsyncSession, refresh_token: str | None) -> Session:
    if not refresh_token:
        raise UnauthorizedError("Сессия истекла, войдите снова", code="no_refresh_token")
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token)))
    if stored is None or stored.expires_at <= _now():
        raise UnauthorizedError("Сессия истекла, войдите снова", code="invalid_refresh_token")
    if stored.revoked_at is not None:
        # Повторное использование отозванного токена — признак кражи: отзываем все сессии пользователя
        await _revoke_all(db, stored.user_id)
        await db.commit()
        raise UnauthorizedError("Сессия отозвана, войдите снова", code="refresh_token_reused")

    user = await db.get(User, stored.user_id)
    if user is None or user.deleted_at is not None:
        raise UnauthorizedError("Сессия истекла, войдите снова", code="invalid_refresh_token")
    stored.revoked_at = _now()
    return await _issue_session(db, user)


async def _revoke_all(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def revoke_sessions(db: AsyncSession, user_id: int) -> None:
    """Закрыть все сессии пользователя (удаление аккаунта). Коммитит вызывающий."""
    await _revoke_all(db, user_id)


async def logout(db: AsyncSession, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_token), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.commit()


async def verify_email(db: AsyncSession, token: str) -> None:
    stored = await db.scalar(
        select(EmailToken).where(
            EmailToken.token_hash == hash_token(token), EmailToken.purpose == EmailTokenPurpose.verify
        )
    )
    if stored is None or stored.used_at is not None or stored.expires_at <= _now():
        raise InvalidTokenError()
    user = await db.get(User, stored.user_id)
    if user is None:
        raise InvalidTokenError()
    stored.used_at = _now()
    if user.email_verified_at is None:
        user.email_verified_at = _now()
    await db.commit()


async def resend_verification(db: AsyncSession, user_id: int) -> Mail | None:
    user = await get_user(db, user_id)
    if user.email_verified_at is not None:
        return None
    mail = await _verification_mail(db, user)
    await db.commit()
    return mail


async def get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise UnauthorizedError()
    return user


async def is_shared_demo_employer(db: AsyncSession, user_id: int) -> bool:
    user = await db.get(User, user_id)
    return user is not None and user.email.lower() == get_settings().demo_employer_email.lower()


async def is_deleted(db: AsyncSession, user_id: int) -> bool:
    user = await db.get(User, user_id)
    return user is None or user.deleted_at is not None


async def is_seeded(db: AsyncSession, user_id: int) -> bool:
    user = await db.get(User, user_id)
    return user is not None and user.seeded


async def me(db: AsyncSession, user_id: int) -> UserOut:
    return _user_out(await get_user(db, user_id))


async def update_notifications(db: AsyncSession, user_id: int, body: NotificationSettings) -> UserOut:
    user = await get_user(db, user_id)
    user.email_notifications = body.email_notifications
    await db.commit()
    return _user_out(user)


async def notification_email(db: AsyncSession, user_id: int) -> str | None:
    """Адрес для писем о подборе (§8.9); None — выключено глобально, пользователем или адрес служебный."""
    if not get_settings().notifications_enabled:
        return None
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or not user.email_notifications:
        return None
    return None if is_skipped_address(user.email) else user.email


async def has_active_consent(db: AsyncSession, user_id: int, kind: ConsentKind) -> bool:
    consent = await db.scalar(
        select(Consent.id).where(
            Consent.user_id == user_id, Consent.kind == kind, Consent.revoked_at.is_(None)
        )
    )
    return consent is not None
