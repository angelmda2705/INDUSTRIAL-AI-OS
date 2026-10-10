"""Findings lifecycle: detection, de-duplication, reopening, verification and workflow."""

from tests.conftest import import_csv, upload_csv

INVENTORY_CSV = """SKU,Descripción,Existencia,Costo unitario,Demanda diaria,Desviación demanda,Lead time,Máximo,Último movimiento
S1,Tornillo,10,2,5,2,4,100,01/06/2024
S2,Rodamiento,0,10,1,,9,,30/06/2024
S3,Empaque,500,1,2,1,1,100,30/06/2024
S4,Refacción vieja,5,100,,,,,01/12/2023
"""


def _findings(client, **params):
    return client.get("/api/v1/findings", params={"page_size": 100, **params}).json()["items"]


def _by_rule(client):
    return {f["rule_code"]: f for f in _findings(client)}


def test_inventory_rules_produce_explained_findings(admin_a):
    import_csv(admin_a, INVENTORY_CSV, "inventory_items", "Inventario")
    rules = _by_rule(admin_a)
    assert {"INV-STOCKOUT", "INV-BELOW-ROP", "INV-EXCESS", "INV-NO-MOVEMENT"} <= set(rules)
    stockout = admin_a.get(f"/api/v1/findings/{rules['INV-STOCKOUT']['id']}").json()
    assert stockout["nature"] == "confirmed_issue" and stockout["code"].startswith("HAL-")
    assert [i["sku"] for i in stockout["evidence"]["items"]] == ["S2"]
    assert stockout["method"] and stockout["recommendation"]
    assert stockout["events"][0]["event_type"] == "detected"
    excess = rules["INV-EXCESS"]
    assert excess["impact_amount"] == 400.0 and "No es un ahorro" in excess["impact_basis"]
    assert excess["impact_kind"] == "capital_tied"
    assert rules["INV-STOCKOUT"]["impact_amount"] is None and rules["INV-STOCKOUT"]["impact_kind"] is None
    assert rules["INV-NO-MOVEMENT"]["nature"] == "hypothesis"
    below = admin_a.get(f"/api/v1/findings/{rules['INV-BELOW-ROP']['id']}").json()
    assert below["evidence"]["items"][0]["_suggested_order_qty"] == 90.0


def test_rerun_does_not_duplicate_findings(admin_a):
    body = import_csv(admin_a, INVENTORY_CSV, "inventory_items", "Inventario")
    ds = body["job"]["target_dataset_id"]
    first = {f["id"] for f in _findings(admin_a)}
    run = admin_a.post(f"/api/v1/datasets/{ds}/analyze").json()
    assert run["summary"]["findings_created"] == 0 and run["summary"]["findings_updated"] == len(first)
    assert {f["id"] for f in _findings(admin_a)} == first


def test_resolved_finding_reopens_if_condition_persists(admin_a):
    body = import_csv(admin_a, INVENTORY_CSV, "inventory_items", "Inventario")
    ds = body["job"]["target_dataset_id"]
    f = _by_rule(admin_a)["INV-STOCKOUT"]
    r = admin_a.patch(f"/api/v1/findings/{f['id']}", json={"status": "resolved"})
    assert r.status_code == 422  # a note is required
    r = admin_a.patch(f"/api/v1/findings/{f['id']}", json={"status": "resolved", "note": "Se compró material"})
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    admin_a.post(f"/api/v1/datasets/{ds}/analyze")
    detail = admin_a.get(f"/api/v1/findings/{f['id']}").json()
    assert detail["status"] == "open"
    assert detail["events"][-1]["event_type"] == "reopened_by_analysis"


def test_condition_no_longer_detected_after_new_data(admin_a):
    body = import_csv(admin_a, INVENTORY_CSV, "inventory_items", "Inventario")
    job_id = body["job"]["id"]
    f = _by_rule(admin_a)["INV-STOCKOUT"]
    admin_a.post(f"/api/v1/imports/{job_id}/revert")
    fixed = INVENTORY_CSV.replace("S2,Rodamiento,0,", "S2,Rodamiento,50,")
    import_csv(admin_a, fixed, "inventory_items", "", dataset_id=body["job"]["target_dataset_id"])
    detail = admin_a.get(f"/api/v1/findings/{f['id']}").json()
    assert detail["condition_active"] is False
    assert any(e["event_type"] == "condition_not_detected" for e in detail["events"])
    assert admin_a.get("/api/v1/findings", params={"active_only": True}).json()["total"] < len(_findings(admin_a))


def test_target_deviation_requires_configured_target(admin_a):
    csv = "Fecha,Centro de trabajo,Cantidad planeada,Piezas buenas\n01/03/2024,L1,100,80\n02/03/2024,L2,100,99\n"
    ds = import_csv(admin_a, csv, "production_records", "Prod")["job"]["target_dataset_id"]
    assert not any(f["category"] == "target_deviation" for f in _findings(admin_a))
    r = admin_a.put("/api/v1/kpis/production_compliance/target", json={"target_value": 95, "tolerance": 1})
    assert r.status_code == 200
    assert admin_a.get("/api/v1/datasets").json()[0]["analysis_stale"] is True
    admin_a.post(f"/api/v1/datasets/{ds}/analyze")
    devs = [f for f in _findings(admin_a) if f["category"] == "target_deviation"]
    titles = " | ".join(f["title"] for f in devs)
    assert len(devs) == 2 and "L1" in titles and "L2" not in titles  # total (89.5 %) and L1 (80 %)
    values = admin_a.get("/api/v1/kpis/values").json()
    comp = next(v for v in values if v["kpi_code"] == "production_compliance")
    assert comp["value"] == 89.5 and comp["evaluation"] == "misses" and comp["target"] == 95
    # Neutral KPIs do not accept targets
    assert admin_a.put("/api/v1/kpis/inventory_value/target", json={"target_value": 1}).status_code == 422


def test_workflow_transitions_owner_and_comments(admin_a):
    import_csv(admin_a, INVENTORY_CSV, "inventory_items", "Inventario")
    f = _findings(admin_a)[0]
    me = admin_a.get("/api/v1/auth/me").json()["user"]["id"]
    r = admin_a.patch(f"/api/v1/findings/{f['id']}", json={"status": "in_review", "owner_user_id": me, "due_date": "2024-12-31"})
    assert r.status_code == 200
    d = r.json()
    assert d["owner_user_id"] == me and d["due_date"] == "2024-12-31" and d["owner_name"]
    r = admin_a.post(f"/api/v1/findings/{f['id']}/comments", json={"note": "Se revisará el lunes"})
    assert r.status_code == 201 and r.json()["events"][-1]["note"] == "Se revisará el lunes"
    r = admin_a.patch(f"/api/v1/findings/{f['id']}", json={"status": "dismissed", "note": "No aplica"})
    assert r.status_code == 200
    r = admin_a.patch(f"/api/v1/findings/{f['id']}", json={"status": "action_planned"})
    assert r.status_code == 422  # dismissed → action_planned is not allowed
    assert admin_a.patch(f"/api/v1/findings/{f['id']}", json={}).status_code == 422
    audit = admin_a.get("/api/v1/audit", params={"action": "finding."}).json()
    assert audit["total"] >= 3


def test_fuel_anomaly_is_statistical_with_confidence_and_impact(admin_a):
    lines = ["Unidad,Fecha,Odómetro,Litros,Importe"]
    odo = 10000
    # 500 km between full fills; one interval (180 l) with abnormal consumption.
    liters = [100, 101, 99, 102, 100, 97, 103, 100, 180, 99, 101, 100]
    for i, lt in enumerate(liters):
        odo += 500
        lines.append(f"T1,{i + 1:02d}/01/2024,{odo},{lt},{lt * 25}")
    import_csv(admin_a, "\n".join(lines) + "\n", "fuel_logs", "Combustible")
    f = _by_rule(admin_a)["FLT-FUEL-ANOMALY"]
    assert f["nature"] == "statistical_anomaly" and f["confidence"] == "media"  # 11 intervals
    # median 5 km/l → expected 100 l; excess = 80 l × 25 = 2000
    assert f["impact_amount"] == 2000.0 and f["impact_kind"] == "estimated_excess_cost"
    detail = admin_a.get(f"/api/v1/findings/{f['id']}").json()
    assert len(detail["evidence"]["anomalous_loads"]) == 1
    assert "no establece la causa" in f["description"]


def test_missing_values_and_duplicates_produce_data_quality_findings(admin_a):
    csv = "Fecha,Centro de trabajo,Piezas buenas,Scrap\n01/03/2024,L1,10,\n02/03/2024,L1,10,\n03/03/2024,L1,10,1\n"
    body = import_csv(admin_a, csv, "production_records", "Prod")
    ds = body["job"]["target_dataset_id"]
    rules = _by_rule(admin_a)
    assert rules["DQ-MISSING"]["category"] == "data_quality"
    # Importing the same rows again *including* duplicates produces a duplicate finding.
    job = upload_csv(admin_a, csv).json()
    preview = admin_a.get(f"/api/v1/imports/{job['id']}/preview").json()
    admin_a.post(f"/api/v1/imports/{job['id']}/validate", json={
        "template_code": "production_records", "mapping": preview["suggested_mappings"]["production_records"], "dataset_id": ds})
    admin_a.post(f"/api/v1/imports/{job['id']}/commit", json={"skip_duplicates": False})
    assert "DQ-DUPLICATES" in _by_rule(admin_a)


def test_impact_amounts_require_a_kind():
    import pytest

    from app.services.analytics.rules import FindingDraft

    with pytest.raises(ValueError):
        FindingDraft(rule_code="X", key="k", area="a", category="c", nature="hypothesis", title="t", description="d",
                     method="m", priority="low", recommendation="r", impact_amount=10.0)


def test_dashboard_never_adds_different_impact_kinds(admin_a):
    import_csv(admin_a, INVENTORY_CSV, "inventory_items", "Inventario")
    impact = admin_a.get("/api/v1/dashboard").json()["impact"]
    by_kind = impact["open_by_kind"]
    # Excess (400 = (500 − 100) × 1) and no-movement (5 × 100 = 500) are both immobilized capital
    assert by_kind == {"capital_tied": {"amount": 900.0, "findings": 2}}
    assert "no se suman" in impact["note"]


def test_findings_filters_and_export(admin_a):
    import_csv(admin_a, INVENTORY_CSV, "inventory_items", "Inventario")
    hyp = admin_a.get("/api/v1/findings", params={"nature": "hypothesis"}).json()
    assert hyp["total"] >= 1 and all(f["nature"] == "hypothesis" for f in hyp["items"])
    crit = admin_a.get("/api/v1/findings", params=[("priority", "critical"), ("priority", "high")]).json()
    assert all(f["priority"] in ("critical", "high") for f in crit["items"])
    r = admin_a.get("/api/v1/findings/export")
    assert r.status_code == 200 and r.content[:2] == b"PK"
