"""Вероятность принятия приглашения (§8.3.1) в API: работодателю — да, кандидату в «почему вы» — нет."""

from app.modules.matching import scoring
from tests.test_invitations import invite, make_candidate
from tests.test_needs import API, NEED, signup


async def test_acceptance_shown_to_employer_and_follows_decline_history(client, session):
    employer = await signup(client, "hr@bank.ru")
    candidate, cid = await make_candidate(
        client, session, "anna@example.com", search_status="active", salary_min=320_000
    )
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()

    listed = (await client.get(f"{API}/needs/{need['id']}/recommendations", headers=employer)).json()
    accept = listed["candidates"][0]["acceptance"]
    assert accept["level"] == "high" and accept["affects_score"] is False
    assert accept["text"].startswith("Вероятность, что кандидат примет приглашение: высокая — ")
    assert "кандидат активно ищет работу" in accept["text"]

    url = f"{API}/talent/candidates/{cid}?need_id={need['id']}"
    before = (await client.get(url, headers=employer)).json()["match"]["acceptance"]
    # Две другие компании получили отказ «зарплата», третья ждёт ответа
    for index in range(3):
        other = await signup(client, f"hr{index}@corp.ru")
        sent = (await client.post(f"{API}/invitations", json=invite(cid), headers=other)).json()
        if index < 2:
            declined = await client.post(
                f"{API}/invitations/{sent['id']}/decline", json={"reason": "salary"}, headers=candidate
            )
            assert declined.status_code == 200, declined.text
    after = (await client.get(url, headers=employer)).json()["match"]["acceptance"]
    # Вилка ниже ожиданий, отказы были из-за зарплаты — её эффект ×2; плюс чужое активное приглашение
    assert after["probability"] < before["probability"]
    assert (after["level"], after["probability"]) == ("medium", 0.587)
    assert "вилка ниже ожиданий (прошлые отказы — чаще из-за зарплаты)" in after["text"]

    # Своё приглашение работодатель видит статусом, «занятостью» кандидата оно не считается
    own = (
        await client.post(f"{API}/invitations", json=invite(cid, need_id=need["id"]), headers=employer)
    ).json()
    mine = (await client.get(url, headers=employer)).json()["match"]["acceptance"]
    assert mine["probability"] == after["probability"]

    inbox = (await client.get(f"{API}/candidates/me/invitations", headers=candidate)).json()
    why_you = next(item["why_you"] for item in inbox if item["id"] == own["id"])
    assert all("Вероятность" not in line["text"] for line in why_you["lines"])


async def test_acceptance_switch_off_hides_it(client, session, monkeypatch):
    employer = await signup(client, "hr@bank.ru")
    _, cid = await make_candidate(client, session, "anna@example.com")
    need = (await client.post(f"{API}/needs", json=NEED, headers=employer)).json()
    monkeypatch.setitem(scoring.get_rules().acceptance, "enabled", False)
    card = (await client.get(f"{API}/talent/candidates/{cid}?need_id={need['id']}", headers=employer)).json()
    assert card["match"]["acceptance"] is None
