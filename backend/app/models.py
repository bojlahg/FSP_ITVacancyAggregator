"""Импорт всех моделей: нужен Alembic для autogenerate и для полной инициализации метаданных."""

from app.core.db import Base
from app.core.ratelimit import RateLimitHit
from app.core.types import add_enum_checks
from app.modules.appeals.models import GradeAppeal
from app.modules.applications.models import Application
from app.modules.auth.models import AuditLog, Consent, EmailToken, RefreshToken, User
from app.modules.candidates.models import Candidate, CandidateExperience, CandidateSkill
from app.modules.categories.models import CandidateCategory
from app.modules.employers.models import Employer
from app.modules.expert.models import AngoffHofstee, AngoffRating, ExpertLabel, ExpertPair
from app.modules.fsp.models import CandidateCompetency, FspAchievement, FspRank
from app.modules.integrations.models import EmployerApiKey, EmployerWebhook, WebhookDelivery
from app.modules.invitations.models import ContactUnlock, Invitation, InvitationReport
from app.modules.matching.models import CandidateSearchIndex
from app.modules.needs.models import HiringNeed, NeedShortlist
from app.modules.resume.models import Resume
from app.modules.survey.models import SurveyResponse
from app.modules.tasks.models import EmployerTask, TaskAssignment
from app.modules.testing.models import TemplateStat, TestAttempt, TestAttemptItem

add_enum_checks(Base.metadata)

__all__ = [
    "AngoffHofstee",
    "AngoffRating",
    "Application",
    "AuditLog",
    "Base",
    "Candidate",
    "CandidateCategory",
    "CandidateCompetency",
    "CandidateExperience",
    "CandidateSearchIndex",
    "CandidateSkill",
    "Consent",
    "ContactUnlock",
    "EmailToken",
    "Employer",
    "EmployerApiKey",
    "EmployerWebhook",
    "ExpertLabel",
    "ExpertPair",
    "EmployerTask",
    "FspAchievement",
    "FspRank",
    "GradeAppeal",
    "HiringNeed",
    "Invitation",
    "InvitationReport",
    "NeedShortlist",
    "RateLimitHit",
    "RefreshToken",
    "Resume",
    "SurveyResponse",
    "TaskAssignment",
    "TemplateStat",
    "TestAttempt",
    "TestAttemptItem",
    "User",
    "WebhookDelivery",
]
