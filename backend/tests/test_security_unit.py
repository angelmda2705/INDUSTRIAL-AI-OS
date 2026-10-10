from app.core.logging import redact
from app.core.permissions import ROLE_PERMISSIONS, Perm, Role, can_assign_role, permissions_for
from app.core.security import hash_password, hash_token, new_token, password_policy_errors, verify_password


def test_password_hash_roundtrip_and_no_plaintext():
    h = hash_password("Una-Contraseña-Larga-123")
    assert "Contraseña" not in h and h.startswith("$2")
    assert verify_password("Una-Contraseña-Larga-123", h)
    assert not verify_password("una-contraseña-larga-123", h)


def test_long_passphrases_are_fully_significant():
    base = "x" * 80
    h = hash_password(base + "A1")
    assert verify_password(base + "A1", h)
    assert not verify_password(base + "B1", h)  # plain bcrypt would ignore bytes after 72


def test_verify_handles_garbage_hash():
    assert verify_password("x", "not-a-hash") is False


def test_tokens_are_random_and_hashed():
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 40
    assert hash_token(a) != a and len(hash_token(a)) == 64


def test_password_policy():
    assert password_policy_errors("corta1")
    assert password_policy_errors("solamenteletras")
    assert password_policy_errors("password1234")
    assert password_policy_errors("juanperez2024x", "juanperez@empresa.com")
    assert password_policy_errors("Segura-Larga-2024") == []


def test_redaction_of_secrets_in_logs():
    text = redact('password="hunter2" Authorization: Bearer abc.def.ghi api_key=XYZ')
    assert "hunter2" not in text and "abc.def.ghi" not in text and "XYZ" not in text


def test_role_matrix_invariants():
    assert ROLE_PERMISSIONS[Role.ORG_ADMIN] == frozenset(Perm)
    auditor = permissions_for("auditor")
    assert Perm.AUDIT_READ in auditor
    assert not ({Perm.DATA_IMPORT, Perm.DATA_DELETE, Perm.USERS_MANAGE, Perm.FINDINGS_UPDATE} & auditor)
    assert Perm.AUDIT_READ not in permissions_for("operator")
    assert permissions_for("unknown-role") == frozenset()
    assert can_assign_role("org_admin", "org_admin")
    assert not can_assign_role("manager", "analyst")  # managers do not manage users
    assert not can_assign_role("director", "org_admin")
