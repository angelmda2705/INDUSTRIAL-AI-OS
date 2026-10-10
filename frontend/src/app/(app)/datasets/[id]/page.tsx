"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge, DemoBadge, ImportStatusBadge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardHeader, PageHeader, Stat } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/field";
import { Pagination, Table, Td, Th } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { api, downloadUrl } from "@/lib/api";
import { fmtCell, fmtDate, fmtDateTime, fmtNumber } from "@/lib/format";
import { TEMPLATE_LABELS, label } from "@/lib/labels";
import { useCan } from "@/lib/session";
import type { AnalysisRun, DataProfile, Dataset, ImportJob, Page } from "@/lib/types";

type Detail = {
  dataset: Dataset;
  template: { code: string; name: string; area: string; fields: { name: string; label: string; type: string }[] };
  latest_run: AnalysisRun | null;
  profile: DataProfile | null;
  imports: ImportJob[];
};
type Tab = "quality" | "records" | "runs" | "inventory" | "imports";

export default function DatasetPage() {
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const qc = useQueryClient();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("quality");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const q = useQuery({ queryKey: ["dataset", id], queryFn: () => api<Detail>(`/datasets/${id}`) });
  const analyze = useMutation({ mutationFn: () => api<AnalysisRun>(`/datasets/${id}/analyze`, { method: "POST" }), onSuccess: () => qc.invalidateQueries() });
  const del = useMutation({
    mutationFn: () => api(`/datasets/${id}`, { method: "DELETE" }),
    onSuccess: () => { qc.invalidateQueries(); router.replace("/datasets"); },
  });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBanner error={q.error} />;
  const { dataset: d, template, latest_run: run, profile } = q.data;
  const tabs: { id: Tab; label: string }[] = [
    { id: "quality", label: "Calidad de datos" },
    { id: "records", label: "Registros" },
    ...(d.template_code === "inventory_items" ? [{ id: "inventory" as Tab, label: "Análisis por artículo" }] : []),
    { id: "runs", label: "Historial de análisis" },
    { id: "imports", label: "Importaciones" },
  ];

  return (
    <>
      <PageHeader
        title={d.name}
        description={<span className="flex flex-wrap items-center gap-2">{label(TEMPLATE_LABELS, d.template_code)} · {d.row_count.toLocaleString("es-MX")} registros {d.is_demo && <DemoBadge />}</span>}
        actions={
          <>
            {can("analysis.run") && <Button variant="secondary" loading={analyze.isPending} onClick={() => analyze.mutate()}><RefreshCw className="h-4 w-4" />Analizar ahora</Button>}
            <ButtonLink variant="secondary" external href={downloadUrl(`/datasets/${id}/export`)}><Download className="h-4 w-4" />Exportar Excel</ButtonLink>
            {can("data.delete") && <Button variant="ghost" onClick={() => setConfirmDelete(true)}><Trash2 className="h-4 w-4" />Eliminar</Button>}
          </>
        }
      />
      <div className="mb-4 space-y-3">
        <ErrorBanner error={analyze.error} />
        {d.analysis_stale && <Notice tone="warn">Los datos u objetivos cambiaron después del último análisis. Ejecuta «Analizar ahora» para actualizar indicadores y hallazgos.</Notice>}
        {d.description && <Notice>{d.description}</Notice>}
      </div>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "quality" && <QualityTab profile={profile} run={run} />}
      {tab === "records" && <RecordsTab datasetId={d.id} fields={template.fields} />}
      {tab === "inventory" && <InventoryTab datasetId={d.id} />}
      {tab === "runs" && <RunsTab datasetId={d.id} />}
      {tab === "imports" && <ImportsTab imports={q.data.imports} />}

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Eliminar conjunto de datos"
        footer={<><Button variant="secondary" onClick={() => setConfirmDelete(false)}>Cancelar</Button><Button variant="danger" loading={del.isPending} onClick={() => del.mutate()}>Eliminar definitivamente</Button></>}>
        <ErrorBanner error={del.error} />
        <p className="text-sm">Se eliminarán {d.row_count} registros, sus análisis, indicadores y hallazgos. Las importaciones se conservan en el historial para trazabilidad. Esta acción no se puede deshacer y queda registrada en auditoría.</p>
      </Dialog>
    </>
  );
}

function QualityTab({ profile, run }: { profile: DataProfile | null; run: AnalysisRun | null }) {
  if (!profile || !run) return <Card><EmptyState title="Sin análisis" description="Ejecuta el análisis para obtener el perfil de calidad." /></Card>;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Registros" value={profile.row_count.toLocaleString("es-MX")} />
        <Stat label="Completitud" value={profile.completeness_pct !== null ? `${fmtNumber(profile.completeness_pct, 1)} %` : "—"} hint={profile.completeness_definition} />
        <Stat label="Periodo" value={profile.date_range ? `${fmtDate(profile.date_range.from)}` : "—"} hint={profile.date_range ? `hasta ${fmtDate(profile.date_range.to)}` : "Sin campo de fecha"} />
        <Stat label="Análisis" value={`#${run.id}`} hint={fmtDateTime(run.finished_at)} />
      </div>
      <Card>
        <CardHeader title="Perfil por campo" description="Valores atípicos por rango intercuartílico (1.5 × IQR); son señales para revisar, no errores confirmados." />
        <Table>
          <thead><tr><Th>Campo</Th><Th>Tipo</Th><Th className="text-right">Vacíos</Th><Th className="text-right">Distintos</Th><Th>Rango</Th><Th className="text-right">Media</Th><Th className="text-right">Atípicos</Th><Th>Valores frecuentes</Th></tr></thead>
          <tbody className="divide-y divide-line">
            {profile.fields.map((f) => (
              <tr key={f.field}>
                <Td className="font-medium">{f.label}</Td>
                <Td className="text-muted">{f.type}</Td>
                <Td className="tabular text-right">{f.missing ? <Badge tone={(f.missing_pct ?? 0) >= 20 ? "amber" : "gray"}>{f.missing} ({fmtNumber(f.missing_pct, 1)} %)</Badge> : "0"}</Td>
                <Td className="tabular text-right">{f.distinct}</Td>
                <Td className="whitespace-nowrap text-xs">{f.min !== undefined ? `${fmtCell(f.min)} – ${fmtCell(f.max)}` : "—"}</Td>
                <Td className="tabular text-right">{f.mean !== undefined ? fmtNumber(f.mean ?? null) : "—"}</Td>
                <Td className="tabular text-right">{f.iqr_outliers ?? "—"}{f.negatives ? <span className="ml-1 text-xs text-red-700">({f.negatives} neg.)</span> : null}</Td>
                <Td className="text-xs text-muted">{f.top_values?.map((t) => `${t.value} (${t.count})`).join(", ") ?? ""}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}

function RecordsTab({ datasetId, fields }: { datasetId: number; fields: { name: string; label: string }[] }) {
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["records", datasetId, page],
    queryFn: () => api<Page<{ id: number; source_row: number; import_job_id: number | null; data: Record<string, unknown> }>>(`/datasets/${datasetId}/records`, { query: { page, page_size: 50 } }),
  });
  const cols = useMemo(() => {
    if (fields.length) return fields;
    const keys = new Set<string>();
    q.data?.items.forEach((r) => Object.keys(r.data).forEach((k) => keys.add(k)));
    return [...keys].map((k) => ({ name: k, label: k }));
  }, [fields, q.data]);
  if (q.isLoading) return <Spinner />;
  return (
    <Card>
      <ErrorBanner error={q.error} />
      <Table>
        <thead><tr><Th>Imp.</Th><Th>Fila</Th>{cols.map((c) => <Th key={c.name}>{c.label}</Th>)}</tr></thead>
        <tbody className="divide-y divide-line">
          {q.data?.items.map((r) => (
            <tr key={r.id}>
              <Td className="tabular text-muted">{r.import_job_id ? <Link className="hover:underline" href={`/imports/${r.import_job_id}`}>#{r.import_job_id}</Link> : "—"}</Td>
              <Td className="tabular text-muted">{r.source_row}</Td>
              {cols.map((c) => <Td key={c.name} className="whitespace-nowrap">{fmtCell(r.data[c.name])}</Td>)}
            </tr>
          ))}
        </tbody>
      </Table>
      <Pagination page={page} pageSize={50} total={q.data?.total ?? 0} onPage={setPage} />
    </Card>
  );
}

type InventoryAnalysis = { columns: { key: string; label: string }[]; items: Record<string, string | number | null>[]; reference_date: string | null };

function InventoryTab({ datasetId }: { datasetId: number }) {
  const q = useQuery({ queryKey: ["inventory", datasetId], queryFn: () => api<InventoryAnalysis>(`/datasets/${datasetId}/inventory-analysis`) });
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBanner error={q.error} />;
  const items = q.data.items.filter(
    (i) => (!status || i.status === status) && (!search || `${i.sku} ${i.description ?? ""}`.toLowerCase().includes(search.toLowerCase())),
  );
  const tone = (s: unknown) => (s === "sin existencia" || s === "negativo" ? "red" : s === "bajo ROP" ? "amber" : s === "exceso" ? "blue" : "green");
  return (
    <Card>
      <CardHeader title="Análisis por artículo"
        description={`ROP = demanda × lead time + stock de seguridad (z·σ·√L). Las cantidades sugeridas son propuestas: no se generó ninguna compra.${q.data.reference_date ? ` Días sin movimiento respecto del ${fmtDate(q.data.reference_date)}.` : ""}`}
        actions={<>
          <Input placeholder="Buscar SKU o descripción" value={search} onChange={(e) => setSearch(e.target.value)} className="w-56" aria-label="Buscar artículo" />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-44" aria-label="Filtrar por estado">
            <option value="">Todos los estados</option>
            {["sin existencia", "negativo", "bajo ROP", "exceso", "normal"].map((s) => <option key={s}>{s}</option>)}
          </Select>
        </>} />
      <Table className="max-h-[60vh]">
        <thead><tr><Th>Estado</Th>{q.data.columns.map((c) => <Th key={c.key}>{c.label}</Th>)}</tr></thead>
        <tbody className="divide-y divide-line">
          {items.map((i, n) => (
            <tr key={n}>
              <Td><Badge tone={tone(i.status)}>{String(i.status)}</Badge></Td>
              {q.data.columns.map((c) => <Td key={c.key} className="whitespace-nowrap tabular">{fmtCell(i[c.key])}</Td>)}
            </tr>
          ))}
        </tbody>
      </Table>
      <div className="border-t border-line px-4 py-2 text-xs text-muted">{items.length} de {q.data.items.length} artículos</div>
    </Card>
  );
}

function RunsTab({ datasetId }: { datasetId: number }) {
  const q = useQuery({ queryKey: ["runs", datasetId], queryFn: () => api<AnalysisRun[]>(`/datasets/${datasetId}/runs`) });
  if (q.isLoading) return <Spinner />;
  return (
    <Card>
      <ErrorBanner error={q.error} />
      <Table>
        <thead><tr><Th>#</Th><Th>Origen</Th><Th>Estado</Th><Th>Fin</Th><Th className="text-right">Registros</Th><Th>Periodo</Th><Th>Resultado</Th></tr></thead>
        <tbody className="divide-y divide-line">
          {q.data?.map((r) => (
            <tr key={r.id}>
              <Td className="tabular">{r.id}</Td>
              <Td>{{ manual: "Manual", import: "Importación", demo: "Demo" }[r.trigger] ?? r.trigger}</Td>
              <Td><Badge tone={r.status === "completed" ? "green" : r.status === "failed" ? "red" : "gray"}>{r.status === "completed" ? "Completado" : r.status === "failed" ? "Falló" : r.status}</Badge></Td>
              <Td className="whitespace-nowrap text-muted">{fmtDateTime(r.finished_at)}</Td>
              <Td className="tabular text-right">{r.record_count}</Td>
              <Td className="whitespace-nowrap text-xs">{r.period_start ? `${fmtDate(r.period_start)} – ${fmtDate(r.period_end)}` : "—"}</Td>
              <Td className="text-xs text-muted">
                {r.status === "failed" ? r.error_message : `${r.summary.kpis_computed ?? 0} KPI · ${r.summary.findings_created ?? 0} nuevos · ${r.summary.findings_no_longer_detected ?? 0} ya no detectados`}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

function ImportsTab({ imports }: { imports: ImportJob[] }) {
  return (
    <Card>
      <Table>
        <thead><tr><Th>#</Th><Th>Archivo</Th><Th>Estado</Th><Th className="text-right">Importados</Th><Th>Confirmado</Th></tr></thead>
        <tbody className="divide-y divide-line">
          {imports.map((j) => (
            <tr key={j.id}>
              <Td className="tabular">{j.id}</Td>
              <Td><Link href={`/imports/${j.id}`} className="hover:underline">{j.original_filename}</Link></Td>
              <Td><ImportStatusBadge value={j.status} /></Td>
              <Td className="tabular text-right">{j.imported_rows}</Td>
              <Td className="text-muted">{fmtDateTime(j.committed_at)}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}
