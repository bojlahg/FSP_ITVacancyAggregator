"""Служебные действия демо-режима."""

import asyncio
import sys
from pathlib import Path

from app.core.errors import AppError, ConflictError
from app.core.schemas import MessageResponse

BACKEND_DIR = Path(__file__).resolve().parents[3]
_running = asyncio.Lock()


async def reseed() -> MessageResponse:
    """Генератор — отдельный процесс: он считает ~40 с и не должен блокировать event loop API."""
    if _running.locked():
        raise ConflictError("Демо-данные уже пересоздаются", code="reseed_running")
    async with _running:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "seed.generate",
            cwd=BACKEND_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise AppError(
            "Не удалось пересоздать демо-данные", code="reseed_failed", details=stderr.decode()[-2000:]
        )
    return MessageResponse(message="Демо-данные пересозданы")
