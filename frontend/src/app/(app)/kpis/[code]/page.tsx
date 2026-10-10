"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { TrendChart } from "@/components/charts/trend-chart";
import { Badge, DemoBadge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, Stat } from "@/components/ui/card";
import { EmptyState, ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtCell, fmtDateTime, fmtKpi, fmtMonth } from "@/lib/format";
import { DIRECTION_LABELS } from "@/lib/labels";
import { useMe } from "@/lib/session";
import type { KpiDefinition, KpiTarget } from "@/lib/types";

type Item = { value: number | null; status: string; sample_size: number; inputs: Record<string, unknown>; message: string | null; evaluation: string | null };
type Detail = {
  definition: Omit<KpiDefinition, "target">;
  dataset: { id: number; name: string; is_demo: boolean };
  target: KpiTarget | null;
  analysis_run_id: number | null;
  total: Item | null;
  by_dimension: (Item & { dimension_value: string })[];
  monthly: (Item & { period_start: string; period_end: string })[];
  history: { analysis_run_id: number; computed_at: string; value: number | null; status: string; sample_size: number }[];
};

function KpiDetail() {
  const { code } = useParams<{ code: string }>();
  const dataset = useSearchParams().get("dataset");
  const { data: me } = useMe();
  const currency = String(me?.organization?.settings?.currency ?? "MXN");
  const q = useQuery({
    queryKey: ["kpi", code, dataset],
    queryFn: () => api<Detail>(`/kpis/${code}`, { query: { dataset_id: dataset ?? "" } }),
    enabled: !!dataset,
  });
  if (!dataset) return <Notice tone="warn">Selecciona un conjunto de datos desde el <Link className="underline" href="/kpis">catálogo</Link>.</Notice>;
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBanner error={q.error} />;
  const d = q.data;
  const k = d.definition;
  const fmt = (v: number | null) => fmtKpi(v, k.unit, currency);
  return (
    <div className="space-y-4">
      <div>
        <Link href="/kpis" className="text-sm text-muted hover:underline">← Indicadores</Link>
        <h1 className="mt-2 text-xl font-semibold">{k.name}</h1>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
          <Link className="underline" href={`/datasets/${d.dataset.id}`}>{d.dataset.name}</Link>
          {d.dataset.is_demo && <DemoBadge />}
          {d.analysis_run_id && <span>· análisis #{d.analysis_run_id}</span>}
          <Badge>{DIRECTION_LABELS[k.direction]}</Badge>
        </p>
      </div>
      {!d.total ? (
        <Card><EmptyState title="Sin cálculo" description="El conjunto aún no se ha analizado o este indicador no aplica a su plantilla." /></Card>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            <Stat label="Valor del periodo" value={d.total.status === "ok" ? fmt(d.total.value) : "Datos insuficientes"} hint={d.total.status === "ok" ? `Muestra: ${d.total.sample_size} registros` : d.total.message} />
            <Stat label="Objetivo" value={d.target ? fmt(d.target.target_value) : "—"} hint={d.target ? `Tolerancia ${fmt(d.target.tolerance)}` : "Definido por la organización en el catálogo"} />
            <Stat label="Evaluación" value={d.total.evaluation === "meets" ? "Cumple" : d.total.evaluation === "misses" ? "No cumple" : "—"} tone={d.total.evaluation === "misses" ? "bad" : "default"} />
          </div>
          <Card>
            <CardHeader title="Cálculo" description="Valores de entrada exactos usados en la fórmula (reproducibles)." />
            <CardBody className="space-y-2 text-sm">
              <div className="rounded-md bg-slate-50 px-3 py-2 font-mono text-xs">{k.formula}</div>
              <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[14rem_1fr]">
                {Object.entries(d.total.inputs).map(([key, v]) => <div key={key} className="contents"><dt className="text-muted">{key}</dt><dd className="tabular">{fmtCell(v)}</dd></div>)}
              </dl>
              <ul className="list-disc pl-5 text-xs text-muted">{k.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </CardBody>
          </Card>
          {d.monthly.length > 0 && (
            <Card>
              <CardHeader title="Serie mensual" />
              <CardBody>
                <TrendChart points={d.monthly.map((m) => ({ period: m.period_start, value: m.status === "ok" ? m.value : null }))}
                  unit={k.unit} target={d.target?.target_value} direction={k.direction} currency={currency} height={240} />
                <Table className="mt-4">
                  <thead><tr><Th>Mes</Th><Th className="text-right">Valor</Th><Th className="text-right">Muestra</Th><Th>Nota</Th></tr></thead>
                  <tbody className="divide-y divide-line">
                    {d.monthly.map((m) => (
                      <tr key={m.period_start}><Td>{fmtMonth(m.period_start)}</Td><Td className="tabular text-right">{m.status === "ok" ? fmt(m.value) : "—"}</Td><Td className="tabular text-right">{m.sample_size}</Td><Td className="text-xs text-muted">{m.message ?? ""}</Td></tr>
                    ))}
                  </tbody>
                </Table>
              </CardBody>
            </Card>
          )}
          {d.by_dimension.length > 0 && (
            <Card>
              <CardHeader title={`Desglose por ${k.dimension}`} />
              <Table>
                <thead><tr><Th>{k.dimension}</Th><Th className="text-right">Valor</Th><Th className="text-right">Muestra</Th><Th>Evaluación</Th></tr></thead>
                <tbody className="divide-y divide-line">
                  {[...d.by_dimension].sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity)).map((r) => (
                    <tr key={r.dimension_value}>
                      <Td>{r.dimension_value}</Td>
                      <Td className="tabular text-right">{r.status === "ok" ? fmt(r.value) : <span className="text-xs text-amber-700" title={r.message ?? ""}>Datos insuficientes</span>}</Td>
                      <Td className="tabular text-right">{r.sample_size}</Td>
                      <Td>{r.evaluation ? <Badge tone={r.evaluation === "meets" ? "green" : "red"}>{r.evaluation === "meets" ? "Cumple" : "No cumple"}</Badge> : "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          )}
          <Card>
            <CardHeader title="Historial de cálculos" description="Un valor por cada análisis ejecutado sobre este conjunto." />
            <Table>
              <thead><tr><Th>Análisis</Th><Th>Fecha</Th><Th className="text-right">Valor</Th><Th className="text-right">Muestra</Th></tr></thead>
              <tbody className="divide-y divide-line">
                {d.history.map((h) => (
                  <tr key={h.analysis_run_id}><Td>#{h.analysis_run_id}</Td><Td className="text-muted">{fmtDateTime(h.computed_at)}</Td><Td className="tabular text-right">{h.status === "ok" ? fmt(h.value) : "—"}</Td><Td className="tabular text-right">{h.sample_size}</Td></tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </>
      )}
    </div>
  );
}

export default function KpiDetailPage() {
  return <Suspense fallback={<Spinner />}><KpiDetail /></Suspense>;
}
