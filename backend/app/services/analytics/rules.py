"""Deterministic finding rules.

Every rule documents the method it applies, the evidence it attaches and the
*nature* of the finding:

* ``confirmed_issue`` — a condition verified directly on the stored data
  (e.g. existence ≤ reorder point). It says nothing about the cause.
* ``statistical_anomaly`` — an unusual value according to a statistical
  method; it may be a data error or a real problem and needs review.
* ``hypothesis`` — a plausible explanation that must be investigated before
  acting (e.g. "possible obsolete stock").
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from statistics import median
from typing import Any

import pandas as pd

from app.models import FindingNature
from app.services.analytics.kpis import KPIS, KpiResult, kpis_for_template
from app.services.analytics.stats import mann_kendall, robust_z_scores, round_or_none
from app.services.imports.templates import ImportTemplate

MAX_EVIDENCE_ROWS = 50
MISSING_THRESHOLD_PCT = 20.0
TREND_MIN_POINTS = 6


@dataclass
class FindingDraft:
    rule_code: str
    key: str
    area: str
    category: str
    nature: str
    title: str
    description: str
    method: str
    priority: str
    recommendation: str
    evidence: dict = field(default_factory=dict)
    impact_amount: float | None = None
    impact_basis: str | None = None
    confidence: str | None = None
    confidence_basis: str | None = None

    def fingerprint(self, dataset_id: int) -> str:
        return hashlib.sha256(f"{dataset_id}|{self.rule_code}|{self.key}".encode()).hexdigest()


@dataclass
class KpiOutcome:
    total: KpiResult
    by_dimension: dict[str, KpiResult]
    monthly: list[tuple[Any, KpiResult]]


@dataclass
class RuleContext:
    dataset_id: int
    dataset_name: str
    template: ImportTemplate
    df: pd.DataFrame
    kpis: dict[str, KpiOutcome]
    targets: dict[str, Any]  # kpi_code -> object with target_value / tolerance
    settings: dict
    currency: str
    profile: dict
    duplicate_records: int


def _rows(df: pd.DataFrame, cols: list[str], limit: int = MAX_EVIDENCE_ROWS) -> list[dict]:
    out = []
    for _, row in df.head(limit).iterrows():
        item = {"source_row": int(row["_source_row"])} if "_source_row" in row else {}
        for c in cols:
            v = row.get(c)
            if isinstance(v, pd.Timestamp):
                v = v.isoformat()
            elif isinstance(v, float):
                v = round_or_none(v)
            elif v is not None and pd.isna(v):
                v = None
            item[c] = v
        out.append(item)
    return out


def _fmt(v: float | None, unit: str = "") -> str:
    if v is None:
        return "—"
    text = f"{v:,.2f}"
    return f"{text} {unit}".strip()


# --- Common rules -------------------------------------------------------------------


def rule_missing_values(ctx: RuleContext) -> list[FindingDraft]:
    drafts = []
    if ctx.template.generic:
        return drafts
    required = {f.name for f in ctx.template.fields if f.required}
    for info in ctx.profile.get("fields", []):
        pct = info.get("missing_pct") or 0
        if info["field"] in required or pct < MISSING_THRESHOLD_PCT:
            continue
        affected = [k.name for k in kpis_for_template(ctx.template.code) if info["field"] in k.required_fields]
        drafts.append(FindingDraft(
            rule_code="DQ-MISSING", key=info["field"], area=ctx.template.area, category="data_quality",
            nature=FindingNature.CONFIRMED_ISSUE,
            title=f"Datos faltantes en «{info['label']}» ({pct:.0f} %)",
            description=(
                f"El {pct:.1f} % de los registros de «{ctx.dataset_name}» no tiene valor en «{info['label']}». "
                + (f"Esto limita: {', '.join(affected)}." if affected else "")
            ),
            method=f"Conteo de celdas vacías por campo; umbral de reporte {MISSING_THRESHOLD_PCT:.0f} %.",
            priority="medium" if pct >= 50 and affected else "low",
            recommendation="Completar el dato en el sistema de origen o en la plantilla de captura y volver a importar.",
            evidence={"field": info["field"], "missing": info["missing"], "row_count": ctx.profile["row_count"],
                      "missing_pct": pct, "affected_kpis": affected},
        ))
    return drafts


def rule_duplicates(ctx: RuleContext) -> list[FindingDraft]:
    if ctx.duplicate_records <= 0:
        return []
    return [FindingDraft(
        rule_code="DQ-DUPLICATES", key="dataset", area=ctx.template.area, category="data_quality",
        nature=FindingNature.CONFIRMED_ISSUE,
        title=f"{ctx.duplicate_records} registros duplicados en el conjunto de datos",
        description="Hay registros con la misma clave de identificación. Pueden inflar sumas y conteos de los indicadores.",
        method="Comparación de la huella (hash) de los campos clave de cada registro.",
        priority="medium",
        recommendation="Revisar las importaciones que se confirmaron incluyendo duplicados y revertir la que corresponda.",
        evidence={"duplicate_records": ctx.duplicate_records},
    )]


def _gap_priority(rel_gap: float) -> str:
    if rel_gap >= 0.2:
        return "high"
    if rel_gap >= 0.1:
        return "medium"
    return "low"


def rule_kpi_targets(ctx: RuleContext) -> list[FindingDraft]:
    drafts = []
    for code, outcome in ctx.kpis.items():
        kpi = KPIS[code]
        target = ctx.targets.get(code)
        if target is None or kpi.direction == "neutral":
            continue
        checks: list[tuple[str, str | None, KpiResult]] = [("total", None, outcome.total)]
        checks += [(f"dim:{v}", v, r) for v, r in outcome.by_dimension.items()]
        for key, dim_value, result in checks:
            if result.status != "ok" or result.value is None:
                continue
            value, goal, tol = result.value, float(target.target_value), float(target.tolerance or 0)
            worse = value < goal - tol if kpi.direction == "higher_is_better" else value > goal + tol
            if not worse:
                continue
            rel_gap = abs(value - goal) / abs(goal) if goal else 1.0
            scope = f" en {kpi.dimension and _dim_label(ctx.template, kpi.dimension)} «{dim_value}»" if dim_value else ""
            drafts.append(FindingDraft(
                rule_code=f"KPI-TARGET:{code}", key=key, area=kpi.area, category="target_deviation",
                nature=FindingNature.CONFIRMED_ISSUE,
                title=f"{kpi.name}{scope}: {_fmt(value, kpi.unit)} vs objetivo {_fmt(goal, kpi.unit)}",
                description=(
                    f"El indicador «{kpi.name}»{scope} está fuera del objetivo definido por la organización "
                    f"(objetivo {_fmt(goal, kpi.unit)}, tolerancia {_fmt(tol, kpi.unit)}). "
                    "La desviación es un hecho medido; sus causas requieren análisis."
                ),
                method=f"Comparación del valor calculado ({kpi.formula}) contra el objetivo configurado.",
                priority=_gap_priority(rel_gap),
                recommendation="Analizar los registros que más contribuyen a la desviación y definir acciones con responsable y fecha.",
                evidence={"kpi_code": code, "value": value, "target": goal, "tolerance": tol, "unit": kpi.unit,
                          "dimension": kpi.dimension if dim_value else None, "dimension_value": dim_value,
                          "sample_size": result.sample_size, "inputs": result.inputs},
            ))
    return drafts


def rule_kpi_trends(ctx: RuleContext) -> list[FindingDraft]:
    drafts = []
    for code, outcome in ctx.kpis.items():
        kpi = KPIS[code]
        if kpi.direction == "neutral":
            continue
        series = [(m, r.value) for m, r in outcome.monthly if r.status == "ok" and r.value is not None]
        if len(series) < TREND_MIN_POINTS:
            continue
        trend = mann_kendall([v for _, v in series])
        if trend is None or trend.direction == "none":
            continue
        worsening = (trend.direction == "decreasing") == (kpi.direction == "higher_is_better")
        if not worsening:
            continue
        confidence = "alta" if trend.p_value < 0.01 and len(series) >= 8 else "media"
        drafts.append(FindingDraft(
            rule_code=f"KPI-TREND:{code}", key="total", area=kpi.area, category="trend",
            nature=FindingNature.STATISTICAL_ANOMALY,
            title=f"Tendencia desfavorable en {kpi.name}",
            description=(
                f"Los valores mensuales de «{kpi.name}» muestran una tendencia "
                f"{'descendente' if trend.direction == 'decreasing' else 'ascendente'} estadísticamente significativa "
                f"({len(series)} meses; pendiente de Sen {trend.sen_slope:+.3f} {kpi.unit}/mes). "
                "Una tendencia no identifica su causa."
            ),
            method="Prueba de Mann-Kendall (aproximación normal, corrección por empates, α = 0.05) y pendiente de Sen.",
            priority="medium",
            recommendation="Revisar qué cambió en el periodo (producto, personal, equipos, proveedores) y confirmar con los responsables del área.",
            evidence={"kpi_code": code, "series": [{"month": str(m), "value": v} for m, v in series],
                      "mann_kendall": {"s": trend.s, "z": round(trend.z, 4), "p_value": round(trend.p_value, 5)},
                      "sen_slope": round(trend.sen_slope, 5)},
            confidence=confidence,
            confidence_basis=f"p = {trend.p_value:.4f} con {len(series)} puntos (alta: p < 0.01 y ≥ 8 meses).",
        ))
    return drafts


def _dim_label(template: ImportTemplate, field_name: str) -> str:
    try:
        return template.field(field_name).label.lower()
    except KeyError:
        return field_name


# --- Production -------------------------------------------------------------------------


def rule_downtime_concentration(ctx: RuleContext) -> list[FindingDraft]:
    df = ctx.df[ctx.df["downtime_min"].notna()]
    if df.empty:
        return []
    by_wc = df.groupby("work_center")["downtime_min"].sum().sort_values(ascending=False)
    total = float(by_wc.sum())
    if len(by_wc) < 3 or total <= 0:
        return []
    top_wc, top_val = by_wc.index[0], float(by_wc.iloc[0])
    share = top_val / total
    if share < 0.5:
        return []
    return [FindingDraft(
        rule_code="PRD-DOWNTIME-CONCENTRATION", key=str(top_wc), area="production", category="pareto",
        nature=FindingNature.CONFIRMED_ISSUE,
        title=f"«{top_wc}» concentra el {share * 100:.0f} % del tiempo muerto",
        description=f"De {total:,.0f} minutos de tiempo muerto registrados, {top_val:,.0f} corresponden a «{top_wc}».",
        method="Análisis de Pareto del tiempo muerto por centro de trabajo; se reporta si un centro concentra ≥ 50 % con al menos 3 centros.",
        priority="high" if share >= 0.7 else "medium",
        recommendation="Priorizar el análisis de causas de paro en ese centro (registro de motivos, mantenimiento, abastecimiento).",
        evidence={"downtime_by_work_center": [{"work_center": str(k), "downtime_min": round(float(v), 2)} for k, v in by_wc.items()],
                  "total_downtime_min": round(total, 2)},
    )]


# --- Maintenance ---------------------------------------------------------------------------


def rule_recurrent_failures(ctx: RuleContext) -> list[FindingDraft]:
    failures = ctx.df[ctx.df["_is_failure"]]
    drafts = []
    for asset, group in failures.groupby("asset_code"):
        n = len(group)
        if n < 3:
            continue
        group = group.sort_values("event_start")
        downtime = float(group["_repair_h"].sum(skipna=True))
        drafts.append(FindingDraft(
            rule_code="MNT-RECURRENT-FAILURES", key=str(asset), area="maintenance", category="reliability",
            nature=FindingNature.CONFIRMED_ISSUE,
            title=f"Equipo «{asset}» con {n} fallas registradas",
            description=(
                f"Entre {group['event_start'].min():%d/%m/%Y} y {group['event_start'].max():%d/%m/%Y} el equipo registró {n} fallas "
                f"con {downtime:,.1f} h fuera de servicio."
            ),
            method="Conteo de eventos tipo falla por equipo; se reporta a partir de 3.",
            priority="high" if n >= 5 else "medium",
            recommendation="Realizar análisis de causa raíz (5 porqués / Ishikawa) y revisar el plan de mantenimiento preventivo del equipo.",
            evidence={"failures": _rows(group, ["event_start", "event_end", "cause", "_repair_h", "_total_cost"]),
                      "total_repair_h": round(downtime, 2)},
            impact_amount=round_or_none(float(group["_total_cost"].sum(skipna=True)), 2) if group["_total_cost"].notna().any() else None,
            impact_basis="Costo registrado de las fallas del equipo (refacciones + mano de obra + otros). No incluye producción perdida." if group["_total_cost"].notna().any() else None,
        ))
    return drafts


def rule_repeated_cause(ctx: RuleContext) -> list[FindingDraft]:
    failures = ctx.df[ctx.df["_is_failure"] & ctx.df["cause"].notna()]
    drafts = []
    for (asset, cause), group in failures.groupby(["asset_code", "cause"]):
        if len(group) < 2:
            continue
        drafts.append(FindingDraft(
            rule_code="MNT-REPEATED-CAUSE", key=f"{asset}|{str(cause).lower()}", area="maintenance", category="root_cause",
            nature=FindingNature.HYPOTHESIS,
            title=f"Posible causa recurrente en «{asset}»: {cause}",
            description=(
                f"La causa «{cause}» se registró {len(group)} veces en el mismo equipo. Puede indicar que la reparación "
                "no eliminó la causa raíz; también puede deberse a una clasificación genérica de la causa."
            ),
            method="Agrupación de fallas por equipo y causa registrada; se reporta a partir de 2 repeticiones.",
            priority="medium",
            recommendation="Verificar con el técnico responsable si la causa registrada es la causa raíz y documentar la investigación.",
            evidence={"events": _rows(group.sort_values("event_start"), ["event_start", "event_end", "work_order_ref"])},
        ))
    return drafts


def rule_long_repairs(ctx: RuleContext) -> list[FindingDraft]:
    repairs = ctx.df[ctx.df["_is_failure"] & ctx.df["_repair_h"].notna()]
    if len(repairs) < 8:
        return []
    threshold = float(ctx.settings.get("anomaly_robust_z_threshold", 3.5))
    scores = robust_z_scores(repairs["_repair_h"].tolist())
    if scores is None:
        return []
    repairs = repairs.assign(_z=scores)
    outliers = repairs[repairs["_z"] >= threshold].sort_values("_z", ascending=False)
    if outliers.empty:
        return []
    med = median(repairs["_repair_h"].tolist())
    return [FindingDraft(
        rule_code="MNT-LONG-REPAIRS", key="dataset", area="maintenance", category="outlier",
        nature=FindingNature.STATISTICAL_ANOMALY,
        title=f"{len(outliers)} reparaciones con duración atípica",
        description=f"Su duración es muy superior a la mediana de {med:,.1f} h. Pueden reflejar espera de refacciones, falta de personal o errores de captura.",
        method=f"Puntaje z robusto (0.6745·(x − mediana)/MAD) ≥ {threshold} sobre {len(repairs)} reparaciones.",
        priority="medium",
        recommendation="Revisar cada orden: confirmar fechas y documentar la causa de la demora.",
        evidence={"median_repair_h": round(med, 2),
                  "repairs": _rows(outliers, ["asset_code", "event_start", "event_end", "_repair_h", "_z", "work_order_ref"])},
        confidence="media" if len(repairs) >= 20 else "baja",
        confidence_basis=f"Basado en {len(repairs)} reparaciones; el método no distingue errores de captura de demoras reales.",
    )]


def rule_preventive_late(ctx: RuleContext) -> list[FindingDraft]:
    df = ctx.df[ctx.df["_preventive_on_time"].notna()]
    late = df[~df["_preventive_on_time"].astype(bool)]
    if late.empty:
        return []
    return [FindingDraft(
        rule_code="MNT-PREVENTIVE-LATE", key="dataset", area="maintenance", category="compliance",
        nature=FindingNature.CONFIRMED_ISSUE,
        title=f"{len(late)} de {len(df)} preventivos se ejecutaron después de su fecha programada",
        description="Ejecutar el preventivo tarde aumenta la exposición a fallas.",
        method=f"Comparación de inicio vs fecha programada + {ctx.settings.get('preventive_tolerance_days', 0)} días de tolerancia.",
        priority="high" if len(late) / len(df) >= 0.3 else "medium",
        recommendation="Revisar la capacidad del equipo de mantenimiento y la disponibilidad de los equipos para programar los preventivos.",
        evidence={"late_events": _rows(late, ["asset_code", "scheduled_date", "event_start", "work_order_ref"])},
    )]


def rule_maintenance_data(ctx: RuleContext) -> list[FindingDraft]:
    drafts = []
    no_end = ctx.df[ctx.df["_is_failure"] & ctx.df["event_end"].isna()]
    if not no_end.empty:
        drafts.append(FindingDraft(
            rule_code="MNT-MISSING-END", key="dataset", area="maintenance", category="data_quality",
            nature=FindingNature.CONFIRMED_ISSUE,
            title=f"{len(no_end)} fallas sin fecha de fin",
            description="Sin fecha de fin no se puede calcular el tiempo de reparación ni el tiempo entre fallas siguiente. Pueden ser reparaciones abiertas.",
            method="Fallas con fin vacío.", priority="low",
            recommendation="Cerrar las órdenes concluidas registrando la fecha en que el equipo quedó disponible.",
            evidence={"events": _rows(no_end, ["asset_code", "event_start", "work_order_ref"])},
        ))
    overlap = ctx.df[ctx.df["_interval_issue"] == "overlap"]
    if not overlap.empty:
        drafts.append(FindingDraft(
            rule_code="MNT-OVERLAP", key="dataset", area="maintenance", category="data_quality",
            nature=FindingNature.CONFIRMED_ISSUE,
            title=f"{len(overlap)} fallas inician antes de que terminara la anterior del mismo equipo",
            description="Fechas traslapadas indican errores de captura o eventos duplicados; se excluyen del MTBF.",
            method="Inicio de la falla < fin de la falla anterior del mismo equipo.", priority="low",
            recommendation="Corregir las fechas en el sistema de origen.",
            evidence={"events": _rows(overlap, ["asset_code", "event_start", "event_end"])},
        ))
    return drafts


# --- Inventory -----------------------------------------------------------------------------


def rule_inventory(ctx: RuleContext) -> list[FindingDraft]:
    df, cur = ctx.df, ctx.currency
    drafts: list[FindingDraft] = []
    item_cols = ["sku", "description", "warehouse", "on_hand_qty", "avg_daily_demand", "lead_time_days", "_rop", "_abc"]

    negative = df[df["_negative"]]
    if not negative.empty:
        drafts.append(FindingDraft(
            rule_code="INV-NEGATIVE", key="dataset", area="inventory", category="data_quality",
            nature=FindingNature.CONFIRMED_ISSUE, title=f"{len(negative)} artículos con existencia negativa",
            description="Una existencia negativa es físicamente imposible: indica salidas registradas sin entrada o errores de captura.",
            method="Existencia < 0.", priority="high",
            recommendation="Realizar conteo físico de los artículos y corregir los movimientos que originaron el saldo negativo.",
            evidence={"items": _rows(negative, ["sku", "description", "warehouse", "on_hand_qty"])},
        ))

    stockout = df[df["_stockout"]]
    if not stockout.empty:
        a_items = int((stockout["_abc"] == "A").sum())
        drafts.append(FindingDraft(
            rule_code="INV-STOCKOUT", key="dataset", area="inventory", category="stock_risk",
            nature=FindingNature.CONFIRMED_ISSUE, title=f"{len(stockout)} artículos con demanda están sin existencia",
            description=f"Artículos con demanda diaria registrada y existencia ≤ 0 ({a_items} clase A).",
            method="Demanda diaria > 0 y existencia ≤ 0.", priority="critical" if a_items else "high",
            recommendation="Confirmar existencias físicas y gestionar reposición urgente de los artículos críticos.",
            evidence={"items": _rows(stockout.sort_values("_annual_value", ascending=False), item_cols)},
        ))

    below = df[df["_below_rop"] & ~df["_stockout"]]
    if not below.empty:
        a_items = int((below["_abc"] == "A").sum())
        drafts.append(FindingDraft(
            rule_code="INV-BELOW-ROP", key="dataset", area="inventory", category="stock_risk",
            nature=FindingNature.CONFIRMED_ISSUE, title=f"{len(below)} artículos en o bajo su punto de reorden",
            description=(
                f"La existencia no cubre la demanda esperada durante el tiempo de reposición más el stock de seguridad "
                f"({a_items} clase A). Se adjunta una cantidad sugerida de pedido como propuesta; no se generó ninguna compra."
            ),
            method="Existencia ≤ ROP, con ROP = d·L + z·σ·√L (ver catálogo de indicadores).",
            priority="high" if a_items else "medium",
            recommendation="Revisar la propuesta de reposición y generar la solicitud de compra con la aprobación correspondiente.",
            evidence={"items": _rows(below.sort_values("_annual_value", ascending=False),
                                     item_cols + ["_safety_stock", "_rop_basis", "_coverage_days", "_suggested_order_qty"]),
                      "suggested_qty_rule": "Máximo − existencia si hay máximo; si no, ROP + d·L − existencia."},
        ))

    excess = df[df["_excess_qty"].notna()]
    if not excess.empty:
        value = float(excess["_excess_value"].sum(skipna=True))
        drafts.append(FindingDraft(
            rule_code="INV-EXCESS", key="dataset", area="inventory", category="excess",
            nature=FindingNature.CONFIRMED_ISSUE, title=f"{len(excess)} artículos por encima de su máximo",
            description="Existencias superiores al máximo definido inmovilizan capital y espacio.",
            method="Existencia > máximo configurado.", priority="medium" if value > 0 else "low",
            recommendation="Revisar compras pendientes de esos artículos y ajustar parámetros de máximo o política de compra.",
            evidence={"items": _rows(excess.sort_values("_excess_value", ascending=False),
                                     ["sku", "description", "on_hand_qty", "max_qty", "_excess_qty", "_excess_value"])},
            impact_amount=round_or_none(value, 2) if value > 0 else None,
            impact_basis=f"Valor del excedente sobre el máximo (capital inmovilizado, {cur}). No es un ahorro: liberar ese capital depende de consumir o vender el inventario." if value > 0 else None,
        ))

    stale = df[df["_obsolete_candidate"]]
    if not stale.empty:
        value = float(stale["_value"].sum(skipna=True))
        days = ctx.settings.get("inventory_obsolete_days", 180)
        drafts.append(FindingDraft(
            rule_code="INV-NO-MOVEMENT", key="dataset", area="inventory", category="obsolescence",
            nature=FindingNature.HYPOTHESIS, title=f"{len(stale)} artículos sin movimiento por más de {days} días",
            description=(
                "Pueden ser inventario obsoleto o de lento movimiento. También pueden ser refacciones de seguridad que "
                "deben conservarse; requiere revisión antes de cualquier decisión."
            ),
            method=f"Días desde el último movimiento > {days}, con referencia al movimiento más reciente del conjunto ({df.attrs.get('obsolescence_reference_date')}).",
            priority="medium" if value > 0 else "low",
            recommendation="Clasificar cada artículo (crítico, lento movimiento, obsoleto) con el área usuaria y definir su disposición.",
            evidence={"items": _rows(stale.sort_values("_value", ascending=False),
                                     ["sku", "description", "on_hand_qty", "last_movement_date", "_days_without_movement", "_value"])},
            impact_amount=round_or_none(value, 2) if value > 0 else None,
            impact_basis=f"Valor a costo de los artículos sin movimiento ({cur}). Es valor expuesto, no pérdida ni ahorro." if value > 0 else None,
        ))

    active = df[df["avg_daily_demand"] > 0]
    no_params = active[active["lead_time_days"].isna()]
    if len(df) and (df["avg_daily_demand"].isna().all() or df["lead_time_days"].isna().all()):
        drafts.append(FindingDraft(
            rule_code="INV-MISSING-PARAMS", key="columns", area="inventory", category="data_quality",
            nature=FindingNature.CONFIRMED_ISSUE, title="No es posible calcular puntos de reorden",
            description="El conjunto no contiene demanda diaria y/o tiempo de reposición, necesarios para evaluar riesgo de desabasto.",
            method="Verificación de columnas requeridas por el cálculo de ROP.", priority="medium",
            recommendation="Agregar demanda diaria promedio (y su desviación) y tiempo de reposición por artículo a la plantilla.",
            evidence={"missing_demand": int(df["avg_daily_demand"].isna().sum()), "missing_lead_time": int(df["lead_time_days"].isna().sum())},
        ))
    elif not no_params.empty:
        drafts.append(FindingDraft(
            rule_code="INV-MISSING-PARAMS", key="items", area="inventory", category="data_quality",
            nature=FindingNature.CONFIRMED_ISSUE, title=f"{len(no_params)} artículos activos sin tiempo de reposición",
            description="Sin tiempo de reposición no se puede evaluar su punto de reorden.",
            method="Artículos con demanda > 0 y tiempo de reposición vacío.", priority="low",
            recommendation="Registrar el tiempo de reposición acordado con el proveedor.",
            evidence={"items": _rows(no_params, ["sku", "description", "avg_daily_demand"])},
        ))
    return drafts


# --- Fleet ------------------------------------------------------------------------------------


def rule_fuel_anomalies(ctx: RuleContext) -> list[FindingDraft]:
    df = ctx.df
    threshold = float(ctx.settings.get("anomaly_robust_z_threshold", 3.5))
    drafts = []
    for vehicle, group in df[df["_kml"].notna()].groupby("vehicle_code"):
        n = len(group)
        if n < 6:
            continue
        scores = robust_z_scores(group["_kml"].tolist())
        if scores is None:
            continue
        group = group.assign(_z=scores)
        low = group[group["_z"] <= -threshold].sort_values("_z")
        if low.empty:
            continue
        baseline = median(group["_kml"].tolist())
        expected_l = low["_interval_km"] / baseline
        excess_l = (low["_interval_liters"] - expected_l).clip(lower=0)
        cpl = low["_interval_cost"] / low["_interval_liters"]
        excess_cost = float((excess_l * cpl).sum(skipna=True)) if cpl.notna().any() else None
        low = low.assign(_expected_liters=expected_l, _excess_liters=excess_l)
        conf = "alta" if n >= 12 and float(low["_z"].min()) <= -5 else ("media" if n >= 8 else "baja")
        drafts.append(FindingDraft(
            rule_code="FLT-FUEL-ANOMALY", key=str(vehicle), area="logistics", category="outlier",
            nature=FindingNature.STATISTICAL_ANOMALY,
            title=f"Consumo de combustible atípico en «{vehicle}» ({len(low)} cargas)",
            description=(
                f"En {len(low)} intervalos el rendimiento fue muy inferior a la mediana del propio vehículo "
                f"({baseline:,.2f} km/l). Posibles explicaciones a verificar: error de captura de odómetro o litros, carga parcial "
                "registrada como llena, ruta o carga distinta, falla mecánica o uso no autorizado. La anomalía no establece la causa."
            ),
            method=(f"Rendimiento por intervalo tanque lleno a tanque lleno; puntaje z robusto ≤ −{threshold} respecto de "
                    f"{n} intervalos del mismo vehículo."),
            priority="high" if excess_cost and excess_cost > 0 and len(low) >= 3 else "medium",
            recommendation="Validar los registros de carga; si son correctos, programar revisión mecánica y revisar la ruta asignada.",
            evidence={"vehicle_median_km_l": round(baseline, 3), "intervals_analyzed": n,
                      "anomalous_loads": _rows(low, ["date", "odometer_km", "_interval_km", "_interval_liters", "_kml", "_z",
                                                     "_expected_liters", "_excess_liters", "driver_code", "route"])},
            impact_amount=round_or_none(excess_cost, 2) if excess_cost else None,
            impact_basis=(f"Σ (litros cargados − distancia ÷ mediana km/l del vehículo) × precio por litro de cada carga ({ctx.currency}). "
                          "Estimación del sobreconsumo; solo es real si la anomalía no es un error de captura.") if excess_cost else None,
            confidence=conf,
            confidence_basis=f"{n} intervalos del vehículo; puntaje z mínimo {float(low['_z'].min()):.1f}. Heurística, no probabilidad.",
        ))
    return drafts


def rule_odometer(ctx: RuleContext) -> list[FindingDraft]:
    bad = ctx.df[ctx.df["_odometer_issue"]]
    if bad.empty:
        return []
    return [FindingDraft(
        rule_code="FLT-ODOMETER", key="dataset", area="logistics", category="data_quality",
        nature=FindingNature.CONFIRMED_ISSUE, title=f"{len(bad)} cargas con odómetro no creciente",
        description="El odómetro es igual o menor al de la carga llena anterior del mismo vehículo; el intervalo se excluyó del rendimiento.",
        method="Odómetro(carga) ≤ odómetro(carga llena previa) por vehículo.", priority="low",
        recommendation="Corregir la captura del odómetro o la fecha de la carga.",
        evidence={"loads": _rows(bad, ["vehicle_code", "date", "odometer_km", "liters"])},
    )]


RULES_BY_TEMPLATE = {
    "production_records": [rule_downtime_concentration],
    "maintenance_events": [rule_recurrent_failures, rule_repeated_cause, rule_long_repairs, rule_preventive_late, rule_maintenance_data],
    "inventory_items": [rule_inventory],
    "fuel_logs": [rule_fuel_anomalies, rule_odometer],
    "generic": [],
}
COMMON_RULES = [rule_missing_values, rule_duplicates, rule_kpi_targets, rule_kpi_trends]


def run_rules(ctx: RuleContext) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    for rule in COMMON_RULES + RULES_BY_TEMPLATE.get(ctx.template.code, []):
        drafts.extend(rule(ctx))
    return drafts
