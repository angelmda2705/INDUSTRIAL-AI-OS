from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.db import get_db

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", summary="Estado del servicio y de la base de datos")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - report degraded state without leaking details
        database = "error"
    status = "ok" if database == "ok" else "degraded"
    return JSONResponse({"status": status, "database": database, "version": __version__},
                        status_code=200 if status == "ok" else 503)


@router.get("/branding", summary="Marca configurable (nombre, colores)")
def branding():
    s = get_settings()
    return {"name": s.brand_name, "short_name": s.brand_short_name, "primary_color": s.brand_primary_color,
            "support_email": s.brand_support_email, "allow_self_signup": s.allow_self_signup}
