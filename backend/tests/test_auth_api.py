from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.db import set_tenant
from app.models import AuditLog, AuthSession, User
from app.services.email import DEV_OUTBOX
from tests.conftest import IS_PG, PASSWORD, add_user, login_member


def test_login_sets_httponly_session_and_csrf_cookie(make_client, org_a):
    client = make_client()
    r = client.login("admin@a.test")
    assert r.status_code == 200
    body = r.json()
    assert body["me"]["organization"]["name"] == "Empresa A"
    assert body["me"]["role"] == "org_admin"
    assert body["access_token"] is None
    set_cookie = ",".join(r.headers.get_list("set-cookie"))
    assert "iios_session=" in set_cookie and "HttpOnly" in set_cookie.split("iios_csrf")[0]
    assert client.get("/api/v1/auth/me").status_code == 200


def test_wrong_password_and_unknown_user_return_same_generic_error(make_client, org_a):
    client = make_client()
    r1 = client.login("admin@a.test", "incorrecta-123")
    r2 = client.login("nadie@a.test", "incorrecta-123")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"]


def test_lockout_after_repeated_failures(make_client, org_a, db):
    client = make_client()
    for _ in range(5):
        assert client.login("admin@a.test", "incorrecta-123").status_code == 401
    r = client.login("admin@a.test")  # correct password while locked
    assert r.status_code == 401 and r.json()["error"]["code"] == "account_locked"
    db.execute(update(User).where(User.email == "admin@a.test").values(locked_until=datetime.now(UTC) - timedelta(seconds=1)))
    db.commit()
    assert client.login("admin@a.test").status_code == 200


def test_login_rate_limit(make_client, org_a):
    client = make_client()
    codes = [client.login("admin@a.test", "mala-clave-1").status_code for _ in range(11)]
    assert codes[-1] == 429


def test_requests_without_session_are_rejected(make_client):
    r = make_client().get("/api/v1/dashboard")
    assert r.status_code == 401
    assert r.json()["error"]["request_id"]


def test_csrf_required_for_cookie_authenticated_mutations(admin_a):
    del admin_a.c.headers["X-CSRF-Token"]
    r = admin_a.post("/api/v1/demo")
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    admin_a.c.headers["X-CSRF-Token"] = "valor-falso"
    assert admin_a.post("/api/v1/demo").status_code == 403


def test_bearer_token_for_integrations(make_client, org_a):
    anon = make_client()
    r = anon.post("/api/v1/auth/login", json={"email": "admin@a.test", "password": PASSWORD, "issue_bearer_token": True})
    token = r.json()["access_token"]
    fresh = make_client()
    r = fresh.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    r = fresh.patch("/api/v1/organization", json={"settings": {"currency": "USD"}}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200  # no CSRF needed: bearer tokens are not sent automatically by browsers


def test_logout_revokes_session(admin_a):
    cookie = admin_a.c.cookies.get("iios_session")
    assert admin_a.post("/api/v1/auth/logout").status_code == 200
    admin_a.c.cookies.set("iios_session", cookie)
    assert admin_a.get("/api/v1/auth/me").status_code == 401


def test_idle_session_expires(admin_a, db):
    db.execute(update(AuthSession).values(last_seen_at=datetime.now(UTC) - timedelta(hours=5)))
    db.commit()
    r = admin_a.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_invalid"


def test_absolute_session_expiry(admin_a, db):
    db.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()
    assert admin_a.get("/api/v1/auth/me").status_code == 401


def test_password_reset_flow(make_client, org_a, db):
    client = make_client()
    r = client.post("/api/v1/auth/password-reset/request", json={"email": "admin@a.test"})
    assert r.status_code == 202
    assert client.post("/api/v1/auth/password-reset/request", json={"email": "nadie@a.test"}).status_code == 202
    assert len(DEV_OUTBOX) == 1
    token = DEV_OUTBOX[0].body.split("#token=")[1].split()[0]
    stored = db.execute(select(User)).scalars().first()
    assert token not in str(stored.__dict__)
    r = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "corta"})
    assert r.status_code == 422
    r = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Nueva-Clave-Segura-9"})
    assert r.status_code == 200
    # Token is single use
    r = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Otra-Clave-Segura-9"})
    assert r.status_code == 422
    assert client.login("admin@a.test", "Nueva-Clave-Segura-9").status_code == 200


def test_password_reset_revokes_existing_sessions(admin_a, make_client):
    other = make_client()
    other.post("/api/v1/auth/password-reset/request", json={"email": "admin@a.test"})
    token = DEV_OUTBOX[-1].body.split("#token=")[1].split()[0]
    other.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "Nueva-Clave-Segura-9"})
    assert admin_a.get("/api/v1/auth/me").status_code == 401


def test_temporary_password_must_be_changed(admin_a, make_client):
    add_user(admin_a, "nuevo@a.test", "analyst")
    client = make_client()
    assert client.login("nuevo@a.test").status_code == 200
    r = client.get("/api/v1/dashboard")
    assert r.status_code == 403 and r.json()["error"]["code"] == "password_change_required"
    assert client.get("/api/v1/auth/me").json()["user"]["must_change_password"] is True
    r = client.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": PASSWORD + "z"})
    assert r.status_code == 200
    assert client.get("/api/v1/dashboard").status_code == 200


def test_change_password_rejects_wrong_current(admin_a):
    r = admin_a.post("/api/v1/auth/change-password", json={"current_password": "mal", "new_password": "Otra-Clave-Segura-9"})
    assert r.status_code == 422


def test_login_events_are_audited(make_client, org_a, db):
    client = make_client()
    client.login("admin@a.test", "incorrecta-123")
    client.login("admin@a.test")
    set_tenant(db, org_a[0].id)
    org_actions = [a.action for a in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars()]
    assert "auth.login" in org_actions
    if not IS_PG:
        # Platform-level rows (organization_id NULL) are not visible to tenant sessions under PostgreSQL RLS.
        all_actions = [a.action for a in db.execute(select(AuditLog)).scalars()]
        assert "auth.login_failed" in all_actions


def test_signup_creates_isolated_org(make_client):
    client = make_client()
    r = client.post("/api/v1/auth/signup", json={"organization_name": "Nueva SA", "display_name": "Ana",
                                                 "email": "ana@nueva.test", "password": PASSWORD})
    assert r.status_code == 201, r.text
    assert r.json()["me"]["role"] == "org_admin"
    r = client.post("/api/v1/auth/signup", json={"organization_name": "Otra", "display_name": "Ana",
                                                 "email": "ana@nueva.test", "password": PASSWORD})
    assert r.status_code == 409


def test_multi_org_user_switches_organization(admin_a, admin_b, make_client):
    add_user(admin_a, "consultor@x.test", "analyst")
    r = admin_b.post("/api/v1/organization/members", json={"email": "consultor@x.test", "display_name": "c", "role": "auditor"})
    assert r.status_code == 201  # existing user: no password needed
    client = login_member(make_client, "consultor@x.test")
    me = client.get("/api/v1/auth/me").json()
    assert len(me["memberships"]) == 2
    target = next(m for m in me["memberships"] if m["organization_name"] == "Empresa B")
    r = client.post("/api/v1/auth/switch-organization", json={"organization_id": target["organization_id"]})
    assert r.status_code == 200 and r.json()["role"] == "auditor"
    assert client.post("/api/v1/auth/switch-organization", json={"organization_id": 99999}).status_code == 403
