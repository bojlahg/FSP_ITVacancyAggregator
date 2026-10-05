"""Резюме → предзаполнение профиля и стандартный PDF-профиль (§7, задача T15)."""

import asyncio
import io
import logging
from pathlib import Path
from uuid import uuid4

import pdfplumber
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.enums import ParserKind, SkillSource
from app.core.errors import AppError, ConflictError
from app.modules.candidates import service as candidates_service
from app.modules.candidates.models import Candidate
from app.modules.candidates.schemas import CandidateProfileBase, CandidateProfileUpdate, DeclaredSkill
from app.modules.categories import service as categories_service
from app.modules.fsp import service as fsp_service
from app.modules.matching import service as matching_service
from app.modules.resume import parser
from app.modules.resume.models import Resume
from app.modules.resume.parser import ResumeDraft, ResumeParse
from app.modules.resume.pdf import (
    ProfileDocument,
    Variant,
    display_name,
    experience_for,
    fsp_lines,
    labels,
    pdf_filename,
    redact_contacts,
    render_pdf,
    skill_groups,
    topic_rows,
)
from app.modules.resume.schemas import ResumeParseResult
from app.modules.survey import service as survey_service
from app.modules.testing import service as testing_service

log = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
SCAN_WARNING = "В файле нет текстового слоя — похоже на скан. Заполните профиль вручную."
PAGES_WARNING = "Разобраны только первые {pages} страниц резюме."
EMPTY_WARNING = "Не нашли в резюме данных для профиля — проверьте и заполните форму вручную."

# Поля, которые резюме заполняет, только если в профиле они пустые
SCALAR_FIELDS = (
    "first_name",
    "last_name",
    "middle_name",
    "contact_email",
    "phone",
    "telegram",
    "city",
    "salary_min",
    "salary_max",
    "experience_years",
    "about",
)
LIST_FIELDS = ("work_formats", "roles", "industries_exp", "soft_skills")


class ResumeFileError(AppError):
    status_code = 422
    code = "invalid_resume_file"
    message = "Не удалось прочитать файл резюме"


# ---------- импорт ----------


def extract_text(content: bytes, max_pages: int) -> tuple[str, int]:
    """Текст PDF постранично (pdfplumber) и число страниц в файле."""
    try:
        with pdfplumber.open(io.BytesIO(content)) as document:
            pages = document.pages
            text = "\n".join((page.extract_text() or "") for page in pages[:max_pages])
            return text, len(pages)
    except Exception as exc:  # pdfminer бросает разные внутренние ошибки на битых файлах
        log.info("resume pdf is unreadable: %s", exc)
        raise ResumeFileError("Файл повреждён или это не PDF", code="invalid_pdf") from exc


def _store(candidate_id: int, content: bytes) -> str:
    """Сохраняет файл в upload_dir; в БД — полный путь (по нему файл удаляется вместе с аккаунтом)."""
    target = Path(get_settings().upload_dir) / "resumes" / str(candidate_id) / f"{uuid4().hex}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target.as_posix()


def _empty(value: object) -> bool:
    return value is None or value == "" or value == []


async def build_prefill(
    db: AsyncSession, candidate: Candidate, draft: ResumeDraft
) -> tuple[CandidateProfileUpdate, list[str]]:
    """Текущий профиль, дополненный резюме: заполненное кандидатом не перетирается, списки объединяются."""
    profile = await candidates_service.profile_out(db, candidate)
    prefill = CandidateProfileUpdate(
        **profile.model_dump(include=set(CandidateProfileBase.model_fields)),
        declared_skills=[
            DeclaredSkill(skill_id=skill.skill_id)
            for skill in profile.skills
            if SkillSource.declared in skill.sources
        ],
        experience=profile.experience,
    )
    filled: list[str] = []

    for name in SCALAR_FIELDS:
        value = getattr(draft, name)
        if not _empty(value) and _empty(getattr(prefill, name)):
            setattr(prefill, name, value)
            filled.append(name)
    if draft.relocation and not prefill.relocation:
        prefill.relocation = True
        filled.append("relocation")
    for name in LIST_FIELDS:
        current = list(getattr(prefill, name))
        added = [item for item in getattr(draft, name) if item not in current]
        if added:
            setattr(prefill, name, current + added)
            filled.append(name)

    declared = [item.skill_id for item in prefill.declared_skills]
    new_skills = [skill_id for skill_id in draft.skills if skill_id not in declared]
    if new_skills:
        prefill.declared_skills += [DeclaredSkill(skill_id=skill_id) for skill_id in new_skills]
        filled.append("declared_skills")

    known = {(item.company.lower(), item.position.lower()) for item in prefill.experience}
    new_jobs = [
        item for item in draft.experience if (item.company.lower(), item.position.lower()) not in known
    ]
    if new_jobs:
        prefill.experience += new_jobs
        filled.append("experience")
    # Повторная валидация: в форму уходит только то, что примет PUT /candidates/me
    return CandidateProfileUpdate.model_validate(prefill.model_dump()), filled


async def upload_resume(db: AsyncSession, user_id: int, file: UploadFile) -> ResumeParseResult:
    settings = get_settings()
    candidate = await candidates_service.get_by_user(db, user_id)
    content = await file.read(settings.resume_max_bytes + 1)
    if len(content) > settings.resume_max_bytes:
        size_mb = settings.resume_max_bytes // (1024 * 1024)
        raise ResumeFileError(f"Файл больше {size_mb} МБ", code="file_too_large")
    if not content.startswith(PDF_MAGIC):
        raise ResumeFileError("Нужен файл в формате PDF", code="not_pdf")

    text, pages = await run_in_threadpool(extract_text, content, settings.resume_max_pages)
    warnings: list[str] = []
    if pages > settings.resume_max_pages:
        warnings.append(PAGES_WARNING.format(pages=settings.resume_max_pages))
    if len(text.strip()) < settings.resume_min_text_chars:
        warnings.append(SCAN_WARNING)
        parsed = ResumeParse(draft=ResumeDraft())
    else:
        parsed = await parser.parse_resume_text(text, user_id=user_id)

    prefill, filled = await build_prefill(db, candidate, parsed.draft)
    if not filled and SCAN_WARNING not in warnings:
        warnings.append(EMPTY_WARNING)
    kind = ParserKind.llm if parsed.used_llm else ParserKind.dict
    file_path = await asyncio.to_thread(_store, candidate.id, content)
    resume = Resume(
        candidate_id=candidate.id,
        file_path=file_path,
        extracted_text=text,
        parsed={
            "draft": parsed.draft.model_dump(mode="json"),
            "unmapped_terms": parsed.unmapped_terms,
        },
        parser=kind,
    )
    db.add(resume)
    await db.commit()

    years = prefill.experience_years
    return ResumeParseResult(
        resume_id=resume.id,
        parser=kind,
        prefill=prefill,
        from_resume=filled,
        suggested_grade=survey_service.suggest_grade(years) if years is not None else None,
        unmapped_terms=parsed.unmapped_terms,
        warnings=warnings,
    )


# ---------- экспорт ----------


async def _render(document: ProfileDocument) -> tuple[bytes, str]:
    return await run_in_threadpool(render_pdf, document), pdf_filename(document)


async def own_document(db: AsyncSession, candidate: Candidate, variant: Variant) -> ProfileDocument:
    """PDF своего профиля: полная версия или та, что видит работодатель до контакта."""
    privacy = candidates_service.privacy_of(candidate)
    public = variant == "public"
    current = await categories_service.get_current(db, candidate.id)
    topics = []
    if current is not None and current.attempt_id is not None:
        try:
            result = await testing_service.result(db, candidate, current.attempt_id)
            topics = topic_rows(result.topic_scores)
        except ConflictError:
            topics = []
    verified, others = skill_groups(await candidates_service.skill_states(db, candidate.id))
    show_fsp = candidate.fsp_id is not None and (privacy.show_fsp or not public)
    ranks, achievements, competencies = fsp_lines(
        await fsp_service.profile(db, candidate) if show_fsp else None
    )
    profile = await candidates_service.profile_out(db, candidate)
    names = labels(
        list(candidate.roles or []), list(candidate.industries_exp or []), list(candidate.soft_skills or [])
    )
    contacts = await matching_service.contacts_of(db, candidate)
    return ProfileDocument(
        variant=variant,
        candidate_id=candidate.id,
        name=display_name(candidate.first_name, candidate.last_name, privacy.show_last_name)
        if public
        else contacts.full_name,
        category_label=categories_service.category_label(current.specialization, current.grade.value)
        if current
        else None,
        percentile=current.percentile if current else None,
        city=candidate.city,
        relocation=candidate.relocation,
        work_formats=list(candidate.work_formats or []),
        salary_min=candidate.salary_min if privacy.show_salary or not public else None,
        experience_years=float(candidate.experience_years)
        if candidate.experience_years is not None
        else None,
        contacts=None if public else contacts,
        topics=topics,
        verified_skills=verified,
        other_skills=others,
        fsp_ranks=ranks,
        fsp_achievements=achievements,
        fsp_competencies=competencies,
        experience=experience_for(profile.experience, variant),
        about=redact_contacts(candidate.about) if public else candidate.about,
        **names,
    )


async def own_profile_pdf(db: AsyncSession, user_id: int, variant: Variant) -> tuple[bytes, str]:
    candidate = await candidates_service.get_by_user(db, user_id)
    return await _render(await own_document(db, candidate, variant))


async def employer_document(db: AsyncSession, user_id: int, candidate_id: int) -> ProfileDocument:
    """PDF для работодателя строится из карточки кандидата — те же проверки доступа и обезличивание.

    Полная версия — только если карточка отдала контакты, то есть есть запись в contact_unlocks.
    """
    card = await matching_service.candidate_card(db, user_id, candidate_id, None)
    variant: Variant = "full" if card.contacts_unlocked and card.contacts is not None else "public"
    brief = card.brief
    verified, others = skill_groups(card.skills)
    ranks, achievements, competencies = fsp_lines(card.fsp)
    names = labels(card.roles, card.industries_exp, card.soft_skills)
    public = variant == "public"
    return ProfileDocument(
        variant=variant,
        candidate_id=brief.id,
        name=card.contacts.full_name if card.contacts and not public else brief.display_name,
        category_label=brief.category.label,
        percentile=brief.percentile,
        city=brief.city,
        relocation=brief.relocation,
        work_formats=[item.value for item in brief.work_formats],
        salary_min=brief.salary_min,
        experience_years=card.experience_years,
        contacts=None if public else card.contacts,
        topics=topic_rows(card.topic_scores),
        verified_skills=verified,
        other_skills=others,
        fsp_ranks=ranks,
        fsp_achievements=achievements,
        fsp_competencies=competencies,
        experience=experience_for(card.experience, variant),
        about=redact_contacts(card.about) if public else card.about,
        **names,
    )


async def employer_candidate_pdf(db: AsyncSession, user_id: int, candidate_id: int) -> tuple[bytes, str]:
    return await _render(await employer_document(db, user_id, candidate_id))
