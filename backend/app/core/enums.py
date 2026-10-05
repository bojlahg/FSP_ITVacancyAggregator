from enum import StrEnum


class Role(StrEnum):
    candidate = "candidate"
    employer = "employer"
    admin = "admin"
    expert = "expert"  # разметка пар «потребность — кандидат» для экспертной валидации подбора (§12.2)


class Grade(StrEnum):
    intern = "intern"
    junior = "junior"
    middle = "middle"
    senior = "senior"


class WorkFormat(StrEnum):
    office = "office"
    hybrid = "hybrid"
    remote = "remote"


class SearchStatus(StrEnum):
    active = "active"
    open = "open"
    hidden = "hidden"


class ConsentKind(StrEnum):
    pd_processing = "pd_processing"
    profile_publication = "profile_publication"
    fsp_import = "fsp_import"


class EmailTokenPurpose(StrEnum):
    verify = "verify"
    reset = "reset"


class SkillSource(StrEnum):
    declared = "declared"
    resume = "resume"
    test = "test"
    fsp = "fsp"
    task = "task"


class SkillStatus(StrEnum):
    verified = "verified"
    fsp_confirmed = "fsp_confirmed"
    task_confirmed = "task_confirmed"
    declared = "declared"


class FspLinkMethod(StrEnum):
    manual = "manual"
    oidc = "oidc"


class ParserKind(StrEnum):
    dict = "dict"
    llm = "llm"


class AttemptPurpose(StrEnum):
    calibration = "calibration"
    upgrade = "upgrade"
    downgrade = "downgrade"
    vacancy_preview = "vacancy_preview"


class AttemptStatus(StrEnum):
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"
    expired = "expired"


class AttemptResult(StrEnum):
    fail = "fail"
    passed = "pass"
    confident_pass = "confident_pass"


class ItemKind(StrEnum):
    single_choice = "single_choice"
    multi_choice = "multi_choice"
    numeric = "numeric"
    ordering = "ordering"
    code_output = "code_output"
    sql_result = "sql_result"
    open_approach = "open_approach"


class TemplateStatus(StrEnum):
    pilot = "pilot"
    active = "active"
    retired = "retired"


class CompetencyStatus(StrEnum):
    confirmed = "confirmed"
    supported = "supported"


class NeedStatus(StrEnum):
    draft = "draft"
    active = "active"
    closed = "closed"


class InvitationStatus(StrEnum):
    sent = "sent"
    viewed = "viewed"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    withdrawn = "withdrawn"


class DeclineReason(StrEnum):
    salary = "salary"
    stack = "stack"
    work_format = "work_format"
    company = "company"
    not_looking = "not_looking"
    other = "other"


class ApplicationStatus(StrEnum):
    sent = "sent"
    viewed = "viewed"
    accepted = "accepted"
    rejected = "rejected"


class UnlockSource(StrEnum):
    invitation = "invitation"
    application = "application"


class TaskKind(StrEnum):
    auto = "auto"
    approach = "approach"


class AssignmentStatus(StrEnum):
    offered = "offered"
    submitted = "submitted"
    expired = "expired"
    skipped = "skipped"


class GradedBy(StrEnum):
    auto = "auto"
    llm = "llm"
    employer = "employer"
