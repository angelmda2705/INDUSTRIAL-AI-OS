import { Table, Td, Th } from "@/components/ui/table";
import { fmtCell } from "@/lib/format";

const COLUMN_LABELS: Record<string, string> = {
  source_row: "Fila origen",
  _repair_h: "Reparación (h)",
  _total_cost: "Costo",
  _rop: "Punto de reorden",
  _abc: "ABC",
  _safety_stock: "Stock seguridad",
  _rop_basis: "Base ROP",
  _coverage_days: "Cobertura (días)",
  _suggested_order_qty: "Cantidad sugerida",
  _excess_qty: "Excedente",
  _excess_value: "Valor excedente",
  _days_without_movement: "Días sin movimiento",
  _value: "Valor",
  _interval_km: "Km intervalo",
  _interval_liters: "Litros intervalo",
  _kml: "km/l",
  _z: "Puntaje z robusto",
  _expected_liters: "Litros esperados",
  _excess_liters: "Litros en exceso",
};

const FIELD_LABELS: Record<string, string> = {
  sku: "SKU",
  description: "Descripción",
  warehouse: "Almacén",
  category: "Categoría",
  on_hand_qty: "Existencia",
  unit_cost: "Costo unitario",
  avg_daily_demand: "Demanda diaria",
  lead_time_days: "Lead time (días)",
  max_qty: "Máximo",
  last_movement_date: "Último movimiento",
  asset_code: "Equipo",
  event_start: "Inicio",
  event_end: "Fin",
  scheduled_date: "Fecha programada",
  cause: "Causa",
  work_order_ref: "Orden de trabajo",
  vehicle_code: "Vehículo",
  date: "Fecha",
  odometer_km: "Odómetro (km)",
  liters: "Litros",
  driver_code: "Conductor",
  route: "Ruta",
  work_center: "Centro de trabajo",
  downtime_min: "Tiempo muerto (min)",
};

// PostgreSQL JSONB does not preserve key order, so columns are ordered here:
// identifiers first, then the remaining fields, and the source row last.
const FIRST = ["sku", "asset_code", "vehicle_code", "work_center", "description", "date", "event_start", "warehouse"];

function orderColumns(cols: string[]): string[] {
  const first = FIRST.filter((c) => cols.includes(c));
  const rest = cols.filter((c) => !first.includes(c) && c !== "source_row").sort((a, b) => Number(a.startsWith("_")) - Number(b.startsWith("_")));
  return [...first, ...rest, ...(cols.includes("source_row") ? ["source_row"] : [])];
}

const colLabel = (k: string) => COLUMN_LABELS[k] ?? FIELD_LABELS[k] ?? k.replace(/^_/, "").replaceAll("_", " ");

/** Renders the evidence object stored with a finding: tables for row lists, key/value pairs otherwise. */
export function Evidence({ evidence }: { evidence: Record<string, unknown> }) {
  const scalars = Object.entries(evidence).filter(([, v]) => v === null || typeof v !== "object");
  const lists = Object.entries(evidence).filter(([, v]) => Array.isArray(v) && v.length && typeof v[0] === "object") as [string, Record<string, unknown>[]][];
  const objects = Object.entries(evidence).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v)) as [string, Record<string, unknown>][];
  return (
    <div className="space-y-4">
      {scalars.length > 0 && (
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[14rem_1fr]">
          {scalars.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted">{colLabel(k)}</dt>
              <dd className="tabular">{fmtCell(v)}</dd>
            </div>
          ))}
        </dl>
      )}
      {objects.map(([k, obj]) => (
        <div key={k}>
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{colLabel(k)}</div>
          <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[14rem_1fr]">
            {Object.entries(obj).map(([kk, vv]) => (
              <div key={kk} className="contents"><dt className="text-muted">{colLabel(kk)}</dt><dd className="tabular">{fmtCell(vv)}</dd></div>
            ))}
          </dl>
        </div>
      ))}
      {lists.map(([k, rows]) => {
        const cols = orderColumns(Object.keys(rows[0]));
        return (
          <div key={k}>
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{colLabel(k)} ({rows.length})</div>
            <Table className="max-h-80 rounded border border-line">
              <thead><tr>{cols.map((c) => <Th key={c}>{colLabel(c)}</Th>)}</tr></thead>
              <tbody className="divide-y divide-line">
                {rows.map((r, i) => (
                  <tr key={i}>{cols.map((c) => <Td key={c} className="whitespace-nowrap tabular">{fmtCell(r[c])}</Td>)}</tr>
                ))}
              </tbody>
            </Table>
          </div>
        );
      })}
    </div>
  );
}
