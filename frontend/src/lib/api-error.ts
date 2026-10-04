import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import type { components } from "@/api/schema";

type ErrorBody = components["schemas"]["ErrorBody"];
type ValidationIssue = components["schemas"]["ValidationIssue"];

export interface ApiErrorInfo {
  /** HTTP-статус; 0 — сеть недоступна или ответ не пришёл. */
  status: number;
  code: string;
  message: string;
  details: unknown;
}

/** Ошибка ответа API в едином формате `{error: {code, message, details}}` (docs/implementation.md §15). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Тело ответа соответствует ErrorResponse. */
export function isErrorResponse(value: unknown): value is components["schemas"]["ErrorResponse"] {
  return (
    isRecord(value) &&
    isRecord(value.error) &&
    typeof value.error.code === "string" &&
    typeof value.error.message === "string"
  );
}

const NETWORK_MESSAGE = "Не удалось связаться с сервером. Проверьте соединение и попробуйте ещё раз.";
const UNKNOWN_MESSAGE = "Что-то пошло не так. Попробуйте ещё раз.";

/** Превращает ответ openapi-fetch с ошибкой в ApiError (для mutationFn/queryFn). */
export function toApiError(response: Response, body: unknown): ApiError {
  if (isErrorResponse(body)) return new ApiError(response.status, body.error);
  return new ApiError(response.status, { code: `http_${response.status}`, message: UNKNOWN_MESSAGE });
}

/** Достаёт {status, code, message, details} из любой ошибки запроса. */
export function apiError(err: unknown): ApiErrorInfo {
  if (err instanceof ApiError) {
    return { status: err.status, code: err.code, message: err.message, details: err.details };
  }
  if (isErrorResponse(err)) {
    return { status: 0, code: err.error.code, message: err.error.message, details: err.error.details ?? null };
  }
  if (err instanceof TypeError) {
    return { status: 0, code: "network_error", message: NETWORK_MESSAGE, details: null };
  }
  return { status: 0, code: "unknown_error", message: UNKNOWN_MESSAGE, details: null };
}

function isValidationIssue(value: unknown): value is ValidationIssue {
  return isRecord(value) && Array.isArray(value.loc) && typeof value.msg === "string";
}

/** Список ошибок валидации из details ответа 422 (`[{loc, msg, type}]`). */
export function validationIssues(err: unknown): ValidationIssue[] {
  const { details } = apiError(err);
  return Array.isArray(details) ? details.filter(isValidationIssue) : [];
}

/**
 * Раскладывает ошибки 422 по полям react-hook-form: поле берётся по последнему элементу `loc`
 * (`["body", "email"]` → `email`) и переводится в имя поля формы через `fieldMap`.
 * Возвращает true, если хотя бы одна ошибка попала в поле.
 */
export function applyValidationErrors<T extends FieldValues>(
  err: unknown,
  setError: UseFormSetError<T>,
  fieldMap: Partial<Record<string, Path<T>>>,
): boolean {
  let applied = false;
  for (const issue of validationIssues(err)) {
    const key = issue.loc[issue.loc.length - 1];
    const field = typeof key === "string" ? fieldMap[key] : undefined;
    if (field) {
      setError(field, { type: "server", message: issue.msg });
      applied = true;
    }
  }
  return applied;
}
