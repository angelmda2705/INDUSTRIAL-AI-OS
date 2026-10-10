/** Spanish labels for codes returned by the API (UI only; the API keeps stable codes). */

export const AREA_LABELS: Record<string, string> = {
  production: "Producción",
  maintenance: "Mantenimiento",
  inventory: "Inventarios",
  logistics: "Logística",
  general: "General",
};

export const NATURE_LABELS: Record<string, string> = {
  confirmed_issue: "Problema confirmado en datos",
  statistical_anomaly: "Anomalía estadística",
  hypothesis: "Hipótesis a investigar",
};

export const NATURE_HELP: Record<string, string> = {
  confirmed_issue:
    "La condición se verificó con una regla determinista sobre los datos (por ejemplo, existencia menor al punto de reorden). No identifica la causa.",
  statistical_anomaly:
    "Un valor inusual según un método estadístico. Puede ser un problema real o un error de captura; requiere revisión antes de actuar.",
  hypothesis:
    "Una posible explicación que debe investigarse y confirmarse con evidencia antes de tomar decisiones.",
};

/** What a finding's amount means. Different kinds are never added together. */
export const IMPACT_KIND_LABELS: Record<string, string> = {
  estimated_excess_cost: "Sobrecosto estimado",
  recorded_cost: "Costo registrado asociado",
  capital_tied: "Inventario expuesto o inmovilizado",
};

export const IMPACT_KIND_HELP: Record<string, string> = {
  estimated_excess_cost: "Costo que probablemente pudo evitarse, estimado con la base de cálculo indicada. Solo es real si la anomalía no es un error de captura.",
  recorded_cost: "Costos ya registrados en los datos (por ejemplo, reparaciones). Muestran la magnitud del problema; no son un ahorro alcanzable completo.",
  capital_tied: "Valor de inventario a costo que está por encima del máximo o sin movimiento. No es pérdida ni ahorro: liberarlo depende de consumirlo o venderlo.",
};

export const PRIORITY_LABELS: Record<string, string> = { critical: "Crítica", high: "Alta", medium: "Media", low: "Baja" };

export const STATUS_LABELS: Record<string, string> = {
  open: "Abierto",
  in_review: "En revisión",
  action_planned: "Acción planificada",
  resolved: "Resuelto",
  dismissed: "Descartado",
};

/** Mirrors FindingStatus.TRANSITIONS in the backend (the backend enforces them). */
export const STATUS_TRANSITIONS: Record<string, string[]> = {
  open: ["in_review", "action_planned", "resolved", "dismissed"],
  in_review: ["open", "action_planned", "resolved", "dismissed"],
  action_planned: ["in_review", "resolved", "dismissed"],
  resolved: ["open"],
  dismissed: ["open"],
};

export const IMPORT_STATUS_LABELS: Record<string, string> = {
  parsed: "Cargado",
  validated: "Validado",
  committed: "Confirmado",
  reverted: "Revertido",
  failed: "Fallido",
};

export const TEMPLATE_LABELS: Record<string, string> = {
  production_records: "Registros de producción",
  maintenance_events: "Eventos de mantenimiento",
  inventory_items: "Existencias de inventario",
  fuel_logs: "Cargas de combustible",
  generic: "Tabla genérica",
};

export const CATEGORY_LABELS: Record<string, string> = {
  data_quality: "Calidad de datos",
  target_deviation: "Desviación vs objetivo",
  trend: "Tendencia",
  pareto: "Concentración (Pareto)",
  reliability: "Confiabilidad",
  root_cause: "Causa raíz",
  outlier: "Valor atípico",
  compliance: "Cumplimiento",
  stock_risk: "Riesgo de desabasto",
  excess: "Exceso de inventario",
  obsolescence: "Obsolescencia",
};

export const EVENT_LABELS: Record<string, string> = {
  detected: "Detectado por el análisis",
  status_changed: "Cambio de estado",
  owner_changed: "Cambio de responsable",
  due_date_changed: "Cambio de fecha límite",
  comment: "Comentario",
  condition_detected_again: "Condición detectada de nuevo",
  reopened_by_analysis: "Reabierto por el análisis",
  condition_not_detected: "Condición ya no detectada",
};

export const DIRECTION_LABELS: Record<string, string> = {
  higher_is_better: "Mayor es mejor",
  lower_is_better: "Menor es mejor",
  neutral: "Informativo",
};

export const REPORT_TYPE_LABELS: Record<string, string> = {
  diagnostic: "Diagnóstico operativo general",
  executive: "Informe ejecutivo",
  inventory: "Reporte de inventarios",
  maintenance: "Reporte de mantenimiento",
  logistics: "Reporte logístico",
  production: "Reporte de producción",
};

export function label(map: Record<string, string>, code: string | null | undefined): string {
  if (!code) return "—";
  return map[code] ?? code;
}
