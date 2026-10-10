"""Multi-tenant isolation and role-based authorization through the API."""

import pytest

from tests.conftest import add_user, import_csv, login_member

PRODUCTION_CSV = """Fecha,Centro de trabajo,Cantidad planeada,Piezas buenas,Scrap
01/03/2024,L1,100,90,5
02/03/2024,L1,100,95,2
"""


@pytest.fixture
def b_data(admin_b):
    result = import_csv(admin_b, PRODUCTION_CSV, "production_records", "Producción B")
    dataset_id = result["job"]["target_dataset_id"]
    # A target that the data misses guarantees at least one finding in organization B.
    assert admin_b.put("/api/v1/kpis/production_compliance/target", json={"target_value": 99}).status_code == 200
    assert admin_b.post(f"/api/v1/datasets/{dataset_id}/analyze").status_code == 200
    report = admin_b.post("/api/v1/reports", json={"report_type": "diagnostic", "file_format": "xlsx"}).json()
    findings = admin_b.get("/api/v1/findings").json()["items"]
    return {"dataset_id": dataset_id, "import_id": result["job"]["id"], "report_id": report["id"], "findings": findings}


def test_other_org_resources_are_not_found(admin_a, b_data):
    ds, imp, rep = b_data["dataset_id"], b_data["import_id"], b_data["report_id"]
    for url in (f"/api/v1/datasets/{ds}", f"/api/v1/datasets/{ds}/records", f"/api/v1/datasets/{ds}/export",
                f"/api/v1/imports/{imp}", f"/api/v1/imports/{imp}/preview", f"/api/v1/reports/{rep}/download",
                f"/api/v1/kpis/production_compliance?dataset_id={ds}"):
        r = admin_a.get(url)
        assert r.status_code == 404, (url, r.status_code)
    for f in b_data["findings"]:
        assert admin_a.get(f"/api/v1/findings/{f['id']}").status_code == 404
        assert admin_a.patch(f"/api/v1/findings/{f['id']}", json={"note": "x"}).status_code == 404
    assert admin_a.post(f"/api/v1/datasets/{ds}/analyze").status_code == 404
    assert admin_a.delete(f"/api/v1/datasets/{ds}").status_code == 404
    assert admin_a.post(f"/api/v1/imports/{imp}/revert").status_code == 404


def test_listings_only_contain_own_org(admin_a, b_data):
    assert admin_a.get("/api/v1/datasets").json() == []
    assert admin_a.get("/api/v1/imports").json()["total"] == 0
    assert admin_a.get("/api/v1/findings").json()["total"] == 0
    assert admin_a.get("/api/v1/reports").json() == []
    assert admin_a.get("/api/v1/kpis/values").json() == []
    dash = admin_a.get("/api/v1/dashboard").json()
    assert dash["has_data"] is False and dash["findings"]["open_total"] == 0
    audit = admin_a.get("/api/v1/audit").json()["items"]
    assert all("b.test" not in a["actor_label"] for a in audit)
    members = admin_a.get("/api/v1/organization/members").json()
    assert [m["email"] for m in members] == ["admin@a.test"]


def test_cannot_append_to_other_org_dataset(admin_a, b_data):
    r = admin_a.post("/api/v1/imports", files={"file": ("x.csv", PRODUCTION_CSV.encode(), "text/csv")})
    job = r.json()["id"]
    preview = admin_a.get(f"/api/v1/imports/{job}/preview").json()
    r = admin_a.post(f"/api/v1/imports/{job}/validate", json={
        "template_code": "production_records", "mapping": preview["suggested_mappings"]["production_records"],
        "dataset_id": b_data["dataset_id"]})
    assert r.status_code == 404


def test_cannot_assign_finding_to_user_of_another_org(admin_a, admin_b, b_data):
    me_a = admin_a.get("/api/v1/auth/me").json()["user"]["id"]
    assert b_data["findings"], "fixture must produce findings"
    fid = b_data["findings"][0]["id"]
    r = admin_b.patch(f"/api/v1/findings/{fid}", json={"owner_user_id": me_a})
    assert r.status_code == 422


def test_auditor_is_read_only(admin_a, make_client):
    add_user(admin_a, "auditor@a.test", "auditor")
    auditor = login_member(make_client, "auditor@a.test")
    assert auditor.get("/api/v1/dashboard").status_code == 200
    assert auditor.get("/api/v1/audit").status_code == 200
    r = auditor.post("/api/v1/imports", files={"file": ("x.csv", PRODUCTION_CSV.encode(), "text/csv")})
    assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"
    assert auditor.post("/api/v1/demo").status_code == 403
    assert auditor.put("/api/v1/kpis/scrap_rate/target", json={"target_value": 2}).status_code == 403
    assert auditor.patch("/api/v1/organization", json={"name": "Hackeada"}).status_code == 403
    assert auditor.post("/api/v1/organization/members", json={"email": "x@a.test", "display_name": "x", "role": "analyst",
                                                               "initial_password": "Clave-Segura-123"}).status_code == 403


def test_operator_cannot_read_audit_or_manage(admin_a, make_client):
    add_user(admin_a, "operador@a.test", "operator")
    op = login_member(make_client, "operador@a.test")
    assert op.get("/api/v1/audit").status_code == 403
    assert op.get("/api/v1/organization/members").status_code == 403
    assert op.post("/api/v1/reports", json={}).status_code == 403
    r = op.post("/api/v1/imports", files={"file": ("x.csv", PRODUCTION_CSV.encode(), "text/csv")})
    assert r.status_code == 201  # operators capture data


def test_only_admin_grants_admin_role(admin_a, make_client):
    add_user(admin_a, "gerente@a.test", "manager")
    manager = login_member(make_client, "gerente@a.test")
    r = manager.post("/api/v1/organization/members", json={"email": "z@a.test", "display_name": "z", "role": "org_admin",
                                                           "initial_password": "Clave-Segura-123"})
    assert r.status_code == 403


def test_last_admin_cannot_be_removed_and_no_self_demotion(admin_a):
    members = admin_a.get("/api/v1/organization/members").json()
    me = members[0]
    r = admin_a.patch(f"/api/v1/organization/members/{me['id']}", json={"role": "analyst"})
    assert r.status_code == 403
    add_user(admin_a, "otro@a.test", "analyst")
    other = next(m for m in admin_a.get("/api/v1/organization/members").json() if m["email"] == "otro@a.test")
    assert admin_a.patch(f"/api/v1/organization/members/{other['id']}", json={"role": "org_admin"}).status_code == 200
    assert admin_a.patch(f"/api/v1/organization/members/{other['id']}", json={"is_active": False}).status_code == 200


def test_deactivated_member_loses_access_immediately(admin_a, make_client):
    add_user(admin_a, "temporal@a.test", "analyst")
    user = login_member(make_client, "temporal@a.test")
    assert user.get("/api/v1/dashboard").status_code == 200
    member = next(m for m in admin_a.get("/api/v1/organization/members").json() if m["email"] == "temporal@a.test")
    admin_a.patch(f"/api/v1/organization/members/{member['id']}", json={"is_active": False})
    r = user.get("/api/v1/dashboard")
    assert r.status_code == 403 and r.json()["error"]["code"] == "organization_required"


def test_plan_user_limit(make_client, db):
    from tests.conftest import create_org_with_admin

    create_org_with_admin(db, "Pequeña", "admin@p.test", plan="starter")  # max 5 users
    admin = make_client()
    admin.login("admin@p.test")
    for i in range(4):
        add_user(admin, f"u{i}@p.test", "operator")
    r = admin.post("/api/v1/organization/members", json={"email": "u9@p.test", "display_name": "u9", "role": "operator",
                                                         "initial_password": "Clave-Segura-123"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "plan_limit_exceeded"


def test_disabled_module_is_enforced_server_side(admin_a, db, org_a):
    from app.core.db import set_tenant
    from app.models import Organization

    set_tenant(db, None)
    org = db.get(Organization, org_a[0].id)
    org.enabled_modules = ["analytics", "findings", "kpis", "reports"]
    db.commit()
    r = admin_a.post("/api/v1/imports", files={"file": ("x.csv", PRODUCTION_CSV.encode(), "text/csv")})
    assert r.status_code == 403 and r.json()["error"]["code"] == "module_disabled"


def test_platform_admin_endpoints_require_flag(admin_a):
    assert admin_a.get("/api/v1/platform/organizations").status_code == 403
