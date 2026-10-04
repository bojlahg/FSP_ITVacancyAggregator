"""Рендер экземпляра задания из шаблона по seed (§10.2): свои числа, имена, порядок и дистракторы."""

import random
import string

from app.modules.testing.engine.expressions import evaluate, substitute
from app.modules.testing.engine.generators import load_all
from app.modules.testing.engine.model import CHOICE_KINDS, Generated, Instance, Option, Template


def _rng(template: Template, seed: int) -> random.Random:
    return random.Random(f"{template.id}:{template.version}:{seed}")


def _params(template: Template, rng: random.Random) -> dict:
    values = {}
    for name, spec in template.params.items():
        if spec.choice is not None:
            values[name] = rng.choice(spec.choice)
        else:
            low, high = spec.int_range
            values[name] = rng.randrange(low, high + 1, spec.step)
    return values


def _with_ids(texts: list[str]) -> tuple[Option, ...]:
    return tuple(Option(id=string.ascii_lowercase[index], text=text) for index, text in enumerate(texts))


def _choice_options(
    template: Template, rng: random.Random, correct_pool: list[str], wrong_pool: list[str]
) -> tuple[tuple[Option, ...], list[str]]:
    if template.kind == "multi_choice":
        count = rng.randint(2, min(len(correct_pool), template.n_options - 1))
    else:
        count = 1
    correct = rng.sample(correct_pool, count)
    wrong_needed = template.n_options - count
    wrong = rng.sample(wrong_pool, min(wrong_needed, len(wrong_pool)))
    texts = correct + wrong
    if len(set(texts)) != len(texts):
        raise ValueError(f"{template.id}: варианты ответа совпадают после подстановки")
    rng.shuffle(texts)
    options = _with_ids(texts)
    key = sorted(option.id for option in options if option.text in correct)
    return options, key


def render(template: Template, seed: int) -> Instance:
    rng = _rng(template, seed)
    params = _params(template, rng)
    generated: Generated | None = None
    if template.generator:
        generated = load_all()[template.generator](rng)
        stem, code, language = generated.stem, generated.code, generated.code_language
    else:
        stem = substitute(rng.choice(template.stem_variants or [template.stem]), params)
        code = substitute(template.code, params) if template.code else None
        language = template.code_language

    options: tuple[Option, ...] = ()
    key: dict = {}
    if template.kind in CHOICE_KINDS:
        if generated is not None:
            correct_pool, wrong_pool = list(generated.correct), list(generated.wrong)
        else:
            correct_pool = [substitute(text, params) for text in template.options.correct]
            wrong_pool = [substitute(text, params) for text in template.options.wrong]
        # Дистрактор не может совпадать с верным ответом (например, после подстановки чисел)
        wrong_pool = [text for text in dict.fromkeys(wrong_pool) if text not in correct_pool]
        options, choice_key = _choice_options(template, rng, correct_pool, wrong_pool)
        key = {"choice_ids": choice_key}
    elif template.kind == "ordering":
        items = (
            list(generated.order_items)
            if generated
            else [substitute(t, params) for t in template.order_items]
        )
        shuffled = items[:]
        for _ in range(10):
            rng.shuffle(shuffled)
            if shuffled != items:
                break
        options = _with_ids(shuffled)
        by_text = {option.text: option.id for option in options}
        key = {"order": [by_text[text] for text in items]}
    elif template.kind == "numeric":
        if generated is not None:
            key = {"number": generated.number, "tolerance": generated.tolerance}
        else:
            key = {"number": evaluate(template.answer.expr, params), "tolerance": template.answer.tolerance}
    elif template.kind == "open_approach":
        key = {"rubric": list(template.rubric)}

    return Instance(
        template_id=template.id,
        version=template.version,
        kind=template.kind,
        topic=template.topic,
        skills=tuple(template.skills),
        stem=stem,
        code=code,
        code_language=language,
        options=options,
        time_limit_sec=template.time_limit_sec,
        max_length=template.max_length if template.kind == "open_approach" else None,
        key=key,
    )
