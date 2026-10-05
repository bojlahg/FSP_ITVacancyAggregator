"""Восстановление параметров шаблонов из симулированных ответов (§12.2 «Калибровка»).

Так же калибруются пилотные слоты в продукте: параметры остальных шаблонов попытки считаются известными,
апостериорное распределение θ кандидата строится по ним (без самого шаблона), а a и b шаблона
находятся максимизацией маргинального правдоподобия его ответов (fixed-parameter calibration, MML).
"""

from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

from app.modules.testing.engine.bank import Bank
from app.modules.testing.engine.irt import GRID, PRIOR, probability
from validation.engine_sim import Attempt


def _posteriors(attempt: Attempt, bank: Bank) -> list[tuple[str, np.ndarray, float]]:
    """(шаблон, апостериор θ без этого шаблона, ответ) по каждому ответу попытки, включая пилотные."""
    answered = [item for item in attempt.items if item.score is not None]
    logs = []
    for item in answered:
        t = bank.templates[item.template_id]
        p = np.clip(probability(GRID, t.irt.a, t.irt.b, t.guessing), 1e-9, 1 - 1e-9)
        logs.append(item.score * np.log(p) + (1 - item.score) * np.log(1 - p))
    operational = [log for item, log in zip(answered, logs, strict=True) if item.scored]
    total = np.log(PRIOR) + (np.sum(operational, axis=0) if operational else 0.0)
    result = []
    for item, log in zip(answered, logs, strict=True):
        loo = total - log if item.scored else total
        weights = np.exp(loo - loo.max())
        result.append((item.template_id, weights / weights.sum(), float(item.score)))
    return result


def _fit(weights: np.ndarray, scores: np.ndarray, c: float, a_bounds, b_bounds) -> tuple[float, float]:
    def loss(params: np.ndarray) -> float:
        a, b = params
        p = np.clip(weights @ probability(GRID, a, b, c), 1e-9, 1 - 1e-9)
        return -float(np.sum(scores * np.log(p) + (1 - scores) * np.log(1 - p)))

    result = minimize(loss, x0=np.array([1.0, 0.0]), method="L-BFGS-B", bounds=[a_bounds, b_bounds])
    return float(result.x[0]), float(result.x[1])


def recover(attempts: list[Attempt], bank: Bank, config: dict) -> list[dict]:
    cfg = config["calibration"]
    per_template: dict[str, list[tuple[np.ndarray, float]]] = defaultdict(list)
    for attempt in attempts:
        for template_id, weights, score in _posteriors(attempt, bank):
            per_template[template_id].append((weights, score))
    rows = []
    for template_id in sorted(per_template):
        responses = per_template[template_id]
        if len(responses) < cfg["min_responses"]:
            continue
        template = bank.templates[template_id]
        weights = np.array([w for w, _ in responses])
        scores = np.array([s for _, s in responses])
        a_hat, b_hat = _fit(
            weights, scores, template.guessing, tuple(cfg["a_bounds"]), tuple(cfg["b_bounds"])
        )
        rows.append(
            {
                "template_id": template_id,
                "status": template.status,
                "n": len(responses),
                "a": template.irt.a,
                "b": template.irt.b,
                "a_hat": a_hat,
                "b_hat": b_hat,
            }
        )
    return rows
