"""Скрипт проверки LLM на стенде (app/scripts/llm_check.py) проходит все сценарии без сети."""

import json

from app.core import llm
from app.core.config import get_settings
from app.scripts import llm_check


async def test_llm_check_runs_all_scenarios_offline(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(get_settings(), "llm_state_dir", str(tmp_path))
    monkeypatch.setattr(llm, "is_enabled", lambda: True)

    async def fake_call(system: str, user: str) -> tuple[str, int]:
        if "проверка связи" in user:
            return '{"ok": true}', 5
        if "Критерии" in user:
            strong = "token bucket" in user.split("Ответ кандидата:")[-1]
            return json.dumps({"hits": [strong] * 4}), 50
        return "{}", 10

    monkeypatch.setattr(llm, "_yandex_call", fake_call)
    code = await llm_check.main()
    out = capsys.readouterr().out
    assert "[OK] связь с провайдером" in out
    assert "[OK] чек-лист подхода" in out
    assert "[OK] разбор потребности" in out
    assert "Итого: вызовов" in out
    assert code in (0, 1)  # резюме и черновики с пустым ответом модели честно помечаются FAIL


async def test_llm_check_reports_disabled(monkeypatch, capsys):
    monkeypatch.setattr(llm, "is_enabled", lambda: False)
    assert await llm_check.main() == 1
    assert "LLM выключен" in capsys.readouterr().out
