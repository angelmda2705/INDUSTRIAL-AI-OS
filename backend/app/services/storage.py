"""Organization-scoped file storage on the local filesystem.

User-supplied file names are never used as paths: files are stored under a
random name inside the organization's directory and every read resolves the
path and verifies it stays inside that directory.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import NotFound

ALLOWED_KINDS = {"imports", "reports"}


def _org_dir(org_id: int, kind: str) -> Path:
    if kind not in ALLOWED_KINDS:
        raise ValueError(kind)
    base = get_settings().storage_dir.resolve()
    path = (base / f"org_{int(org_id)}" / kind).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(org_id: int, kind: str, data: bytes, extension: str) -> tuple[str, str]:
    """Persist bytes; returns (stored_filename, sha256)."""
    name = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
    target = _org_dir(org_id, kind) / name
    target.write_bytes(data)
    return name, hashlib.sha256(data).hexdigest()


def path_for(org_id: int, kind: str, stored_filename: str) -> Path:
    directory = _org_dir(org_id, kind)
    path = (directory / stored_filename).resolve()
    if path.parent != directory or not path.is_file():
        raise NotFound("Archivo no encontrado.")
    return path


def delete(org_id: int, kind: str, stored_filename: str) -> None:
    try:
        path_for(org_id, kind, stored_filename).unlink()
    except NotFound:
        pass
