"""Mock реестра ФСП. Реальные API и структура данных ФСП не предоставлены — это наша модель (§9.1).

Данные читаются из JSON, который генерирует backend/seed (T07). В проде сервис заменяется реестром ФСП.
"""

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    fsp_api_key: str = "dev-fsp-key"
    # Локально — .data/fsp.json в корне репо (его пишет генератор демо-данных), в контейнере — из compose
    fsp_data_path: str = str(Path(__file__).resolve().parents[2] / ".data" / "fsp.json")


class Participant(BaseModel):
    fsp_id: str
    full_name: str
    birth_year: int | None = None
    region: str | None = None


class Competition(BaseModel):
    id: str
    name: str
    discipline: Literal["algorithmic", "product", "infosec", "drones", "robotics"]
    level: Literal["international", "national", "interregional", "regional", "municipal"]
    format: Literal["individual", "team"]
    held_on: date
    participants_count: int
    organizer: str | None = None


class Result(BaseModel):
    id: str
    fsp_id: str
    competition_id: str
    team_name: str | None = None
    team_role: str | None = None
    place: int
    score: float | None = None
    prize: Literal["winner", "prize", "participant"] = "participant"


class Rank(BaseModel):
    fsp_id: str
    discipline: str
    rank: Literal["III", "II", "I", "КМС", "МС"]
    awarded_at: date


class Dataset(BaseModel):
    participants: list[Participant] = []
    competitions: list[Competition] = []
    results: list[Result] = []
    ranks: list[Rank] = []


class ResultWithCompetition(Result):
    competition: Competition


@lru_cache
def get_settings() -> Settings:
    return Settings()


_cache: dict[str, tuple[float, Dataset]] = {}


def load_dataset() -> Dataset:
    """Перечитывает файл при изменении: backend перезаписывает его при reseed демо-данных."""
    path = Path(get_settings().fsp_data_path)
    if not path.exists():
        return Dataset()
    mtime = path.stat().st_mtime
    cached = _cache.get(str(path))
    if cached is None or cached[0] != mtime:
        cached = (mtime, Dataset.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        _cache[str(path)] = cached
    return cached[1]


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if x_api_key != get_settings().fsp_api_key:
        raise HTTPException(status_code=401, detail="invalid api key")


app = FastAPI(
    title="FSP Registry Mock",
    version="0.1.0",
    description="Mock реестра Федерации спортивного программирования для ITScout.",
    docs_url="/fsp-api/docs",
    openapi_url="/fsp-api/openapi.json",
)


@app.get("/health", tags=["service"])
def health() -> dict[str, object]:
    data = load_dataset()
    return {"status": "ok", "participants": len(data.participants)}


def _participant_or_404(fsp_id: str) -> Participant:
    for participant in load_dataset().participants:
        if participant.fsp_id == fsp_id:
            return participant
    raise HTTPException(status_code=404, detail="participant not found")


PREFIX = "/fsp-api/v1"
SECURED = [Depends(require_api_key)]


@app.get(f"{PREFIX}/participants/{{fsp_id}}", response_model=Participant, dependencies=SECURED)
def get_participant(fsp_id: str) -> Participant:
    return _participant_or_404(fsp_id)


@app.get(
    f"{PREFIX}/participants/{{fsp_id}}/results",
    response_model=list[ResultWithCompetition],
    dependencies=SECURED,
)
def get_results(fsp_id: str) -> list[ResultWithCompetition]:
    _participant_or_404(fsp_id)
    data = load_dataset()
    competitions = {competition.id: competition for competition in data.competitions}
    return [
        ResultWithCompetition(**result.model_dump(), competition=competitions[result.competition_id])
        for result in data.results
        if result.fsp_id == fsp_id
    ]


@app.get(f"{PREFIX}/participants/{{fsp_id}}/ranks", response_model=list[Rank], dependencies=SECURED)
def get_ranks(fsp_id: str) -> list[Rank]:
    _participant_or_404(fsp_id)
    return [rank for rank in load_dataset().ranks if rank.fsp_id == fsp_id]


@app.get(f"{PREFIX}/competitions", response_model=list[Competition], dependencies=SECURED)
def list_competitions() -> list[Competition]:
    return load_dataset().competitions
