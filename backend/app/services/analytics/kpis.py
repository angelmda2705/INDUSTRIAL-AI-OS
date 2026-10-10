"""Central KPI catalog.

Each KPI documents its formula, unit, data source, minimum requirements,
missing-value treatment and assumptions. ``compute`` receives the prepared
row-level frame (see ``domain/``) — possibly a subset for a month or a
dimension value — and returns a :class:`KpiResult`. When requirements are not
met the result has ``status = insufficient_data`` and no value; the platform
never fills in a number in that case.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from app.services.analytics.frames import present
from app.services.analytics.stats import round_or_none, safe_ratio


@dataclass
class KpiResult:
    value: float | None
    status: str  # ok | insufficient_data
    sample_size: int = 0
    inputs: dict = field(default_factory=dict)
    message: str | None = None


def ok(value: float | None, n: int, inputs: dict, digits: int = 4) -> KpiResult:
    if value is None:
        return KpiResult(None, "insufficient_data", n, inputs, "El denominador es cero; no se puede calcular.")
    return KpiResult(round_or_none(value, digits), "ok", n, {k: round_or_none(v, 4) if isinstance(v, float) else v for k, v in inputs.items()})


def insufficient(message: str, n: int = 0) -> KpiResult:
    return KpiResult(None, "insufficient_data", n, {}, message)


@dataclass(frozen=True)
class KpiDefinition:
    code: str
    name: str
    area: str
    template: str
    description: str
    formula: str
    unit: str
    frequency: str
    required_fields: tuple[str, ...]
    min_requirements: str
    missing_handling: str
    assumptions: tuple[str, ...]
    direction: str  # higher_is_better | lower_is_better | neutral
    compute: Callable[[pd.DataFrame], KpiResult]
    dimension: str | None = None
    monthly: bool = True

    def public(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "area": self.area,
            "template": self.template,
            "description": self.description,
            "formula": self.formula,
            "unit": self.unit,
            "frequency": self.frequency,
            "required_fields": list(self.required_fields),
            "min_requirements": self.min_requirements,
            "missing_handling": self.missing_handling,
            "assumptions": list(self.assumptions),
            "direction": self.direction,
            "dimension": self.dimension,
            "monthly": self.monthly,
        }


# --- Production ---------------------------------------------------------------


def _production_compliance(df: pd.DataFrame) -> KpiResult:
    rows = present(df, "planned_qty", "produced_qty")
    rows = rows[rows["planned_qty"] > 0]
    if rows.empty:
        return insufficient("Se requiere al menos un registro con cantidad planeada mayor a cero.")
    num, den = float(rows["produced_qty"].sum()), float(rows["planned_qty"].sum())
    return ok(safe_ratio(num, den) * 100, len(rows), {"produced_qty": num, "planned_qty": den})


def _scrap_rate(df: pd.DataFrame) -> KpiResult:
    rows = present(df, "scrap_qty", "produced_qty")
    if rows.empty:
        return insufficient("Se requiere la columna de desperdicio con valores.")
    scrap, good = float(rows["scrap_qty"].sum()), float(rows["produced_qty"].sum())
    total = scrap + good
    return ok(scrap / total * 100 if total > 0 else None, len(rows), {"scrap_qty": scrap, "good_qty": good})


def _utilization(df: pd.DataFrame) -> KpiResult:
    rows = present(df, "run_time_min", "planned_time_min")
    rows = rows[rows["planned_time_min"] > 0]
    if rows.empty:
        return insufficient("Se requieren tiempo de operación y tiempo programado.")
    run, planned = float(rows["run_time_min"].sum()), float(rows["planned_time_min"].sum())
    return ok(safe_ratio(run, planned) * 100, len(rows), {"run_time_min": run, "planned_time_min": planned})


def _downtime_rate(df: pd.DataFrame) -> KpiResult:
    rows = present(df, "downtime_min", "planned_time_min")
    rows = rows[rows["planned_time_min"] > 0]
    if rows.empty:
        return insufficient("Se requieren tiempo muerto y tiempo programado.")
    down, planned = float(rows["downtime_min"].sum()), float(rows["planned_time_min"].sum())
    return ok(safe_ratio(down, planned) * 100, len(rows), {"downtime_min": down, "planned_time_min": planned})


def _productivity(df: pd.DataFrame) -> KpiResult:
    rows = present(df, "produced_qty", "run_time_min")
    rows = rows[rows["run_time_min"] > 0]
    if rows.empty:
        return insufficient("Se requiere tiempo de operación mayor a cero.")
    units, minutes = float(rows["produced_qty"].sum()), float(rows["run_time_min"].sum())
    return ok(units / (minutes / 60.0), len(rows), {"produced_qty": units, "run_time_h": minutes / 60.0})


def _performance(df: pd.DataFrame) -> KpiResult:
    rows = present(df, "produced_qty", "run_time_min", "std_time_per_unit_min")
    rows = rows[rows["run_time_min"] > 0]
    if rows.empty:
        return insufficient("Se requieren tiempo estándar por unidad y tiempo de operación.")
    earned = float(((rows["produced_qty"] + rows["scrap_qty"].fillna(0)) * rows["std_time_per_unit_min"]).sum())
    run = float(rows["run_time_min"].sum())
    return ok(earned / run * 100, len(rows), {"standard_minutes_earned": earned, "run_time_min": run})


# --- Maintenance ----------------------------------------------------------------

MIN_REPAIRS = 3
MIN_INTERVALS = 3


def _mttr(df: pd.DataFrame) -> KpiResult:
    repairs = df.loc[df["_is_failure"] & df["_repair_h"].notna(), "_repair_h"]
    if len(repairs) < MIN_REPAIRS:
        return insufficient(f"Se requieren al menos {MIN_REPAIRS} fallas con fecha de fin (hay {len(repairs)}).", len(repairs))
    return ok(float(repairs.mean()), len(repairs), {"total_repair_h": float(repairs.sum()), "repairs": int(len(repairs))})


def _mtbf(df: pd.DataFrame) -> KpiResult:
    intervals = df["_uptime_before_h"].dropna()
    if len(intervals) < MIN_INTERVALS:
        return insufficient(
            f"Se requieren al menos {MIN_INTERVALS} intervalos entre fallas consecutivas del mismo equipo (hay {len(intervals)}).",
            len(intervals),
        )
    return ok(float(intervals.mean()), len(intervals), {"total_uptime_h": float(intervals.sum()), "intervals": int(len(intervals))})


def _availability(df: pd.DataFrame) -> KpiResult:
    mtbf, mttr = _mtbf(df), _mttr(df)
    if mtbf.status != "ok" or mttr.status != "ok":
        return insufficient("Requiere MTBF y MTTR calculables.", min(mtbf.sample_size, mttr.sample_size))
    return ok(mtbf.value / (mtbf.value + mttr.value) * 100, min(mtbf.sample_size, mttr.sample_size),
              {"mtbf_h": mtbf.value, "mttr_h": mttr.value})


def _maintenance_cost(df: pd.DataFrame) -> KpiResult:
    costs = df["_total_cost"].dropna()
    if costs.empty:
        return insufficient("No hay costos registrados (refacciones, mano de obra u otros).")
    return ok(float(costs.sum()), len(costs), {"events_with_cost": int(len(costs))}, digits=2)


def _failure_count(df: pd.DataFrame) -> KpiResult:
    n = int(df["_is_failure"].sum())
    return ok(float(n), len(df), {"failures": n}, digits=0)


def _preventive_on_time(df: pd.DataFrame) -> KpiResult:
    rows = df[df["_preventive_on_time"].notna()]
    if rows.empty:
        return insufficient("Se requieren preventivos con fecha programada.")
    on_time = int(rows["_preventive_on_time"].astype(bool).sum())
    return ok(on_time / len(rows) * 100, len(rows), {"on_time": on_time, "preventive_events": int(len(rows))})


# --- Inventory -------------------------------------------------------------------


def _inventory_value(df: pd.DataFrame) -> KpiResult:
    rows = df[df["_value"].notna()]
    if rows.empty:
        return insufficient("Se requiere costo unitario.")
    return ok(float(rows["_value"].sum()), len(rows), {"items_valued": int(len(rows)), "items_without_cost": int(df["_value"].isna().sum())}, 2)


def _below_rop_pct(df: pd.DataFrame) -> KpiResult:
    rows = df[df["_rop"].notna() & (df["avg_daily_demand"] > 0)]
    if rows.empty:
        return insufficient("Se requieren demanda diaria y tiempo de reposición.")
    below = int(rows["_below_rop"].sum())
    return ok(below / len(rows) * 100, len(rows), {"items_below_rop": below, "items_evaluated": int(len(rows))})


def _stockout_pct(df: pd.DataFrame) -> KpiResult:
    rows = df[df["avg_daily_demand"] > 0]
    if rows.empty:
        return insufficient("Se requiere demanda diaria para identificar artículos activos.")
    out = int(rows["_stockout"].sum())
    return ok(out / len(rows) * 100, len(rows), {"items_out_of_stock": out, "active_items": int(len(rows))})


def _coverage_days(df: pd.DataFrame) -> KpiResult:
    rows = present(df, "unit_cost", "avg_daily_demand")
    rows = rows[rows["on_hand_qty"] >= 0]
    daily_value = float((rows["avg_daily_demand"] * rows["unit_cost"]).sum())
    if rows.empty or daily_value <= 0:
        return insufficient("Se requieren demanda diaria y costo unitario.")
    stock_value = float((rows["on_hand_qty"] * rows["unit_cost"]).sum())
    return ok(stock_value / daily_value, len(rows), {"stock_value": stock_value, "daily_consumption_value": daily_value}, 2)


def _obsolete_share(df: pd.DataFrame) -> KpiResult:
    rows = df[df["_value"].notna() & df["last_movement_date"].notna()]
    total = float(rows["_value"].sum())
    if rows.empty or total <= 0:
        return insufficient("Se requieren costo unitario y fecha del último movimiento.")
    obsolete = float(rows.loc[rows["_obsolete_candidate"], "_value"].sum())
    return ok(obsolete / total * 100, len(rows), {"obsolete_candidate_value": obsolete, "inventory_value": total})


# --- Fleet -------------------------------------------------------------------------

MIN_FUEL_INTERVALS = 3


def _fuel_efficiency(df: pd.DataFrame) -> KpiResult:
    rows = df[df["_kml"].notna()]
    if len(rows) < MIN_FUEL_INTERVALS:
        return insufficient(f"Se requieren al menos {MIN_FUEL_INTERVALS} intervalos válidos entre cargas (hay {len(rows)}).", len(rows))
    km, liters = float(rows["_interval_km"].sum()), float(rows["_interval_liters"].sum())
    return ok(km / liters, len(rows), {"distance_km": km, "liters": liters})


def _cost_per_km(df: pd.DataFrame) -> KpiResult:
    rows = df[df["_kml"].notna() & df["_interval_cost"].notna()]
    if len(rows) < MIN_FUEL_INTERVALS:
        return insufficient("Se requieren importes de combustible en al menos 3 intervalos válidos.", len(rows))
    cost, km = float(rows["_interval_cost"].sum()), float(rows["_interval_km"].sum())
    return ok(cost / km, len(rows), {"fuel_cost": cost, "distance_km": km})


def _fuel_cost_total(df: pd.DataFrame) -> KpiResult:
    costs = df["total_cost"].dropna()
    if costs.empty:
        return insufficient("No hay importes de combustible registrados.")
    return ok(float(costs.sum()), len(costs), {"loads_with_cost": int(len(costs))}, 2)


_MISSING_ROWS = "Los registros sin los campos requeridos se excluyen del cálculo; el tamaño de muestra indica cuántos se usaron."

CATALOG: list[KpiDefinition] = [
    KpiDefinition(
        "production_compliance", "Cumplimiento de producción", "production", "production_records",
        "Proporción de la cantidad planeada que se produjo en buen estado.",
        "Σ cantidad buena producida ÷ Σ cantidad planeada × 100", "%", "mensual",
        ("produced_qty", "planned_qty"), "Al menos un registro con cantidad planeada > 0.", _MISSING_ROWS,
        ("La cantidad producida corresponde a unidades conformes.", "Puede superar 100 % si se produce más de lo planeado."),
        "higher_is_better", _production_compliance, "work_center",
    ),
    KpiDefinition(
        "scrap_rate", "Porcentaje de desperdicio", "production", "production_records",
        "Unidades rechazadas sobre el total de unidades procesadas.",
        "Σ desperdicio ÷ (Σ producidas buenas + Σ desperdicio) × 100", "%", "mensual",
        ("scrap_qty", "produced_qty"), "Columna de desperdicio con al menos un valor.", _MISSING_ROWS,
        ("Las unidades de desperdicio y buenas se miden en la misma unidad.",),
        "lower_is_better", _scrap_rate, "work_center",
    ),
    KpiDefinition(
        "capacity_utilization", "Utilización de capacidad", "production", "production_records",
        "Tiempo efectivamente produciendo respecto del tiempo programado.",
        "Σ tiempo de operación ÷ Σ tiempo programado × 100", "%", "mensual",
        ("run_time_min", "planned_time_min"), "Registros con tiempo programado > 0.", _MISSING_ROWS,
        ("El tiempo programado excluye paros planeados (comidas, mantenimiento programado).",),
        "higher_is_better", _utilization, "work_center",
    ),
    KpiDefinition(
        "downtime_rate", "Tiempo muerto", "production", "production_records",
        "Paros no planeados como proporción del tiempo programado.",
        "Σ tiempo muerto ÷ Σ tiempo programado × 100", "%", "mensual",
        ("downtime_min", "planned_time_min"), "Registros con tiempo programado > 0.", _MISSING_ROWS,
        ("El tiempo muerto registrado corresponde a paros no planeados.",),
        "lower_is_better", _downtime_rate, "work_center",
    ),
    KpiDefinition(
        "productivity_units_per_hour", "Productividad (unidades por hora)", "production", "production_records",
        "Unidades buenas por hora de operación.",
        "Σ cantidad buena ÷ (Σ tiempo de operación ÷ 60)", "u/h", "mensual",
        ("produced_qty", "run_time_min"), "Registros con tiempo de operación > 0.", _MISSING_ROWS,
        ("Solo es comparable entre centros o periodos con mezcla de productos similar.",),
        "higher_is_better", _productivity, "work_center",
    ),
    KpiDefinition(
        "performance_efficiency", "Eficiencia de desempeño", "production", "production_records",
        "Minutos estándar ganados respecto del tiempo de operación.",
        "Σ ((buenas + desperdicio) × tiempo estándar por unidad) ÷ Σ tiempo de operación × 100", "%", "mensual",
        ("produced_qty", "run_time_min", "std_time_per_unit_min"), "Tiempo estándar por unidad informado.", _MISSING_ROWS,
        ("Los tiempos estándar están vigentes y medidos correctamente.",),
        "higher_is_better", _performance, "work_center",
    ),
    KpiDefinition(
        "mttr_hours", "MTTR — tiempo medio de reparación", "maintenance", "maintenance_events",
        "Tiempo promedio desde la falla hasta que el equipo vuelve a estar disponible.",
        "Σ (fin − inicio) de fallas ÷ número de fallas con fin registrado", "h", "mensual",
        ("event_type", "event_start", "event_end"), f"Al menos {MIN_REPAIRS} fallas con fecha de fin.",
        "Las fallas sin fecha de fin se excluyen y se reportan como problema de calidad de datos.",
        ("Incluye tiempo de espera de refacciones y personal (tiempo total fuera de servicio).",),
        "lower_is_better", _mttr, "asset_code",
    ),
    KpiDefinition(
        "mtbf_hours", "MTBF — tiempo medio entre fallas", "maintenance", "maintenance_events",
        "Tiempo promedio en servicio entre una reparación y la siguiente falla del mismo equipo.",
        "Σ (inicio falla i+1 − fin falla i) ÷ número de intervalos, por equipo", "h", "mensual",
        ("asset_code", "event_type", "event_start", "event_end"), f"Al menos {MIN_INTERVALS} intervalos entre fallas consecutivas.",
        "Intervalos cuyo evento previo no tiene fecha de fin, o que se traslapan, se excluyen.",
        ("Usa tiempo calendario: asume que el equipo está disponible entre fallas. Para equipos que no operan 24/7 sobreestima el tiempo de operación.",
         "En el desglose mensual cada intervalo se asigna al mes de la falla que lo cierra."),
        "higher_is_better", _mtbf, "asset_code",
    ),
    KpiDefinition(
        "availability_inherent", "Disponibilidad inherente", "maintenance", "maintenance_events",
        "Proporción del tiempo en que el equipo está disponible considerando solo fallas y reparaciones.",
        "MTBF ÷ (MTBF + MTTR) × 100", "%", "mensual",
        ("asset_code", "event_type", "event_start", "event_end"), "MTBF y MTTR calculables.",
        "Hereda las exclusiones de MTBF y MTTR.",
        ("No incluye paros por mantenimiento preventivo ni falta de material (no es disponibilidad operativa).",),
        "higher_is_better", _availability, "asset_code",
    ),
    KpiDefinition(
        "maintenance_cost_total", "Costo de mantenimiento", "maintenance", "maintenance_events",
        "Suma de refacciones, mano de obra y otros costos de los eventos.",
        "Σ (refacciones + mano de obra + otros)", "moneda", "mensual",
        ("parts_cost", "labor_cost", "other_cost"), "Al menos un evento con costo.",
        "Los componentes de costo vacíos se consideran no informados (no cero) y el evento solo suma lo informado.",
        ("Los costos están expresados en la moneda configurada para la organización.",),
        "lower_is_better", _maintenance_cost, "asset_code",
    ),
    KpiDefinition(
        "failure_count", "Número de fallas", "maintenance", "maintenance_events",
        "Cantidad de eventos registrados como falla.", "Conteo de eventos con tipo = falla", "eventos", "mensual",
        ("event_type",), "Ninguno.", "No aplica.", ("Depende de que todas las fallas se registren.",),
        "lower_is_better", _failure_count, "asset_code",
    ),
    KpiDefinition(
        "preventive_on_time", "Puntualidad del mantenimiento preventivo", "maintenance", "maintenance_events",
        "Preventivos ejecutados a más tardar en su fecha programada (más la tolerancia configurada).",
        "Preventivos con inicio ≤ fecha programada + tolerancia ÷ preventivos con fecha programada × 100", "%", "mensual",
        ("event_type", "event_start", "scheduled_date"), "Preventivos con fecha programada.",
        "Preventivos sin fecha programada se excluyen.",
        ("Solo evalúa preventivos ejecutados; los programados no realizados no están en este conjunto de datos.",),
        "higher_is_better", _preventive_on_time, "asset_code",
    ),
    KpiDefinition(
        "inventory_value", "Valor del inventario", "inventory", "inventory_items",
        "Valor de las existencias a costo unitario.", "Σ max(existencia, 0) × costo unitario", "moneda", "por corte",
        ("on_hand_qty", "unit_cost"), "Costo unitario informado.", "Artículos sin costo no se valoran y se cuentan aparte.",
        ("Existencias negativas se valoran en cero (son un error de registro).",),
        "neutral", _inventory_value, "category", monthly=False,
    ),
    KpiDefinition(
        "items_below_reorder_point_pct", "Artículos en o bajo punto de reorden", "inventory", "inventory_items",
        "Proporción de artículos activos cuya existencia es menor o igual a su punto de reorden.",
        "Artículos con existencia ≤ ROP ÷ artículos con demanda y tiempo de reposición × 100; ROP = d·L + z·σ·√L",
        "%", "por corte", ("on_hand_qty", "avg_daily_demand", "lead_time_days"),
        "Demanda diaria y tiempo de reposición.", "Artículos sin demanda o sin tiempo de reposición no se evalúan.",
        ("Demanda aproximadamente normal y estable.", "No modela variabilidad del tiempo de reposición."),
        "lower_is_better", _below_rop_pct, "category", monthly=False,
    ),
    KpiDefinition(
        "stockout_items_pct", "Tasa de faltantes", "inventory", "inventory_items",
        "Proporción de artículos con demanda que tienen existencia cero o negativa.",
        "Artículos con demanda > 0 y existencia ≤ 0 ÷ artículos con demanda > 0 × 100", "%", "por corte",
        ("on_hand_qty", "avg_daily_demand"), "Demanda diaria informada.", "Artículos sin demanda no se evalúan.",
        ("Mide faltantes al momento del corte, no pedidos no surtidos.",),
        "lower_is_better", _stockout_pct, "category", monthly=False,
    ),
    KpiDefinition(
        "inventory_coverage_days", "Días de inventario (cobertura)", "inventory", "inventory_items",
        "Días que alcanzaría el inventario al ritmo de demanda actual, ponderado por valor.",
        "Σ existencia × costo ÷ Σ demanda diaria × costo", "días", "por corte",
        ("on_hand_qty", "unit_cost", "avg_daily_demand"), "Demanda y costo unitario.", _MISSING_ROWS,
        ("Aproxima días de inventario con demanda, no con costo de ventas contable.",),
        "neutral", _coverage_days, "category", monthly=False,
    ),
    KpiDefinition(
        "obsolete_inventory_share", "Inventario sin movimiento", "inventory", "inventory_items",
        "Proporción del valor del inventario sin movimiento por más días que el umbral configurado.",
        "Valor de artículos con días sin movimiento > umbral ÷ valor total × 100", "%", "por corte",
        ("on_hand_qty", "unit_cost", "last_movement_date"), "Costo y fecha del último movimiento.", _MISSING_ROWS,
        ("La fecha de referencia es el movimiento más reciente del conjunto de datos.", "Sin movimiento no implica obsolescencia confirmada."),
        "lower_is_better", _obsolete_share, "category", monthly=False,
    ),
    KpiDefinition(
        "fuel_efficiency_km_l", "Rendimiento de combustible", "logistics", "fuel_logs",
        "Kilómetros recorridos por litro, método tanque lleno a tanque lleno.",
        "Σ distancia entre cargas llenas ÷ Σ litros cargados en el intervalo", "km/l", "mensual",
        ("vehicle_code", "date", "odometer_km", "liters"), f"Al menos {MIN_FUEL_INTERVALS} intervalos válidos.",
        "La primera carga de cada vehículo solo sirve de referencia; intervalos con odómetro no creciente se excluyen.",
        ("Cada carga llena repone el combustible consumido desde la carga llena anterior.",),
        "higher_is_better", _fuel_efficiency, "vehicle_code",
    ),
    KpiDefinition(
        "fuel_cost_per_km", "Costo de combustible por kilómetro", "logistics", "fuel_logs",
        "Importe de combustible por kilómetro recorrido.", "Σ importe en intervalos válidos ÷ Σ distancia", "moneda/km", "mensual",
        ("vehicle_code", "date", "odometer_km", "liters", "total_cost"), f"Al menos {MIN_FUEL_INTERVALS} intervalos con importe.",
        "Intervalos sin importe se excluyen.", ("Solo combustible; no incluye mantenimiento, llantas ni depreciación.",),
        "lower_is_better", _cost_per_km, "vehicle_code",
    ),
    KpiDefinition(
        "fuel_cost_total", "Gasto en combustible", "logistics", "fuel_logs",
        "Suma de importes de cargas de combustible.", "Σ importe", "moneda", "mensual",
        ("total_cost",), "Al menos una carga con importe.", "Cargas sin importe no suman.", (),
        "neutral", _fuel_cost_total, "vehicle_code",
    ),
]

KPIS: dict[str, KpiDefinition] = {k.code: k for k in CATALOG}


def kpis_for_template(template_code: str) -> list[KpiDefinition]:
    return [k for k in CATALOG if k.template == template_code]
