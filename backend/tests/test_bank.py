from app.modules.catalog.service import get_catalog
from app.modules.testing.engine.bank import coverage, get_blueprints, load_bank, validate_bank


def test_bank_is_valid():
    errors = validate_bank(load_bank(), get_blueprints(), {skill.id for skill in get_catalog().skills})
    assert not errors, "\n".join(errors)


def test_blueprint_topic_quotas_match_mode_lengths():
    blueprints = get_blueprints()
    full = blueprints.modes["full"]
    for spec, blueprint in blueprints.specializations.items():
        assert sum(blueprint.topics.values()) == full.stage1_items + full.stage2_items, spec


def test_bank_covers_every_blueprint_topic():
    blueprints = get_blueprints()
    missing = [
        f"{spec}.{topic}"
        for spec, counts in coverage(load_bank(), blueprints).items()
        for topic in blueprints.specializations[spec].topics
        if counts[topic] == 0
    ]
    # Пока банк наполняется, покрытие проверяется только для специализаций, где шаблоны уже есть
    started = {
        spec for spec, counts in coverage(load_bank(), blueprints).items() if sum(counts.values()) >= 30
    }
    assert not [item for item in missing if item.split(".")[0] in started], missing
