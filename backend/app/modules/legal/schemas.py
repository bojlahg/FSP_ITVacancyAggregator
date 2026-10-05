from typing import Literal

from pydantic import Field

from app.core.schemas import ApiModel

LegalSlug = Literal["recommendations", "privacy", "consent-pd", "consent-publication"]


class LegalTable(ApiModel):
    columns: list[str]
    rows: list[list[str]]


class LegalSection(ApiModel):
    heading: str
    paragraphs: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    table: LegalTable | None = None


class LegalDocumentRef(ApiModel):
    slug: LegalSlug
    title: str


class LegalDocument(LegalDocumentRef):
    version: str = Field(description="Редакция текста; та же строка пишется в consents.policy_version")
    summary: str
    sections: list[LegalSection]
