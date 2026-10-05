"""«Как определён грейд» и возражения против категории (152-ФЗ ст. 16, §13.1): доступ и правила."""

from sqlalchemy import select

from app.core.enums import Role
from app.core.security import hash_password
from app.modules.appeals.models import GradeAppeal
from app.modules.auth.models import User
from app.modules.categories.models import CandidateCategory
from tests.conftest import bearer
from tests.test_invitations import make_candidate
from tests.test_needs import API, signup

COMMENT = {"comment": "Считаю, что тест занизил грейд: задания по базам данных были не по моему стеку"}


async def make_admin(session) -> dict[str, str]:
    admin = User(email="admin@itscout.ru", password_hash=hash_password("password-123"), role=Role.admin)
    session.add(admin)
    await session.commit()
    return bearer(Role.admin, admin.id)


async def test_grade_explanation_shows_test_decision(client, session):
    fresh = await signup(client, "new@example.com", role="candidate")
    empty = await client.get(f"{API}/candidates/me/grade-explanation", headers=fresh)
    assert empty.status_code == 200 and empty.json() == {"current": None}

    candidate, _ = await make_candidate(client, session, "anna@example.com")
    body = (await client.get(f"{API}/candidates/me/grade-explanation", headers=candidate)).json()["current"]
    assert body["category"]["label"] == "Backend · Middle"
    assert body["theta"] == 0.8 and body["cut"] == 0.2
    assert body["next_grade"] == "senior" and body["next_cut"] == 1.2
    employer = await signup(client, "hr@bank.ru")
    assert (await client.get(f"{API}/candidates/me/grade-explanation", headers=employer)).status_code == 403


async def test_candidate_appeals_once_per_category_and_sees_only_own(client, session):
    anna, anna_id = await make_candidate(client, session, "anna@example.com")
    boris, _ = await make_candidate(client, session, "boris@example.com")
    newbie = await signup(client, "new@example.com", role="candidate")

    created = await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=anna)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "open" and created.json()["category"]["grade"] == "middle"

    again = await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=anna)
    assert again.status_code == 409 and again.json()["error"]["code"] == "appeal_already_open"
    no_category = await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=newbie)
    assert no_category.status_code == 409 and no_category.json()["error"]["code"] == "no_category"
    short = await client.post(f"{API}/candidates/me/appeals", json={"comment": "не так"}, headers=boris)
    assert short.status_code == 422

    assert [
        item["id"] for item in (await client.get(f"{API}/candidates/me/appeals", headers=anna)).json()
    ] == [created.json()["id"]]
    assert (await client.get(f"{API}/candidates/me/appeals", headers=boris)).json() == []
    employer = await signup(client, "hr@bank.ru")
    assert (await client.get(f"{API}/candidates/me/appeals", headers=employer)).status_code == 403
    assert (
        await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=employer)
    ).status_code == 403
    rows = list(await session.scalars(select(GradeAppeal)))
    assert [row.candidate_id for row in rows] == [anna_id]


async def test_admin_endpoints_forbidden_for_other_roles(client, session):
    candidate, _ = await make_candidate(client, session, "anna@example.com")
    appeal = (await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=candidate)).json()
    employer = await signup(client, "hr@bank.ru")

    for headers in (candidate, employer, bearer(Role.expert)):
        assert (await client.get(f"{API}/admin/appeals", headers=headers)).status_code == 403
        resolved = await client.post(
            f"{API}/admin/appeals/{appeal['id']}/resolve", json={"reply": "ок"}, headers=headers
        )
        assert resolved.status_code == 403
    assert (await client.get(f"{API}/admin/appeals")).status_code == 401


async def test_admin_resolves_appeal_without_changing_grade(client, session):
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    admin = await make_admin(session)
    appeal = (await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=candidate)).json()

    listed = (await client.get(f"{API}/admin/appeals?status=open", headers=admin)).json()
    assert [item["id"] for item in listed] == [appeal["id"]]
    assert listed[0]["candidate_name"] == "Анна Ковалёва" and listed[0]["category_is_current"] is True

    reply = {"reply": "Проверили задания попытки: ошибок в ключах нет. Пересдать можно через 90 дней."}
    resolved = await client.post(f"{API}/admin/appeals/{appeal['id']}/resolve", json=reply, headers=admin)
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved" and resolved.json()["reply"] == reply["reply"]
    assert (await client.get(f"{API}/admin/appeals?status=open", headers=admin)).json() == []

    twice = await client.post(f"{API}/admin/appeals/{appeal['id']}/resolve", json=reply, headers=admin)
    assert twice.status_code == 409 and twice.json()["error"]["code"] == "appeal_already_resolved"
    missing = await client.post(f"{API}/admin/appeals/999999/resolve", json=reply, headers=admin)
    assert missing.status_code == 404

    own = (await client.get(f"{API}/candidates/me/appeals", headers=candidate)).json()
    assert own[0]["reply"] == reply["reply"]
    session.expire_all()
    current = await session.scalar(
        select(CandidateCategory).where(CandidateCategory.candidate_id == cid, CandidateCategory.is_current)
    )
    assert current.grade.value == "middle" and current.theta == 0.8, "ответ на обращение грейд не меняет"
    # После ответа по той же категории можно обратиться снова
    reopened = await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=candidate)
    assert reopened.status_code == 201


async def test_delete_account_removes_appeals(client, session):
    candidate, cid = await make_candidate(client, session, "anna@example.com")
    await client.post(f"{API}/candidates/me/appeals", json=COMMENT, headers=candidate)

    assert (await client.delete(f"{API}/candidates/me", headers=candidate)).status_code == 200
    assert await session.scalar(select(GradeAppeal.id).where(GradeAppeal.candidate_id == cid)) is None
