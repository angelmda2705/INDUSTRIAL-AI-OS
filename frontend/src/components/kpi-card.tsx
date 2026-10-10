import Link from "next/link";

import { Badge, DemoBadge } from "@/components/ui/badge";
import { fmtKpi } from "@/lib/format";
import type { KpiValue } from "@/lib/types";

export function KpiCard({ kpi, currency }: { kpi: KpiValue; currency: string }) {
  return (
    <Link
      href={`/kpis/${kpi.kpi_code}?dataset=${kpi.dataset_id}`}
      className="block rounded-lg border border-line bg-panel px-4 py-3 transition-colors hover:border-slate-300"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs font-medium text-muted">{kpi.name}</div>
        {kpi.is_demo && <DemoBadge />}
      </div>
      {kpi.status === "ok" ? (
        <div className="tabular mt-1 text-2xl font-semibold text-ink">{fmtKpi(kpi.value, kpi.unit, currency)}</div>
      ) : (
        <div className="mt-1 text-sm font-medium text-amber-700" title={kpi.message ?? undefined}>
          Datos insuficientes
        </div>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
        <span className="truncate">{kpi.dataset_name}</span>
        {kpi.target !== null && (
          <Badge tone={kpi.evaluation === "meets" ? "green" : kpi.evaluation === "misses" ? "red" : "gray"}>
            Objetivo {fmtKpi(kpi.target, kpi.unit, currency)}
          </Badge>
        )}
      </div>
      {kpi.status !== "ok" && kpi.message && <p className="mt-1 line-clamp-2 text-xs text-muted">{kpi.message}</p>}
    </Link>
  );
}
