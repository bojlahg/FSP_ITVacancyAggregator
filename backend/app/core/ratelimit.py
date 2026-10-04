import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"
    message = "Слишком много запросов, попробуйте позже"


class SlidingWindowLimiter:
    """In-memory: backend работает одним процессом, для MVP этого достаточно."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


auth_limiter = SlidingWindowLimiter()


def limit_auth_requests(request: Request) -> None:
    settings = get_settings()
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.url.path}"
    if not auth_limiter.hit(key, settings.auth_rate_limit, settings.auth_rate_window_seconds):
        raise TooManyRequestsError()
