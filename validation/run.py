"""Процедура валидации (§12): `make validate` или `cd backend && uv run python ../validation/run.py`.

Пишет docs/validation/report.md, metrics.json и PNG-графики. Результат детерминирован по seed.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import yaml  # noqa: E402

DEFAULT_CONFIG = ROOT / "validation" / "config.yaml"
DEFAULT_OUT = ROOT / "docs" / "validation"


def load_config(path: Path = DEFAULT_CONFIG, size: int | None = None, seed: int | None = None) -> dict:
    with path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if size is not None:
        config["population"]["size"] = size
    if seed is not None:
        config["seed"] = seed
    return config


def main() -> None:
    from validation.report import write_report
    from validation.simulate import run_validation

    parser = argparse.ArgumentParser(description="Симуляционная валидация тестирования и подбора ITScout")
    parser.add_argument("--size", type=int, help="размер популяции (по умолчанию из config.yaml)")
    parser.add_argument("--seed", type=int, help="seed (по умолчанию из config.yaml)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    config = load_config(args.config, args.size, args.seed)
    results = run_validation(config)
    report = write_report(results, args.out)
    print(f"отчёт: {report}")


if __name__ == "__main__":
    main()
