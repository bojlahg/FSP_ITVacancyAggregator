"""Служебные действия демо-режима."""

import asyncio
import sys
import time
import uuid
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.core.errors import AppError, ConflictError
from app.core.schemas import MessageResponse

BACKEND_DIR = Path(__file__).resolve().parents[3]
# Ключ advisory-блокировки Postgres: общий для всех процессов uvicorn, в отличие от asyncio.Lock
RESEED_LOCK_KEY = 7_340_201


async def _backup_before_reseed() -> None:
    """Бэкап снимает сервис backup (у backend нет pg_dump нужной версии): запрос — файлом в общем томе.

    Без BACKUP_REQUESTS_DIR (локальная разработка) шаг пропускается.
    """
    settings = get_settings()
    if not settings.backup_requests_dir:
        return
    folder = Path(settings.backup_requests_dir)
    request = folder / f"{uuid.uuid4().hex}.request"
    request.write_text(str(time.time()))
    deadline = time.monotonic() + settings.backup_request_timeout_seconds
    try:
        while time.monotonic() < deadline:
            if request.with_suffix(".ok").exists():
                return
            if request.with_suffix(".failed").exists():
                raise AppError("Бэкап перед пересозданием не удался, данные не тронуты", code="backup_failed")
            await asyncio.sleep(1)
        raise AppError("Сервис бэкапов не ответил — данные не тронуты", code="backup_failed")
    finally:
        for path in (request, request.with_suffix(".ok"), request.with_suffix(".failed")):
            path.unlink(missing_ok=True)


async def reseed() -> MessageResponse:
    """Генератор — отдельный процесс: он считает ~40 с и не должен блокировать event loop API."""
    async with engine.connect() as connection:
        locked = await connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": RESEED_LOCK_KEY})
        if not locked:
            raise ConflictError("Демо-данные уже пересоздаются", code="reseed_running")
        try:
            await _backup_before_reseed()
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "seed.generate",
                cwd=BACKEND_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        finally:
            await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RESEED_LOCK_KEY})
    if process.returncode != 0:
        raise AppError(
            "Не удалось пересоздать демо-данные", code="reseed_failed", details=stderr.decode()[-2000:]
        )
    return MessageResponse(message="Демо-данные пересозданы")
