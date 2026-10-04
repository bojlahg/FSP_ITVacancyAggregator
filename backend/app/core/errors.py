from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "Некорректный запрос"

    def __init__(self, message: str | None = None, *, code: str | None = None, details: Any = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.code = code or self.code
        self.details = details


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Требуется вход"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Недостаточно прав"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Не найдено"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Конфликт состояния"


class NotImplementedApiError(AppError):
    status_code = 501
    code = "not_implemented"
    message = "Метод ещё не реализован"


def _error(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status, content=body.model_dump())


def app_error_response(exc: AppError) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.message, exc.details)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return app_error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return _error(422, "validation_error", "Ошибка валидации данных", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, f"http_{exc.status_code}", str(exc.detail))


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    descriptions = {
        400: "Некорректный запрос",
        401: "Требуется вход",
        403: "Недостаточно прав",
        404: "Не найдено",
        409: "Конфликт состояния",
        422: "Ошибка валидации данных",
        429: "Слишком много запросов",
        501: "Метод ещё не реализован",
    }
    return {code: {"model": ErrorResponse, "description": descriptions[code]} for code in codes}
