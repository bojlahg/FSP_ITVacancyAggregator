"""Определение специализации по опросу (§6.2, §12.2 «Категоризация») на синтетических ответах.

Расчёт — продуктовая функция survey.service.score_specializations (чистая функция над survey.yaml).
"""

import random

from app.modules.survey.service import score_specializations, survey_config
from seed import data
from validation.population import Person
from validation.stats import share


def _options(question_id: str) -> list[str]:
    question = next(q for q in survey_config()["questions"] if q["id"] == question_id)
    return [option["id"] for option in question.get("options", [])]


def synthetic_answers(person: Person, rng: random.Random, cfg: dict) -> dict:
    """Типичные ответы специализации плюс шум: нетипичная работа, второй вид работы, другой язык."""
    daily = [data.SPEC_DAILY[person.spec]]
    if rng.random() < cfg["atypical"]:
        daily = [rng.choice([o for o in _options("daily_work") if o not in daily])]
    if rng.random() < cfg["extra_daily"]:
        daily.append(rng.choice([o for o in _options("daily_work") if o not in daily]))
    favorite = [data.SPEC_FAVORITE[person.spec]]
    if rng.random() < cfg["extra_favorite"]:
        favorite.append(rng.choice([o for o in _options("favorite_tasks") if o not in favorite]))
    language = data.MODULE_LANGUAGE[person.module]
    if rng.random() < cfg["other_language"]:
        language = rng.choice(_options("main_language"))
    return {
        "daily_work": daily,
        "favorite_tasks": favorite,
        "main_language": language,
        "stack": list(person.resume_stack),
    }


def evaluate_survey(people: list[Person], config: dict) -> dict:
    rng = random.Random(f"survey:{config['seed']}")
    top1, top2 = [], []
    by_spec: dict[str, list[bool]] = {}
    for person in people:
        scores = score_specializations(synthetic_answers(person, rng, config["survey"]))
        ranked = sorted(scores, key=lambda spec: (-scores[spec], spec))
        hit = bool(ranked) and ranked[0] == person.spec
        top1.append(hit)
        top2.append(person.spec in ranked[:2])
        by_spec.setdefault(person.spec, []).append(hit)
    return {
        "top1": share(top1),
        "top2": share(top2),
        "by_spec": {spec: share(hits) for spec, hits in sorted(by_spec.items())},
        "n": len(people),
    }
