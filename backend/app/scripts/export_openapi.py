"""Выгружает OpenAPI-спецификацию в backend/openapi.json — из неё генерируется клиент фронта."""

import json
import sys
from pathlib import Path

from app.main import app

OUTPUT = Path(__file__).resolve().parents[2] / "openapi.json"


def main() -> None:
    spec = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != spec:
            sys.exit("openapi.json устарел: выполните `make openapi` и закоммитьте результат")
        return
    OUTPUT.write_text(spec, encoding="utf-8", newline="\n")
    print(f"written {OUTPUT}")


if __name__ == "__main__":
    main()
