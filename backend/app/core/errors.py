"""Error types and handlers.

Errors returned to clients never include stack traces or internal details.
Every response carries the request id so support can correlate it with logs.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class LimitExceeded(AppError):
    status_code = 429
    code = "limit_exceeded"


class PlanLimitExceeded(AppError):
    status_code = 402
    code = "plan_limit_exceeded"


def _body(request: Request, code: str, message: str, details: Any = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


_FIELD_MESSAGES = {
    "missing": "Campo obligatorio.",
    "string_too_short": "El valor es demasiado corto.",
    "string_too_long": "El valor es demasiado largo.",
    "value_error": "Valor no válido.",
    "int_parsing": "Debe ser un número entero.",
    "float_parsing": "Debe ser un número.",
    "enum": "Valor no permitido.",
    "literal_error": "Valor no permitido.",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
            msg = err.get("msg", "Valor no válido.")
            if err.get("type") in _FIELD_MESSAGES and err.get("type") != "value_error":
                msg = _FIELD_MESSAGES[err["type"]]
            elif msg.startswith("Value error, "):
                msg = msg.removeprefix("Value error, ")
            details.append({"field": ".".join(loc), "message": msg})
        return JSONResponse(
            _body(request, "validation_failed", "Los datos enviados no son válidos.", details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        messages = {404: "Recurso no encontrado.", 405: "Método no permitido.", 413: "Archivo demasiado grande."}
        message = exc.detail if isinstance(exc.detail, str) and exc.status_code not in messages else messages.get(
            exc.status_code, "Solicitud no válida."
        )
        return JSONResponse(_body(request, f"http_{exc.status_code}", message), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(
            _body(request, "internal_error", "Ocurrió un error interno. Comparte el identificador de solicitud con soporte."),
            status_code=500,
        )
