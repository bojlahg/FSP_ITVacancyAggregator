import pytest

from app.modules.catalog.service import Catalog, get_catalog

API = "/api/v1/catalog"


def test_content_is_consistent():
    catalog = get_catalog()
    assert {spec.slug for spec in catalog.specializations if spec.has_test} == {
        "backend",
        "frontend",
        "qa",
        "devops",
        "data",
    }
    assert [grade.slug.value for grade in sorted(catalog.grades, key=lambda g: g.order)] == [
        "intern",
        "junior",
        "middle",
        "senior",
    ]
    assert len(catalog.skills) >= 140
    assert set(catalog.rules.fsp.rank_floor) == set(catalog.rules.fsp.rank_order)


def test_broken_reference_is_rejected():
    data = get_catalog().model_dump()
    data["skills"][0]["parent"] = "no_such_skill"
    with pytest.raises(ValueError, match="unknown parent"):
        Catalog.model_validate(data)


def test_alias_collision_is_rejected():
    data = get_catalog().model_dump()
    data["skills"][1]["aliases"].append(data["skills"][0]["id"])
    with pytest.raises(ValueError, match="alias"):
        Catalog.model_validate(data)


async def test_skills_search_by_alias(client):
    response = await client.get(f"{API}/skills", params={"q": "постгрес"})
    assert response.status_code == 200
    assert [skill["id"] for skill in response.json()] == ["postgresql"]


async def test_catalog_endpoints_are_public(client):
    for path in ("specializations", "grades", "industries", "soft-skills", "team-roles"):
        response = await client.get(f"{API}/{path}")
        assert response.status_code == 200, path
        assert response.json(), path
