from app.modules.catalog.service import get_catalog
from app.modules.testing.engine.bank import coverage, get_blueprints, load_bank, validate_bank
from app.modules.testing.engine.expressions import plural, substitute
from app.modules.testing.engine.render import render


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


def test_plural_forms_golden():
    forms = ("повтор", "повтора", "повторов")
    expected = {0: "повторов", 1: "повтор", 2: "повтора", 4: "повтора", 5: "повторов", 11: "повторов"}
    expected |= {12: "повторов", 14: "повторов", 21: "повтор", 22: "повтора", 101: "повтор", 111: "повторов"}
    assert {n: plural(n, *forms) for n in expected} == expected


def test_substitute_plural_placeholder_and_angular_pipe():
    params = {"n": 3, "items": "invoices"}
    assert substitute("до {{n|раза|раз|раз}}", params) == "до 3 раз"
    assert substitute("{{n|задача|задачи|задач}}", {"n": 21}) == "21 задача"
    # пайп Angular в тексте задания — не форма числа: латиница после | не подставляется
    assert substitute("{{ items | activeOnly: field }} и {{items}}", params) == (
        "{{ items | activeOnly: field }} и invoices"
    )


def test_reported_template_defects_are_gone():
    """Замечания с прода: согласование числа, падеж подстановки, случайный метод, опечатка O(n·k)."""
    bank = load_bank().templates
    seeds = range(200)
    retry = {render(bank["be.http.retry_budget"], seed).stem for seed in seeds}
    assert not any("повторов" in stem for stem in retry)
    conflict = {render(bank["be.http.status_codes_conflict"], seed).stem for seed in seeds}
    assert not any("команду с таким" in stem or "компанию с таким" in stem for stem in conflict)
    random_pairs = ("DELETE /login", "POST /health", "HEAD /login", "POST /static")
    for template_id in ("be.http.request_path_order", "ops.net.request_lifecycle"):
        texts = {o.text for seed in seeds for o in render(bank[template_id], seed).options}
        assert not any(pair in text for text in texts for pair in random_pairs)
    complexity = bank["be.algo.doubling_loop_complexity"]
    options = {o.text for seed in seeds for o in render(complexity, seed).options}
    assert not any(text.startswith(("O(n·", "O(n^")) for text in options)
