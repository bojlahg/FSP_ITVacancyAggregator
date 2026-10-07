import pytest

from app.core.enums import Grade
from app.modules.catalog.service import get_catalog
from app.modules.survey.service import suggest_grade, survey_config


# Golden-кейсы подсказки грейда по стажу, границы — grade_hint в content/survey.yaml (§6.2)
@pytest.mark.parametrize(
    ("years", "grade"),
    [
        (None, Grade.intern),
        (0, Grade.intern),
        (0.4, Grade.intern),
        (0.5, Grade.junior),
        (1, Grade.junior),
        (1.9, Grade.junior),
        (2, Grade.middle),
        (3, Grade.middle),
        (4.9, Grade.middle),
        (5, Grade.senior),
        (12, Grade.senior),
    ],
)
def test_suggest_grade_by_experience(years: float | None, grade: Grade) -> None:
    assert suggest_grade(years) == grade


def test_grade_hint_covers_every_grade_in_order() -> None:
    rules = survey_config()["grade_hint"]
    order = {grade.slug.value: grade.order for grade in get_catalog().grades}
    assert [rule["grade"] for rule in rules] == sorted(order, key=order.get)
    bounds = [rule["max_years"] for rule in rules]
    assert bounds == sorted(bounds)
