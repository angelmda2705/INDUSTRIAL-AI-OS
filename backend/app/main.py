"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import analysis, auth, data, organization, system
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, request_id_var

log = logging.getLogger("app.http")
API_PREFIX = "/api/v1"


def check_production_settings(settings: Settings) -> None:
    """Refuse to start a production instance with unsafe settings."""
    if not settings.is_production:
        return
    problems = []
    if not settings.cookie_secure:
        problems.append("IIOS_COOKIE_SECURE debe ser true en producción (requiere HTTPS).")
    if settings.is_sqlite:
        problems.append("Producción requiere PostgreSQL (IIOS_DATABASE_URL).")
    if settings.debug:
        problems.append("IIOS_DEBUG debe ser false en producción.")
    if problems:
        raise RuntimeError("Configuración insegura para producción: " + " ".join(problems))


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    check_production_settings(settings)

    app = FastAPI(
        title=f"{settings.brand_name} API",
        version=__version__,
        description="API de la plataforma de inteligencia operativa. Todas las rutas requieren sesión salvo las de "
                    "autenticación y sistema.",
        docs_url=f"{API_PREFIX}/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if not settings.is_production else None,
    )
    install_error_handlers(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")
        if not (0 < len(rid) <= 64 and rid.replace("-", "").isalnum()):
            rid = uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_var.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        if not request.url.path.startswith(f"{API_PREFIX}/docs"):
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        log.info("request", extra={"method": request.method, "path": request.url.path, "status": response.status_code,
                                   "ms": round(elapsed, 1), "rid": rid})
        return response

    for router in (system.router, auth.router, organization.router, organization.platform, data.router, analysis.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
