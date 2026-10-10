import threading

from fastapi.testclient import TestClient

from tests.conftest import upload_csv

CSV = """Fecha,Centro de trabajo,Producto,Cantidad planeada,Piezas buenas,Scrap
01/03/2024,L1,A,100,90,5
02/03/2024,L1,A,100,95,2
02/03/2024,L1,A,100,95,2
03/03/2024,L1,A,100,abc,1
,L2,A,100,80,1
"""


def _validate(client, job_id, **extra):
    preview = client.get(f"/api/v1/imports/{job_id}/preview").json()
    body = {"template_code": "production_records", "mapping": preview["suggested_mappings"]["production_records"],
            "dataset_name": "Producción marzo", **extra}
    return client.post(f"/api/v1/imports/{job_id}/validate", json=body)


def test_full_import_workflow(admin_a):
    r = upload_csv(admin_a, CSV)
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "parsed" and job["total_rows"] == 5 and len(job["file_sha256"]) == 64

    preview = admin_a.get(f"/api/v1/imports/{job['id']}/preview").json()
    assert [c["name"] for c in preview["columns"]][:2] == ["Fecha", "Centro de trabajo"]
    assert preview["columns"][3]["kind"] == "número"
    assert preview["rows"][0] == {"row": 2, "values": ["01/03/2024", "L1", "A", "100", "90", "5"]}

    r = _validate(admin_a, job["id"])
    assert r.status_code == 200
    s = r.json()["summary"]
    assert (s["valid_rows"], s["invalid_rows"], s["duplicate_rows"]) == (3, 2, 1)
    assert {(e["row"], e["field"]) for e in s["errors"]} == {(5, "produced_qty"), (6, "date")}
    assert s["duplicates_in_file"] == [{"row": 4, "duplicate_of_row": 3}]

    r = admin_a.post(f"/api/v1/imports/{job['id']}/commit", json={"skip_invalid": False})
    assert r.status_code == 422 and r.json()["error"]["code"] == "rows_with_errors"

    r = admin_a.post(f"/api/v1/imports/{job['id']}/commit", json={"skip_invalid": True, "skip_duplicates": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job"]["status"] == "committed" and body["job"]["imported_rows"] == 2
    assert body["analysis_run"]["status"] == "completed"
    ds_id = body["job"]["target_dataset_id"]

    records = admin_a.get(f"/api/v1/datasets/{ds_id}/records").json()
    assert records["total"] == 2
    assert records["items"][0]["data"] == {"date": "2024-03-01", "work_center": "L1", "product": "A", "planned_qty": 100.0,
                                          "produced_qty": 90.0, "scrap_qty": 5.0}
    assert records["items"][0]["source_row"] == 2

    # Committing twice is rejected
    assert admin_a.post(f"/api/v1/imports/{job['id']}/commit", json={}).status_code == 409


def test_reimporting_same_rows_into_dataset_skips_existing(admin_a):
    first = upload_csv(admin_a, CSV).json()
    _validate(admin_a, first["id"])
    ds_id = admin_a.post(f"/api/v1/imports/{first['id']}/commit", json={}).json()["job"]["target_dataset_id"]

    second = upload_csv(admin_a, CSV).json()
    preview = admin_a.get(f"/api/v1/imports/{second['id']}/preview").json()
    assert preview["same_file_committed_import_ids"] == [first["id"]]
    s = admin_a.post(f"/api/v1/imports/{second['id']}/validate", json={
        "template_code": "production_records", "mapping": preview["suggested_mappings"]["production_records"],
        "dataset_id": ds_id}).json()["summary"]
    assert s["importable_rows_without_duplicates"] == 0
    r = admin_a.post(f"/api/v1/imports/{second['id']}/commit", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "nothing_to_import"


def test_revert_removes_exactly_the_imported_rows(admin_a):
    a = upload_csv(admin_a, CSV).json()
    _validate(admin_a, a["id"])
    ds_id = admin_a.post(f"/api/v1/imports/{a['id']}/commit", json={}).json()["job"]["target_dataset_id"]
    extra = "Fecha,Centro de trabajo,Producto,Cantidad planeada,Piezas buenas,Scrap\n10/03/2024,L3,B,50,49,1\n"
    b = upload_csv(admin_a, extra).json()
    preview = admin_a.get(f"/api/v1/imports/{b['id']}/preview").json()
    admin_a.post(f"/api/v1/imports/{b['id']}/validate", json={
        "template_code": "production_records", "mapping": preview["suggested_mappings"]["production_records"], "dataset_id": ds_id})
    admin_a.post(f"/api/v1/imports/{b['id']}/commit", json={})
    assert admin_a.get(f"/api/v1/datasets/{ds_id}").json()["dataset"]["row_count"] == 3

    r = admin_a.post(f"/api/v1/imports/{a['id']}/revert")
    assert r.status_code == 200 and r.json()["job"]["status"] == "reverted"
    detail = admin_a.get(f"/api/v1/datasets/{ds_id}").json()
    assert detail["dataset"]["row_count"] == 1
    rows = admin_a.get(f"/api/v1/datasets/{ds_id}/records").json()["items"]
    assert [r["data"]["work_center"] for r in rows] == ["L3"]
    assert admin_a.post(f"/api/v1/imports/{a['id']}/revert").status_code == 409
    assert admin_a.delete(f"/api/v1/imports/{a['id']}").status_code == 409  # kept for traceability


def test_mapping_errors_are_explained(admin_a):
    job = upload_csv(admin_a, CSV).json()
    r = admin_a.post(f"/api/v1/imports/{job['id']}/validate", json={
        "template_code": "production_records", "mapping": {"date": "Fecha"}, "dataset_name": "X X X"})
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"work_center", "produced_qty"} <= fields
    r = admin_a.post(f"/api/v1/imports/{job['id']}/validate", json={"template_code": "nope", "mapping": {}})
    assert r.status_code == 422


def test_generic_template_profiles_any_table(admin_a):
    job = upload_csv(admin_a, "Col A,Col B\n1,x\n2,\n2,\n").json()
    r = admin_a.post(f"/api/v1/imports/{job['id']}/validate", json={"template_code": "generic", "dataset_name": "Genérico"})
    s = r.json()["summary"]
    assert s["valid_rows"] == 3 and s["duplicate_rows"] == 1
    body = admin_a.post(f"/api/v1/imports/{job['id']}/commit", json={"skip_duplicates": False}).json()
    detail = admin_a.get(f"/api/v1/datasets/{body['job']['target_dataset_id']}").json()
    fields = {f["field"]: f for f in detail["profile"]["fields"]}
    assert fields["Col B"]["missing"] == 2
    assert detail["profile"]["row_count"] == 3


def test_upload_validation(admin_a):
    r = admin_a.post("/api/v1/imports", files={"file": ("x.exe", b"MZ....", "application/octet-stream")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_file"
    r = admin_a.post("/api/v1/imports", files={"file": ("vacío.csv", b"", "text/csv")})
    assert r.status_code == 422
    r = admin_a.post("/api/v1/imports", files={"file": ("../../etc/passwd.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 201 and r.json()["original_filename"] == "passwd.csv"


def test_discard_uncommitted_import(admin_a):
    job = upload_csv(admin_a, CSV).json()
    assert admin_a.delete(f"/api/v1/imports/{job['id']}").status_code == 200
    assert admin_a.get(f"/api/v1/imports/{job['id']}").status_code == 404


def test_concurrent_commits_import_rows_only_once(admin_a, app):
    job = upload_csv(admin_a, CSV).json()
    _validate(admin_a, job["id"])
    results = []
    barrier = threading.Barrier(2)

    def commit():
        client = TestClient(app)
        client.cookies.update(admin_a.c.cookies)
        client.headers["X-CSRF-Token"] = admin_a.c.headers["X-CSRF-Token"]
        barrier.wait()
        results.append(client.post(f"/api/v1/imports/{job['id']}/commit", json={"run_analysis": False}).status_code)

    threads = [threading.Thread(target=commit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 409], results
    ds = admin_a.get("/api/v1/datasets").json()
    assert len(ds) == 1 and ds[0]["row_count"] == 2
    assert admin_a.get(f"/api/v1/datasets/{ds[0]['id']}/records").json()["total"] == 2
