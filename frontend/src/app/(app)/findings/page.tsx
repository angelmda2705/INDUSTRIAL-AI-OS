"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DemoBadge, NatureBadge, PriorityBadge, StatusBadge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { EmptyState, ErrorBanner, Spinner } from "@/components/ui/feedback";
import { Checkbox, Input, Select } from "@/components/ui/field";
import { Pagination, Table, Td, Th } from "@/components/ui/table";
import { api, downloadUrl } from "@/lib/api";
import { fmtDate, fmtMoney } from "@/lib/format";
import { AREA_LABELS, IMPACT_KIND_HELP, IMPACT_KIND_LABELS, NATURE_LABELS, PRIORITY_LABELS, STATUS_LABELS, label } from "@/lib/labels";
import type { Finding, Page } from "@/lib/types";

const OPEN = ["open", "in_review", "action_planned"];

export default function FindingsPage() {
  const [statusFilter, setStatusFilter] = useState("pending");
  const [priority, setPriority] = useState("");
  const [area, setArea] = useState("");
  const [nature, setNature] = useState("");
  const [activeOnly, setActiveOnly] = useState(false);
  const [includeDemo, setIncludeDemo] = useState(true);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const status = statusFilter === "pending" ? OPEN : statusFilter ? [statusFilter] : undefined;
  const query = useQuery({
    queryKey: ["findings", statusFilter, priority, area, nature, activeOnly, includeDemo, q, page],
    queryFn: () =>
      api<Page<Finding>>("/findings", {
        query: { status, priority, area, nature, active_only: activeOnly, include_demo: includeDemo, q, page, page_size: 25 },
      }),
  });
  const reset = <T,>(setter: (v: T) => void) => (v: T) => { setter(v); setPage(1); };

  return (
    <>
      <PageHeader
        title="Hallazgos"
        description="Problemas detectados por reglas verificables. Cada uno indica su evidencia, el método usado y si es un hecho, una anomalía estadística o una hipótesis."
        actions={<ButtonLink variant="secondary" external href={downloadUrl("/findings/export", { include_demo: includeDemo })}><Download className="h-4 w-4" />Exportar Excel</ButtonLink>}
      />
      <Card className="mb-4 px-4 py-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="w-56 text-xs text-muted">Buscar
            <Input className="mt-1" placeholder="Código o texto" value={q} onChange={(e) => reset(setQ)(e.target.value)} />
          </label>
          <label className="w-44 text-xs text-muted">Estado
            <Select className="mt-1" value={statusFilter} onChange={(e) => reset(setStatusFilter)(e.target.value)}>
              <option value="pending">Pendientes</option>
              <option value="">Todos</option>
              {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </label>
          <label className="w-36 text-xs text-muted">Prioridad
            <Select className="mt-1" value={priority} onChange={(e) => reset(setPriority)(e.target.value)}>
              <option value="">Todas</option>
              {Object.entries(PRIORITY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </label>
          <label className="w-40 text-xs text-muted">Área
            <Select className="mt-1" value={area} onChange={(e) => reset(setArea)(e.target.value)}>
              <option value="">Todas</option>
              {Object.entries(AREA_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </label>
          <label className="w-56 text-xs text-muted">Naturaleza
            <Select className="mt-1" value={nature} onChange={(e) => reset(setNature)(e.target.value)}>
              <option value="">Todas</option>
              {Object.entries(NATURE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </label>
          <div className="flex flex-col gap-1 pb-1">
            <Checkbox label="Solo condición vigente" checked={activeOnly} onChange={(e) => reset(setActiveOnly)(e.target.checked)} />
            <Checkbox label="Incluir demostración" checked={includeDemo} onChange={(e) => reset(setIncludeDemo)(e.target.checked)} />
          </div>
        </div>
      </Card>
      <ErrorBanner error={query.error} />
      <Card>
        {query.isLoading ? <Spinner /> : !query.data?.items.length ? (
          <EmptyState title="No hay hallazgos con estos filtros" description="Los hallazgos se generan al analizar conjuntos de datos." />
        ) : (
          <>
            <Table>
              <thead><tr><Th>Código</Th><Th>Hallazgo</Th><Th>Prioridad</Th><Th>Naturaleza</Th><Th>Estado</Th><Th className="text-right">Monto (tipo)</Th><Th>Detectado</Th></tr></thead>
              <tbody className="divide-y divide-line">
                {query.data.items.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50">
                    <Td className="whitespace-nowrap font-mono text-xs text-muted">{f.code}</Td>
                    <Td>
                      <Link href={`/findings/${f.id}`} className="font-medium hover:underline">{f.title}</Link>
                      <div className="mt-0.5 flex flex-wrap gap-1.5 text-xs text-muted">
                        {label(AREA_LABELS, f.area)}
                        {f.is_demo && <DemoBadge />}
                        {!f.condition_active && <span>· ya no detectado en el último análisis</span>}
                      </div>
                    </Td>
                    <Td><PriorityBadge value={f.priority} /></Td>
                    <Td><NatureBadge value={f.nature} /></Td>
                    <Td><StatusBadge value={f.status} /></Td>
                    <Td className="tabular whitespace-nowrap text-right">
                      {f.impact_amount ? (
                        <span title={f.impact_kind ? IMPACT_KIND_HELP[f.impact_kind] : undefined}>
                          {fmtMoney(f.impact_amount, f.impact_currency ?? "MXN")}
                          <span className="block text-[11px] text-muted">{label(IMPACT_KIND_LABELS, f.impact_kind)}</span>
                        </span>
                      ) : "—"}
                    </Td>
                    <Td className="whitespace-nowrap text-muted">{fmtDate(f.first_detected_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} pageSize={25} total={query.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
