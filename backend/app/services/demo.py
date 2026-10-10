"""Clearly-labelled demonstration data.

Demo data is synthetic, generated with a fixed random seed, flagged with
``is_demo`` on datasets, import jobs and findings, and its dataset names start
with "[DEMO]". It goes through the regular import pipeline (upload → validate
→ commit → analysis) so the demo exercises the same code as real data.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.models import Dataset, ImportJob
from app.services import audit, storage
from app.services.analytics.engine import run_analysis
from app.services.context import RequestContext
from app.services.datasets import purge_dataset
from app.services.imports import service as imports

DEMO_PREFIX = "[DEMO]"
SEED = 20240501
END = date(2024, 12, 31)


def _csv(header: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def production_csv(rng: np.random.Generator) -> bytes:
    rows = []
    start = date(2024, 5, 1)
    centers = {"Línea 1": (0.01, 25), "Línea 2": (0.015, 30), "Línea 3": (0.02, 95)}
    day = start
    month_index = 0
    while day <= END:
        month_index = (day.year - start.year) * 12 + day.month - start.month
        if day.weekday() < 6:
            for wc, (scrap_base, downtime_mean) in centers.items():
                for shift in ("Matutino", "Vespertino"):
                    planned = 480.0
                    downtime = max(0.0, rng.normal(downtime_mean, downtime_mean * 0.35))
                    run = max(0.0, planned - downtime - rng.uniform(5, 15))
                    std = 0.9
                    total_units = run / std * rng.uniform(0.86, 0.96)
                    scrap_rate = scrap_base + (0.006 * month_index if wc == "Línea 2" else 0) + rng.normal(0, 0.003)
                    scrap = max(0.0, total_units * scrap_rate)
                    good = total_units - scrap
                    rows.append([day.strftime("%d/%m/%Y"), wc, "Producto A" if wc != "Línea 3" else "Producto B", shift,
                                 f"OP-{day:%m%d}-{wc[-1]}{shift[0]}", 500, round(good), round(scrap), planned,
                                 round(run, 1), round(downtime, 1), std])
        day += timedelta(days=1)
    return _csv(["Fecha", "Centro de trabajo", "Producto", "Turno", "Orden", "Cantidad planeada", "Piezas buenas",
                 "Scrap", "Tiempo programado", "Tiempo de operación", "Tiempo muerto", "Tiempo estándar"], rows)


def maintenance_csv(rng: np.random.Generator) -> bytes:
    rows = []
    assets = {"PRENSA-01": 900, "PRENSA-02": 260, "TORNO-01": 1100, "COMPRESOR-01": 700, "MONTACARGAS-01": 800, "ROBOT-01": 1500}
    causes = ["Desgaste de rodamiento", "Falla eléctrica", "Fuga de aceite", "Sensor dañado", "Ajuste mecánico"]
    start = datetime(2024, 1, 1, 7, 0)
    end = datetime(2024, 12, 31, 23, 0)
    ot = 1000
    for asset, mtbf in assets.items():
        t = start + timedelta(hours=float(rng.exponential(mtbf)))
        while t < end:
            repair = float(rng.lognormal(np.log(5), 0.5))
            if asset == "PRENSA-02":
                cause = "Falla hidráulica" if rng.random() < 0.7 else causes[int(rng.integers(len(causes)))]
            else:
                cause = causes[int(rng.integers(len(causes)))]
            ot += 1
            fin = t + timedelta(hours=repair)
            rows.append([asset, "falla", t.strftime("%Y-%m-%d %H:%M"), fin.strftime("%Y-%m-%d %H:%M"), "", cause,
                         f"OT-{ot}", round(repair * 1.5, 1), round(float(rng.uniform(800, 6000)), 2), round(repair * 1.5 * 180, 2), ""])
            t = fin + timedelta(hours=float(rng.exponential(mtbf)))
        # Preventive plan every 60 days; some executions are late on purpose.
        sched = date(2024, 1, 15)
        while sched < END:
            delay = int(rng.choice([0, 0, 0, 1, 3, 9]))
            done = datetime.combine(sched + timedelta(days=delay), datetime.min.time()) + timedelta(hours=8)
            ot += 1
            rows.append([asset, "preventivo", done.strftime("%Y-%m-%d %H:%M"), (done + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
                         sched.isoformat(), "", f"OT-{ot}", 2, round(float(rng.uniform(300, 1200)), 2), 360, ""])
            sched += timedelta(days=60)
    ot += 1
    rows.append(["ROBOT-01", "falla", "2024-09-02 10:00", "2024-09-07 18:00", "", "Tarjeta de control (espera de refacción)",
                 f"OT-{ot}", 12, 38500, 2160, 4500])
    return _csv(["Equipo", "Tipo", "Inicio", "Fin", "Fecha programada", "Causa", "OT", "Horas hombre", "Refacciones",
                 "Mano de obra", "Otros costos"], rows)


def inventory_csv(rng: np.random.Generator) -> bytes:
    rows = []
    categories = ["Materia prima", "Refacciones", "Empaque", "Consumibles"]
    for i in range(1, 81):
        demand = float(rng.lognormal(1.5, 1.0))
        cost = float(rng.lognormal(4, 1.0))
        lead = float(rng.choice([3, 5, 7, 10, 15, 21]))
        sigma = demand * float(rng.uniform(0.2, 0.6))
        rop = demand * lead + 1.645 * sigma * lead ** 0.5
        roll = rng.random()
        if roll < 0.08:
            on_hand = 0
        elif roll < 0.25:
            on_hand = rop * float(rng.uniform(0.3, 0.95))
        elif roll < 0.35:
            on_hand = rop * float(rng.uniform(4, 8))
        else:
            on_hand = rop * float(rng.uniform(1.2, 2.5))
        max_qty = rop * 2.5
        last_move = END - timedelta(days=int(rng.integers(200, 400) if rng.random() < 0.1 else rng.integers(0, 60)))
        if i == 77:
            on_hand = -4
        rows.append([f"SKU-{i:04d}", f"Artículo de ejemplo {i}", categories[i % 4], "pza", "Almacén central",
                     round(on_hand), round(cost, 2), round(demand, 2), round(sigma, 2), lead, round(rop * 0.5),
                     round(max_qty), last_move.strftime("%d/%m/%Y")])
    return _csv(["SKU", "Descripción", "Categoría", "Unidad", "Almacén", "Existencia", "Costo unitario", "Demanda diaria",
                 "Desviación demanda", "Lead time", "Mínimo", "Máximo", "Último movimiento"], rows)


def fuel_csv(rng: np.random.Generator) -> bytes:
    rows = []
    vehicles = {"CAM-101": 3.1, "CAM-102": 3.3, "CAM-103": 2.9, "CAM-104": 3.2, "VAN-201": 8.5}
    for code, kml in vehicles.items():
        odo = float(rng.uniform(40000, 120000))
        t = datetime(2024, 7, 1, 8, 0)
        k = 0
        while t < datetime(2024, 12, 31):
            km = float(rng.uniform(450, 900)) if code.startswith("CAM") else float(rng.uniform(250, 500))
            eff = kml * float(rng.normal(1, 0.035))
            if code == "CAM-103" and k in (14, 19, 23):
                eff = kml * 0.62
            liters = km / eff
            odo += km
            price = float(rng.uniform(23.5, 25.5))
            rows.append([code, t.strftime("%d/%m/%Y %H:%M"), round(odo), round(liters, 1), round(liters * price, 2),
                         f"OPR-{int(rng.integers(1, 9)):02d}", "Ruta Norte" if code != "VAN-201" else "Reparto urbano", "sí"])
            t += timedelta(days=int(rng.integers(3, 6)))
            k += 1
    return _csv(["Unidad", "Fecha", "Odómetro", "Litros", "Importe", "Conductor", "Ruta", "Tanque lleno"], rows)


DEMO_SETS = [
    ("production_records", f"{DEMO_PREFIX} Producción planta ejemplo", "demo_produccion.csv", production_csv),
    ("maintenance_events", f"{DEMO_PREFIX} Mantenimiento equipos ejemplo", "demo_mantenimiento.csv", maintenance_csv),
    ("inventory_items", f"{DEMO_PREFIX} Inventario almacén ejemplo", "demo_inventario.csv", inventory_csv),
    ("fuel_logs", f"{DEMO_PREFIX} Combustible flotilla ejemplo", "demo_combustible.csv", fuel_csv),
]


def load_demo(db: Session, ctx: RequestContext) -> list[Dataset]:
    exists = db.execute(
        select(Dataset.id).where(Dataset.organization_id == ctx.org_id, Dataset.is_demo.is_(True)).limit(1)
    ).first()
    if exists:
        raise Conflict("Los datos de demostración ya están cargados. Elimínalos antes de volver a cargarlos.")
    rng = np.random.default_rng(SEED)
    created: list[Dataset] = []
    for template, name, filename, generator in DEMO_SETS:
        job = imports.upload(db, ctx, filename, generator(rng), is_demo=True)
        preview = imports.preview(db, ctx, job)
        mapping = preview["suggested_mappings"][template]
        imports.validate(db, ctx, job, template_code=template, mapping=mapping, dataset_id=None, dataset_name=name,
                         decimal_separator=".", date_format="dayfirst")
        job = imports.commit(db, ctx, job.id, skip_invalid=True, skip_duplicates=True,
                             dataset_description="Datos sintéticos de demostración. No pertenecen a ninguna empresa.")
        dataset = db.get(Dataset, job.target_dataset_id)
        run_analysis(db, ctx, dataset, trigger="demo")
        created.append(dataset)
    audit.record(db, ctx, "demo.loaded", details={"datasets": [d.id for d in created]})
    db.commit()
    return created


def remove_demo(db: Session, ctx: RequestContext) -> int:
    datasets = list(db.execute(select(Dataset).where(Dataset.organization_id == ctx.org_id, Dataset.is_demo.is_(True))).scalars())
    for ds in datasets:
        purge_dataset(db, ctx.org_id, ds.id)
    jobs = list(db.execute(select(ImportJob).where(ImportJob.organization_id == ctx.org_id, ImportJob.is_demo.is_(True))).scalars())
    for job in jobs:
        storage.delete(ctx.org_id, "imports", job.stored_filename)
        db.delete(job)
    audit.record(db, ctx, "demo.removed", details={"datasets": len(datasets), "import_jobs": len(jobs)})
    db.commit()
    return len(datasets)
