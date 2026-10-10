"""Password hashing, opaque token generation and password policy."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

import bcrypt

from app.core.config import get_settings

BCRYPT_ROUNDS = 12

# A short deny-list of passwords that pass naive length rules but are trivially
# guessable. It is intentionally small; production deployments can extend the
# policy with a breached-password check (see docs/SECURITY.md).
_COMMON_PASSWORDS = {
    "password1234", "contraseña123", "contrasena123", "1234567890", "qwerty12345",
    "administrador1", "admin123456", "bienvenido123", "industrial123", "password123",
}


def _prehash(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes; pre-hashing keeps long passphrases
    # fully significant. base64 avoids NUL bytes in the bcrypt input.
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except ValueError:
        return False


# Used to keep login timing similar whether or not the account exists.
_DUMMY_HASH = bcrypt.hashpw(_prehash("timing-equalizer"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def dummy_verify() -> None:
    verify_password("not-the-password", _DUMMY_HASH)


def new_token() -> str:
    """Return a URL-safe random token with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored only as SHA-256 digests so a database leak does not expose sessions."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def password_policy_errors(password: str, email: str | None = None) -> list[str]:
    settings = get_settings()
    errors: list[str] = []
    if len(password) < settings.password_min_length:
        errors.append(f"Debe tener al menos {settings.password_min_length} caracteres.")
    if len(password) > 256:
        errors.append("No debe exceder 256 caracteres.")
    if not any(c.isalpha() for c in password):
        errors.append("Debe incluir al menos una letra.")
    if not any(c.isdigit() for c in password):
        errors.append("Debe incluir al menos un número.")
    if password.lower() in _COMMON_PASSWORDS:
        errors.append("Es una contraseña demasiado común.")
    if email and email.split("@")[0].lower() in password.lower() and len(email.split("@")[0]) >= 4:
        errors.append("No debe contener tu usuario de correo.")
    return errors
