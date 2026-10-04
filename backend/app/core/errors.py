import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


class ValidationIssue(BaseModel):
    """Элемент details при 422: loc вида ["body", "email"], msg — по-русски."""

    loc: list[str | int]
    msg: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ValidationIssue] | dict[str, Any] | None = Field(
        default=None, description="Для 422 — список полей с ошибками"
    )


class ErrorResponse(BaseModel):
    error: ErrorBody


# Сообщения pydantic по-английски; пользователю показываем русские
VALIDATION_MESSAGES = {
    "missing": "Обязательное поле",
    "string_too_short": "Слишком короткое значение",
    "string_too_long": "Слишком длинное значение",
    "string_pattern_mismatch": "Неверный формат",
    "value_error": "Некорректное значение",
    "greater_than": "Значение слишком маленькое",
    "greater_than_equal": "Значение слишком маленькое",
    "less_than_equal": "Значение слишком большое",
    "int_parsing": "Нужно целое число",
    "float_parsing": "Нужно число",
    "bool_parsing": "Нужно да или нет",
    "enum": "Недопустимое значение",
    "literal_error": "Недопустимое значение",
    "json_invalid": "Некорректный JSON",
}


def _validation_message(error: dict) -> str:
    message = str(error.get("msg", "")).removeprefix("Value error, ")
    if error["type"] == "value_error":
        # Наши model_validator пишут по-русски — их текст показываем; английский от библиотек заменяем
        if re.search("[а-яА-ЯёЁ]", message):
            return message
        if "email" in message.lower():
            return "Некорректный email"
    return VALIDATION_MESSAGES.get(error["type"], "Некорректное значение")


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
        details = [
            ValidationIssue(loc=list(e["loc"]), msg=_validation_message(e), type=e["type"]).model_dump()
            for e in exc.errors()
        ]
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


def use_unified_validation_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """FastAPI документирует 422 своей схемой HTTPValidationError; фактический ответ — ErrorResponse."""
    for item in schema.get("paths", {}).values():
        for operation in item.values():
            response = operation.get("responses", {}).get("422")
            if response:
                response["description"] = "Ошибка валидации данных"
                response["content"] = {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
                }
    components = schema.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        components.pop(name, None)
    return schema
