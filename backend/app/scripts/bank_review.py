"""Отчёт для ревью банка заданий командой: каждый шаблон, его параметры и несколько экземпляров
с отмеченным верным ответом. Ключи берутся из тех же YAML, что лежат в репозитории, но готовый HTML
в git не попадает (bank-review/ в .gitignore) и публично не выкладывается.

Запуск: `cd backend && uv run python -m app.scripts.bank_review [--spec backend] [--samples 3]`.
Замечания ревьюер пишет прямо в отчёте; они сохраняются в браузере и выгружаются в CSV.
"""

import argparse
import html
from pathlib import Path

import yaml

from app.modules.testing.engine.bank import CONTENT_DIR, GRADE_ORDER, get_bank, get_blueprints
from app.modules.testing.engine.model import Template
from app.modules.testing.engine.render import render

GRADE_NAMES = {"intern": "Стажёр", "junior": "Junior", "middle": "Middle", "senior": "Senior"}
KIND_NAMES = {
    "single_choice": "один вариант",
    "multi_choice": "несколько вариантов",
    "numeric": "число",
    "ordering": "порядок",
    "code_output": "что выведет код",
    "open_approach": "открытый вопрос",
}

ASSETS = Path(__file__).with_name("bank_review_assets")


def _sources() -> dict[str, str]:
    sources = {}
    for path in sorted((CONTENT_DIR / "templates").rglob("*.yaml")):
        for raw in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            sources[raw["id"]] = str(path.relative_to(CONTENT_DIR.parent))
    return sources


def _level(b: float) -> str:
    cuts = get_blueprints().scale.cuts
    below = [grade for grade in GRADE_ORDER if cuts[grade] <= b]
    return f"уровень {GRADE_NAMES[below[-1]]}" if below else "ниже уровня стажёра"


def _instance(template: Template, seed: int) -> str:
    instance = render(template, seed)
    e = html.escape
    parts = [f'<div class="inst"><div class="small">seed {seed}</div><p>{e(instance.stem)}</p>']
    if instance.code:
        parts.append(f"<pre>{e(instance.code)}</pre>")
    key = instance.key
    if instance.kind == "ordering":
        texts = {option.id: option.text for option in instance.options}
        shown = "".join(f"<li>{e(option.text)}</li>" for option in instance.options)
        right = "".join(f"<li>{e(texts[option_id])}</li>" for option_id in key["order"])
        parts.append(f"<div class='small'>Показано:</div><ol>{shown}</ol>")
        parts.append(f"<div class='small'>Верный порядок:</div><ol class='ok-list'>{right}</ol>")
    elif instance.options:
        correct = set(key.get("choice_ids", []))
        items = "".join(
            f'<li class="{"ok" if option.id in correct else ""}">{e(option.text)}</li>'
            for option in instance.options
        )
        parts.append(f"<ol type='a'>{items}</ol>")
    if instance.kind == "numeric":
        tolerance = f" ± {key['tolerance']}" if key.get("tolerance") else ""
        number = key["number"]
        shown = int(number) if float(number).is_integer() else number
        parts.append(f"<p class='ok'>{e(str(shown))}{tolerance}</p>")
    if instance.kind == "open_approach":
        rubric = "".join(f"<li>{e(item)}</li>" for item in key["rubric"])
        parts.append(f"<div class='small'>Чек-лист:</div><ul>{rubric}</ul>")
    parts.append("</div>")
    return "".join(parts)


def _card(template: Template, source: str, samples: int) -> str:
    e = html.escape
    names = get_blueprints().topic_names
    status = f'<span class="tag pilot">{template.status}</span>' if template.status != "active" else ""
    meta = [
        f"<b>{e(template.id)}</b> v{template.version}",
        f'<span class="tag">{e(names.get(template.topic, template.topic))}</span>',
        f'<span class="tag">{KIND_NAMES.get(template.kind, template.kind)}</span>',
        f"b = {template.irt.b:+.2f} ({_level(template.irt.b)})",
        f"a = {template.irt.a:.2f}",
        f"{template.time_limit_sec} с",
        status,
    ]
    if template.stack_module:
        meta.insert(2, f'<span class="tag">{e(template.stack_module)}</span>')
    instances = "".join(_instance(template, seed) for seed in range(1, samples + 1))
    radios = "".join(
        f'<label class="state"><input type="radio" name="v-{e(template.id)}" value="{value}"> {text}</label>'
        for value, text in (("ok", "ок"), ("fix", "поправить"), ("drop", "убрать"))
    )
    return (
        f'<section class="card" data-id="{e(template.id)}" data-topic="{e(template.topic)}">'
        f'<div class="meta">{" ".join(meta)}</div>'
        f'<div class="small">{e(source)} · навыки: {e(", ".join(template.skills))}</div>'
        f'<div class="grid">{instances}</div><div style="margin-top:10px">{radios}</div>'
        '<textarea placeholder="Замечание: неоднозначно, два верных ответа, ошибка в коде…"></textarea>'
        "</section>"
    )


def build(spec: str, samples: int, out: Path) -> Path:
    templates = sorted(
        (t for t in get_bank().for_spec(spec) if t.status != "retired"),
        key=lambda t: (t.topic, t.irt.b, t.id),
    )
    sources = _sources()
    names = get_blueprints().topic_names
    topics = sorted({t.topic for t in templates}, key=lambda topic: names.get(topic, topic))
    options = "".join(f'<option value="{t}">{html.escape(names.get(t, t))}</option>' for t in topics)
    cards = "".join(_card(t, sources.get(t.id, "?"), samples) for t in templates)
    style = (ASSETS / "review.css").read_text(encoding="utf-8")
    script = (ASSETS / "review.js").read_text(encoding="utf-8")
    page = (
        f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Ревью банка: {spec}</title><style>{style}</style></head>"
        f'<body data-spec="{spec}"><header><h1>Банк заданий · {spec} · {len(templates)} шаблонов</h1>'
        f'<select id="filter"><option value="">Все темы</option>{options}</select>'
        f'<span class="small">Проверено: <b id="progress"></b></span>'
        f'<button id="export">Скачать замечания CSV</button></header>'
        f"<main>{cards}</main><script>{script}</script></body></html>"
    )
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{spec}.html"
    path.write_text(page, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", action="append", help="специализация; по умолчанию все")
    parser.add_argument("--samples", type=int, default=3, help="экземпляров на шаблон")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[3] / "bank-review")
    args = parser.parse_args()
    specs = args.spec or sorted(get_blueprints().specializations)
    for spec in specs:
        print(build(spec, args.samples, args.out))


if __name__ == "__main__":
    main()
