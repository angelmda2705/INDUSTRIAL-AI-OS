"""Administrative command line.

Usage (from backend/):
    python -m app.cli migrate
    python -m app.cli create-org --name "Mi Empresa" --admin-email admin@empresa.com --admin-name "Admin"
    python -m app.cli create-platform-admin --email ops@proveedor.com --name "Operación"
    python -m app.cli cleanup-sessions

Passwords are read from IIOS_BOOTSTRAP_PASSWORD or prompted interactively;
they are never accepted as command-line arguments (they would end up in shell history).
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select

from app.core.config import BACKEND_DIR
from app.core.db import session_factory, set_tenant
from app.core.errors import AppError
from app.core.security import hash_password
from app.models import AuthSession, PasswordResetToken, User
from app.services.auth import normalize_email, validate_new_password
from app.services.organizations import create_organization, ensure_default_plans


def _password(email: str) -> str:
    pw = os.environ.get("IIOS_BOOTSTRAP_PASSWORD")
    if not pw:
        pw = getpass.getpass(f"Contraseña para {email}: ")
        if pw != getpass.getpass("Confirma la contraseña: "):
            sys.exit("Las contraseñas no coinciden.")
    validate_new_password(pw, email)
    return pw


def cmd_migrate(_: argparse.Namespace) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")
    print("Base de datos actualizada.")


def cmd_create_org(args: argparse.Namespace) -> None:
    with session_factory()() as db:
        email = normalize_email(args.admin_email)
        exists = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        password = None if exists else _password(email)
        org, user = create_organization(db, name=args.name, admin_email=email, admin_name=args.admin_name,
                                        admin_password=password, plan_code=args.plan)
        db.commit()
        print(f"Organización creada: id={org.id} slug={org.slug}; administrador: {user.email}")


def cmd_create_platform_admin(args: argparse.Namespace) -> None:
    with session_factory()() as db:
        set_tenant(db, None)
        ensure_default_plans(db)
        email = normalize_email(args.email)
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(email=email, display_name=args.name, password_hash=hash_password(_password(email)))
            db.add(user)
        user.is_platform_admin = True
        db.commit()
        print(f"Administrador de plataforma: {user.email}")


def cmd_cleanup_sessions(_: argparse.Namespace) -> None:
    """Delete expired/revoked sessions and used/expired reset tokens older than 30 days."""
    cutoff = datetime.now(UTC) - timedelta(days=30)
    with session_factory()() as db:
        s = db.execute(delete(AuthSession).where(or_(AuthSession.expires_at < cutoff, AuthSession.revoked_at < cutoff))).rowcount
        t = db.execute(delete(PasswordResetToken).where(PasswordResetToken.expires_at < cutoff)).rowcount
        db.commit()
        print(f"Sesiones eliminadas: {s}; tokens de recuperación eliminados: {t}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="Aplicar migraciones pendientes").set_defaults(func=cmd_migrate)
    p = sub.add_parser("create-org", help="Crear organización con su administrador")
    p.add_argument("--name", required=True)
    p.add_argument("--admin-email", required=True)
    p.add_argument("--admin-name", required=True)
    p.add_argument("--plan", default="starter")
    p.set_defaults(func=cmd_create_org)
    p = sub.add_parser("create-platform-admin", help="Crear o promover administrador de plataforma")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.set_defaults(func=cmd_create_platform_admin)
    sub.add_parser("cleanup-sessions", help="Depurar sesiones y tokens vencidos").set_defaults(func=cmd_cleanup_sessions)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except AppError as exc:
        details = f" {exc.details}" if exc.details else ""
        sys.exit(f"Error: {exc.message}{details}")


if __name__ == "__main__":
    main()
