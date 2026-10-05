"""Юридические документы (§13.1): тексты собираются, числа в правилах рекомендаций — из весов подбора."""

import re

from app.core.config import get_settings
from app.modules.legal import service
from app.modules.matching.scoring import get_rules

API = "/api/v1"


async def test_documents_list_and_render_without_login(client):
    listed = await client.get(f"{API}/legal/documents")
    assert listed.status_code == 200
    slugs = [item["slug"] for item in listed.json()]
    assert slugs == ["recommendations", "privacy", "consent-pd", "consent-publication"]
    for slug in slugs:
        response = await client.get(f"{API}/legal/documents/{slug}")
        assert response.status_code == 200, slug
        body = response.json()
        assert body["version"] == get_settings().policy_version and body["sections"]
        assert not re.search(r"\{[a-z_]+\}", response.text), "плейсхолдер не подставлен"


async def test_unknown_document_is_404(client):
    response = await client.get(f"{API}/legal/documents/terms")
    assert response.status_code == 404 and response.json()["error"]["code"] == "legal_document_not_found"


def test_recommendation_rules_cite_actual_weights():
    doc = service.get_document("recommendations")
    table = next(section.table for section in doc.sections if section.table)
    weights = {row[0]: row[1] for row in table.rows}
    rules = get_rules().weights
    assert weights["Навыки"] == f"{rules['skills']:.2f}".replace(".", ",")
    assert weights["Условия"] == f"{rules['conditions']:.2f}".replace(".", ",")
    assert len(table.rows) == len(rules), "в правилах описан каждый компонент score"


def test_consents_name_llm_processor_and_fsp_source():
    pd = service.get_document("consent-pd")
    text = " ".join(" ".join(s.paragraphs + s.items) for s in pd.sections)
    assert "Yandex AI Studio" in text and "реестра Федерации спортивного программирования" in text
    publication = service.get_document("consent-publication")
    assert "10.1" in publication.summary
