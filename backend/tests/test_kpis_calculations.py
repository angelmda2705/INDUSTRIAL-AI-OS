"""KPI formulas checked against values computed by hand (see comments)."""

import math

import pytest

from app.services.analytics.domain import fleet, inventory, maintenance, production
from app.services.analytics.frames import records_frame
from app.services.analytics.kpis import KPIS
from app.services.analytics.stats import mann_kendall, robust_z_scores
from app.services.imports.templates import FUEL, INVENTORY, MAINTENANCE, PRODUCTION
from app.services.organizations import DEFAULT_ORG_SETTINGS

S = DEFAULT_ORG_SETTINGS


def frame(template, rows):
    return records_frame([(i + 1, i + 2, r) for i, r in enumerate(rows)], template)


def kpi(code, df):
    return KPIS[code].compute(df)


@pytest.fixture
def prod():
    rows = [
        dict(date="2024-01-10", work_center="L1", planned_qty=100, produced_qty=90, scrap_qty=10, planned_time_min=480,
             run_time_min=400, downtime_min=60, std_time_per_unit_min=4),
        dict(date="2024-01-11", work_center="L2", planned_qty=200, produced_qty=150, scrap_qty=0, planned_time_min=480,
             run_time_min=300, downtime_min=150, std_time_per_unit_min=2),
        dict(date="2024-02-01", work_center="L1", produced_qty=50),
    ]
    return production.prepare(frame(PRODUCTION, rows), S)


def test_production_kpis(prod):
    r = kpi("production_compliance", prod)
    assert r.value == pytest.approx(80.0) and r.sample_size == 2  # 240 / 300
    assert r.inputs == {"produced_qty": 240.0, "planned_qty": 300.0}
    assert kpi("scrap_rate", prod).value == pytest.approx(4.0)  # 10 / (240 + 10)
    assert kpi("capacity_utilization", prod).value == pytest.approx(700 / 960 * 100, abs=1e-3)
    assert kpi("downtime_rate", prod).value == pytest.approx(21.875)
    assert kpi("productivity_units_per_hour", prod).value == pytest.approx(240 / (700 / 60), abs=1e-3)
    assert kpi("performance_efficiency", prod).value == pytest.approx(100.0)  # (100·4 + 150·2) / 700


def test_production_kpis_by_subset_and_insufficient(prod):
    assert kpi("production_compliance", prod[prod.work_center == "L2"]).value == pytest.approx(75.0)
    feb = prod[prod["_month"].astype(str) == "2024-02-01"]
    r = kpi("production_compliance", feb)
    assert r.status == "insufficient_data" and r.value is None and r.message


@pytest.fixture
def mnt():
    rows = [
        dict(asset_code="P1", event_type="falla", event_start="2024-01-01T00:00:00", event_end="2024-01-01T04:00:00",
             parts_cost=100, labor_cost=50),
        dict(asset_code="P1", event_type="falla", event_start="2024-01-03T04:00:00", event_end="2024-01-03T06:00:00"),
        dict(asset_code="P1", event_type="falla", event_start="2024-01-05T06:00:00", event_end="2024-01-05T12:00:00"),
        dict(asset_code="P2", event_type="falla", event_start="2024-01-02T00:00:00", event_end="2024-01-02T08:00:00"),
        dict(asset_code="P2", event_type="falla", event_start="2024-01-04T08:00:00", event_end=None),
        dict(asset_code="P2", event_type="falla", event_start="2024-01-06T00:00:00", event_end="2024-01-06T01:00:00"),
        dict(asset_code="P1", event_type="preventivo", event_start="2024-01-10T08:00:00", scheduled_date="2024-01-10"),
        dict(asset_code="P2", event_type="preventivo", event_start="2024-01-12T08:00:00", scheduled_date="2024-01-11"),
    ]
    return maintenance.prepare(frame(MAINTENANCE, rows), S)


def test_maintenance_kpis(mnt):
    mttr = kpi("mttr_hours", mnt)
    assert mttr.value == pytest.approx(4.2) and mttr.sample_size == 5  # (4+2+6+8+1)/5
    mtbf = kpi("mtbf_hours", mnt)
    assert mtbf.value == pytest.approx(48.0) and mtbf.sample_size == 3  # P2's 3rd failure follows an open repair
    assert kpi("availability_inherent", mnt).value == pytest.approx(48 / 52.2 * 100, abs=1e-3)
    assert kpi("preventive_on_time", mnt).value == pytest.approx(50.0)
    cost = kpi("maintenance_cost_total", mnt)
    assert cost.value == 150.0 and cost.sample_size == 1
    assert kpi("failure_count", mnt).value == 6
    assert mnt.loc[mnt["event_start"].astype(str) == "2024-01-06 00:00:00", "_interval_issue"].iloc[0] == "previous_without_end"


def test_mtbf_refuses_insufficient_history(mnt):
    r = kpi("mtbf_hours", mnt[mnt.asset_code == "P1"].head(2))
    assert r.status == "insufficient_data" and "intervalos" in r.message
    assert kpi("availability_inherent", mnt.head(2)).status == "insufficient_data"


@pytest.fixture
def inv():
    rows = [
        dict(sku="S1", on_hand_qty=10, unit_cost=2, avg_daily_demand=5, demand_std_daily=2, lead_time_days=4, max_qty=100,
             last_movement_date="2024-06-01"),
        dict(sku="S2", on_hand_qty=0, unit_cost=10, avg_daily_demand=1, lead_time_days=9, last_movement_date="2024-06-30"),
        dict(sku="S3", on_hand_qty=500, unit_cost=1, avg_daily_demand=2, demand_std_daily=1, lead_time_days=1, max_qty=100,
             last_movement_date="2024-06-30"),
        dict(sku="S4", on_hand_qty=5, unit_cost=100, last_movement_date="2023-12-01"),
    ]
    return inventory.prepare(frame(INVENTORY, rows), S).set_index("sku")


def test_inventory_item_metrics(inv):
    assert inv.loc["S1", "_safety_stock"] == pytest.approx(1.645 * 2 * 2)
    assert inv.loc["S1", "_rop"] == pytest.approx(20 + 6.58)
    assert inv.loc["S2", "_rop"] == pytest.approx(9.0) and "sin stock" in inv.loc["S2", "_rop_basis"]
    assert bool(inv.loc["S1", "_below_rop"]) and bool(inv.loc["S2", "_stockout"])
    assert inv.loc["S3", "_excess_value"] == pytest.approx(400.0)
    assert list(inv["_abc"]) == ["A", "A", "B", "Sin clasificar"]
    assert bool(inv.loc["S4", "_obsolete_candidate"]) and inv.loc["S4", "_days_without_movement"] == 212
    assert not bool(inv.loc["S1", "_obsolete_candidate"])
    assert inv.loc["S1", "_suggested_order_qty"] == pytest.approx(90.0)  # max − on hand
    assert inv.loc["S2", "_suggested_order_qty"] == pytest.approx(18.0)  # ROP + d·L − on hand


def test_inventory_kpis(inv):
    df = inv.reset_index()
    assert kpi("inventory_value", df).value == pytest.approx(1020.0)
    assert kpi("items_below_reorder_point_pct", df).value == pytest.approx(200 / 3, abs=1e-3)
    assert kpi("stockout_items_pct", df).value == pytest.approx(100 / 3, abs=1e-3)
    assert kpi("inventory_coverage_days", df).value == pytest.approx(520 / 22, abs=1e-2)
    assert kpi("obsolete_inventory_share", df).value == pytest.approx(500 / 1020 * 100, abs=1e-3)


@pytest.fixture
def fuel():
    rows = [
        dict(vehicle_code="V1", date="2024-01-01T08:00:00", odometer_km=1000, liters=50, total_cost=1000, full_tank=True),
        dict(vehicle_code="V1", date="2024-01-05T08:00:00", odometer_km=1300, liters=30, total_cost=600, full_tank=False),
        dict(vehicle_code="V1", date="2024-01-10T08:00:00", odometer_km=1600, liters=70, total_cost=1400, full_tank=True),
        dict(vehicle_code="V1", date="2024-01-15T08:00:00", odometer_km=1600, liters=10, total_cost=200, full_tank=True),
        dict(vehicle_code="V1", date="2024-01-20T08:00:00", odometer_km=2100, liters=100, total_cost=2000, full_tank=True),
        dict(vehicle_code="V2", date="2024-01-01T08:00:00", odometer_km=0, liters=10),
        dict(vehicle_code="V2", date="2024-01-08T08:00:00", odometer_km=400, liters=50, total_cost=1000),
    ]
    return fleet.prepare(frame(FUEL, rows), S)


def test_fuel_tank_to_tank(fuel):
    kml = fuel["_kml"].tolist()
    assert math.isnan(kml[0]) and math.isnan(kml[1])
    assert kml[2] == pytest.approx(6.0)  # 600 km / (30 + 70) l, partial fill accumulated
    assert bool(fuel["_odometer_issue"].iloc[3])
    assert kml[4] == pytest.approx(5.0)
    assert kml[6] == pytest.approx(8.0)
    assert kpi("fuel_efficiency_km_l", fuel).value == pytest.approx(6.0)  # 1500 / 250
    assert kpi("fuel_cost_per_km", fuel).value == pytest.approx(5000 / 1500, abs=1e-4)
    assert kpi("fuel_cost_total", fuel).value == pytest.approx(6200.0)


def test_robust_z_and_mann_kendall():
    z = robust_z_scores([1, 2, 3, 4, 100])
    assert z[-1] == pytest.approx(0.6745 * 97)
    assert robust_z_scores([5, 5, 5, 5, 9]) is None  # MAD = 0
    t = mann_kendall([1, 2, 3, 4, 5, 6, 7, 8])
    assert t.s == 28 and t.direction == "increasing" and t.sen_slope == 1
    assert t.z == pytest.approx(27 / math.sqrt(8 * 7 * 21 / 18), abs=1e-6)
    assert t.p_value < 0.001
    assert mann_kendall([3, 1, 4, 1, 5, 2, 3, 2]).direction == "none"
    assert mann_kendall([1, 2]) is None


def test_every_kpi_is_documented():
    for k in KPIS.values():
        assert k.formula and k.unit and k.min_requirements and k.missing_handling and k.description
        assert k.direction in ("higher_is_better", "lower_is_better", "neutral")
