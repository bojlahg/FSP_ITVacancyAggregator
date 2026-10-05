"""Ручная привязка ФСП ID не доказывает владение: в score не идёт без FSP_MANUAL_LINK_COUNTS (§9.3)."""

import pytest
from sqlalchemy import update

from app.core.config import get_settings
from app.core.enums import FspLinkMethod
from app.modules.candidates.models import Candidate
from app.modules.fsp import service as fsp_service
from app.modules.matching import service as matching_service
from app.modules.matching.models import CandidateSearchIndex
from tests.test_fsp_oidc import REGISTRY
from tests.test_invitations import make_candidate


async def _index_with_fsp(client, session, method: FspLinkMethod) -> CandidateSearchIndex:
    _, cid = await make_candidate(client, session, "anna@example.com")
    await session.execute(
        update(Candidate).where(Candidate.id == cid).values(fsp_id="FSP-2026-7781", fsp_link_method=method)
    )
    candidate = await session.get(Candidate, cid)
    await fsp_service.store_evidence(session, candidate, *REGISTRY["FSP-2026-7781"])
    await matching_service.refresh_candidate(session, cid)
    await session.commit()
    row = await session.get(CandidateSearchIndex, cid)
    await session.refresh(row)
    return row


async def test_oidc_link_counts(client, session):
    row = await _index_with_fsp(client, session, FspLinkMethod.oidc)
    assert row.has_fsp and row.fsp_score > 0


async def test_manual_link_is_shown_but_not_scored(client, session):
    row = await _index_with_fsp(client, session, FspLinkMethod.manual)
    assert row.has_fsp, "достижения остаются видны"
    assert row.fsp_score == 0.0
    assert "fsp_confirmed" not in (row.skills_status or {}).values()
    best = await matching_service._best_fsp(session, [row.candidate_id])
    assert best[row.candidate_id].endswith("владение не подтверждено, в score не учтено")


async def test_manual_link_counts_when_enabled(client, session, monkeypatch):
    monkeypatch.setattr(get_settings(), "fsp_manual_link_counts", True)
    row = await _index_with_fsp(client, session, FspLinkMethod.manual)
    assert row.fsp_score > 0


@pytest.mark.parametrize(
    ("method", "enabled", "expected"),
    [
        (FspLinkMethod.oidc, False, True),
        (FspLinkMethod.manual, False, False),
        (FspLinkMethod.manual, True, True),
        (None, True, False),
    ],
)
def test_counts_in_score(monkeypatch, method, enabled, expected):
    monkeypatch.setattr(get_settings(), "fsp_manual_link_counts", enabled)
    assert fsp_service.counts_in_score(Candidate(fsp_link_method=method)) is expected
