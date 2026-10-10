"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { TrendChart } from "@/components/charts/trend-chart";
import { KpiCard } from "@/components/kpi-card";
import { DemoBadge, ImportStatusBadge, NatureBadge, PriorityBadge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardBody, CardHeader, PageHeader, Stat } from "@/components/ui/card";
import { EmptyState, ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Checkbox, Select } from "@/components/ui/field";
import { api } from "@/lib/api";
import { fmtDateTime, fmtMoney } from "@/lib/format";
import { AREA_LABELS, IMPACT_KIND_HELP, IMPACT_KIND_LABELS, NATURE_LABELS, label } from "@/lib/labels";
import { useCan } from "@/lib/session";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const can = useCan();
  const qc = useQueryClient();
  const [area, setArea] = useState("");
  const [datasetId, setDatasetId] = useState("");
  const [includeDemo, setIncludeDemo] = useState(true);
  const query = useQuery({
    queryKey: ["dashboard", area, datasetId, includeDemo],
    queryFn: () => api<Dashboard>("/dashboard", { query: { area, dataset_id: datasetId, include_demo: includeDemo } }),
  });
  const loadDemo = useMutation({ mutationFn: () => api("/demo", { method: "POST" }), onSuccess: () => qc.invalidateQueries() });
  const removeDemo = useMutation({ mutationFn: () => api("/demo", { method: "DELETE" }), onSuccess: () => qc.invalidateQueries() });
  const reanalyze = useMutation({
    mutationFn: (id: number) => api(`/datasets/${id}/analyze`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const d = query.data;
  const header = (
    <PageHeader
      title="Panel ejecutivo"
      description="Estado de las operaciones calculado exclusivamente con los datos importados por tu organización."
      actions={can("data.import") && <ButtonLink href="/imports/new"><Upload className="h-4 w-4" />Importar datos</ButtonLink>}
    />
  );

  if (query.isLoading) return (<>{header}<Spinner /></>);
  if (query.error || !d) return (<>{header}<ErrorBanner error={query.error} /></>);

  if (!d.has_data) {
    return (
      <>
        {header}
        <ErrorBanner error={loadDemo.error} />
        <Card>
          <EmptyState
            title="Aún no hay datos para analizar"
            description={
              <>
                Importa un archivo de Excel o CSV de producción, mantenimiento, inventario o combustible para calcular
                indicadores y detectar problemas. Si solo quieres conocer la plataforma, carga los datos de demostración:
                son sintéticos, se marcan como <strong>DEMO</strong> en todas las pantallas y puedes eliminarlos en cualquier momento.
              </>
            }
            actions={
              <>
                {can("data.import") && <ButtonLink href="/imports/new">Importar archivo</ButtonLink>}
                {can("demo.manage") && (
                  <Button variant="secondary" loading={loadDemo.isPending} onClick={() => loadDemo.mutate()}>
                    Cargar datos de demostración
                  </Button>
                )}
              </>
            }
          />
        </Card>
      </>
    );
  }

  const stale = d.datasets.filter((x) => x.analysis_stale);
  const high = (d.findings.by_priority.critical ?? 0) + (d.findings.by_priority.high ?? 0);
  const excess = d.impact.open_by_kind.estimated_excess_cost;
  const kpiByCode = Object.fromEntries(d.kpis.map((k) => [`${k.kpi_code}:${k.dataset_id}`, k]));

  return (
    <>
      {header}
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="w-44 text-xs text-muted">
          Área
          <Select value={area} onChange={(e) => setArea(e.target.value)} className="mt-1">
            <option value="">Todas</option>
            {Object.entries(AREA_LABELS).filter(([k]) => k !== "general").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </label>
        <label className="w-64 text-xs text-muted">
          Conjunto de datos
          <Select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} className="mt-1">
            <option value="">Todos</option>
            {d.datasets.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </Select>
        </label>
        <Checkbox label="Incluir datos de demostración" checked={includeDemo} onChange={(e) => setIncludeDemo(e.target.checked)} />
      </div>

      <div className="space-y-4">
        {d.has_demo_data && (
          <Notice tone="demo">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>
                Hay <strong>datos de demostración</strong> cargados (marcados con <DemoBadge />). No pertenecen a tu organización.
              </span>
              {can("demo.manage") && (
                <Button size="sm" variant="secondary" loading={removeDemo.isPending} onClick={() => removeDemo.mutate()}>
                  Eliminar datos de demostración
                </Button>
              )}
            </div>
          </Notice>
        )}
        {stale.length > 0 && (
          <Notice tone="warn">
            <div className="space-y-1">
              <p>Estos conjuntos cambiaron (datos u objetivos) después de su último análisis. Los resultados mostrados pueden estar desactualizados:</p>
              <ul className="flex flex-wrap gap-2">
                {stale.map((s) => (
                  <li key={s.id}>
                    {can("analysis.run") ? (
                      <Button size="sm" variant="secondary" loading={reanalyze.isPending && reanalyze.variables === s.id} onClick={() => reanalyze.mutate(s.id)}>
                        Analizar «{s.name}»
                      </Button>
                    ) : (
                      <span className="font-medium">{s.name}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </Notice>
        )}

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Hallazgos abiertos" value={d.findings.open_total} hint={`${d.findings.resolved_total} resueltos a la fecha`} />
          <Stat label="Prioridad crítica o alta" value={high} tone={high > 0 ? "bad" : "default"} />
          <Stat
            label="Sobrecosto estimado abierto"
            value={excess ? fmtMoney(excess.amount, d.currency) : "—"}
            hint={excess ? `${excess.findings} hallazgo(s) · estimación, no ahorro realizado` : "Sin sobrecostos calculables"}
            tone={excess ? "warn" : "default"}
          />
          <Stat label="Registros analizados" value={d.total_records.toLocaleString("es-MX")} hint={`${d.datasets.length} conjuntos de datos`} />
        </div>

        <Card>
          <CardHeader title="Indicadores clave" description="Último análisis de cada conjunto. Haz clic para ver fórmula, desglose e historial."
            actions={<ButtonLink href="/kpis" variant="ghost" size="sm">Ver catálogo</ButtonLink>} />
          <CardBody>
            {d.kpis.length === 0 ? (
              <p className="text-sm text-muted">No hay indicadores para el filtro seleccionado.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {d.kpis.map((k) => <KpiCard key={`${k.kpi_code}-${k.dataset_id}`} kpi={k} currency={d.currency} />)}
              </div>
            )}
          </CardBody>
        </Card>

        <div className="grid gap-4 xl:grid-cols-5">
          <Card className="xl:col-span-3">
            <CardHeader title="Problemas prioritarios" description="Hallazgos abiertos ordenados por prioridad."
              actions={<ButtonLink href="/findings" variant="ghost" size="sm">Ver todos</ButtonLink>} />
            {d.findings.top.length === 0 ? (
              <EmptyState title="Sin hallazgos abiertos" description="Las reglas vigentes no detectan problemas en los datos actuales." />
            ) : (
              <ul className="divide-y divide-line">
                {d.findings.top.map((f) => (
                  <li key={f.id}>
                    <Link href={`/findings/${f.id}`} className="flex flex-col gap-1 px-5 py-3 hover:bg-slate-50">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-mono text-xs text-muted">{f.code}</span>
                        <PriorityBadge value={f.priority} />
                        <NatureBadge value={f.nature} />
                        {f.is_demo && <DemoBadge />}
                        {!f.condition_active && <span className="text-xs text-muted">(ya no detectado)</span>}
                      </div>
                      <div className="text-sm font-medium text-ink">{f.title}</div>
                      <div className="text-xs text-muted">
                        {label(AREA_LABELS, f.area)}
                        {f.impact_amount ? ` · ${label(IMPACT_KIND_LABELS, f.impact_kind).toLowerCase()}: ${fmtMoney(f.impact_amount, f.impact_currency ?? d.currency)}` : ""}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card className="xl:col-span-2">
            <CardHeader title="Composición de hallazgos abiertos" />
            <CardBody className="space-y-4 text-sm">
              <Breakdown title="Por área" data={d.findings.by_area} labels={AREA_LABELS} />
              <Breakdown title="Por naturaleza" data={d.findings.by_nature} labels={NATURE_LABELS} />
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Montos económicos por tipo</div>
                {Object.keys(d.impact.open_by_kind).length === 0 ? (
                  <p className="text-xs text-muted">Ningún hallazgo abierto tiene un monto calculable.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {Object.entries(d.impact.open_by_kind).map(([kind, v]) => (
                      <li key={kind} className="flex items-baseline justify-between gap-3 text-xs" title={IMPACT_KIND_HELP[kind]}>
                        <span>{label(IMPACT_KIND_LABELS, kind)} <span className="text-muted">({v.findings})</span></span>
                        <span className="tabular font-medium">{fmtMoney(v.amount, d.currency)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <p className="text-xs text-muted">{d.impact.note}</p>
            </CardBody>
          </Card>
        </div>

        {d.series.length > 0 && (
          <Card>
            <CardHeader title="Evolución mensual" description="Indicadores con al menos dos meses de datos." />
            <CardBody>
              <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
                {d.series.slice(0, 6).map((s) => {
                  const k = kpiByCode[`${s.kpi_code}:${s.dataset_id}`];
                  return (
                    <div key={`${s.kpi_code}-${s.dataset_id}`}>
                      <div className="mb-1 text-sm font-medium">{s.name}</div>
                      <div className="mb-2 text-xs text-muted">{s.dataset_name}</div>
                      <TrendChart points={s.points} unit={s.unit} target={k?.target} direction={k?.direction} currency={d.currency} />
                    </div>
                  );
                })}
              </div>
            </CardBody>
          </Card>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Importaciones recientes" actions={<ButtonLink href="/imports" variant="ghost" size="sm">Historial</ButtonLink>} />
            <ul className="divide-y divide-line text-sm">
              {d.recent_imports.map((i) => (
                <li key={i.id} className="flex items-center justify-between gap-3 px-5 py-2.5">
                  <Link href={`/imports/${i.id}`} className="min-w-0 truncate hover:underline">{i.filename}</Link>
                  <div className="flex shrink-0 items-center gap-2 text-xs text-muted">
                    {i.is_demo && <DemoBadge />}
                    <ImportStatusBadge value={i.status} />
                    {fmtDateTime(i.created_at)}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          {d.activity.length > 0 && (
            <Card>
              <CardHeader title="Actividad reciente" actions={<ButtonLink href="/audit" variant="ghost" size="sm">Auditoría</ButtonLink>} />
              <ul className="divide-y divide-line text-sm">
                {d.activity.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-2.5">
                    <span className="min-w-0 truncate"><span className="font-mono text-xs">{a.action}</span> · {a.actor}</span>
                    <span className="shrink-0 text-xs text-muted">{fmtDateTime(a.created_at)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

function Breakdown({ title, data, labels }: { title: string; data: Record<string, number>; labels: Record<string, string> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      {entries.length === 0 ? (
        <p className="text-xs text-muted">Sin datos.</p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map(([k, v]) => (
            <li key={k} className="grid grid-cols-[9rem_1fr_2rem] items-center gap-2 text-xs">
              <span className="truncate">{label(labels, k)}</span>
              <span className="h-2 rounded bg-slate-100">
                <span className="block h-2 rounded bg-brand" style={{ width: `${(v / max) * 100}%` }} />
              </span>
              <span className="tabular text-right">{v}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
