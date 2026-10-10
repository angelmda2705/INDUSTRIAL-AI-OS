"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Badge, DemoBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, PageHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorBanner, Spinner } from "@/components/ui/feedback";
import { Field, Input, Textarea } from "@/components/ui/field";
import { api } from "@/lib/api";
import { fmtKpi } from "@/lib/format";
import { AREA_LABELS, DIRECTION_LABELS, label } from "@/lib/labels";
import { useCan, useMe } from "@/lib/session";
import type { KpiDefinition, KpiValue } from "@/lib/types";

export default function KpisPage() {
  const can = useCan();
  const { data: me } = useMe();
  const currency = String(me?.organization?.settings?.currency ?? "MXN");
  const catalog = useQuery({ queryKey: ["kpi-catalog"], queryFn: () => api<KpiDefinition[]>("/kpis/catalog") });
  const values = useQuery({ queryKey: ["kpi-values"], queryFn: () => api<KpiValue[]>("/kpis/values") });
  const [editing, setEditing] = useState<KpiDefinition | null>(null);

  if (catalog.isLoading) return <Spinner />;
  if (catalog.error) return <ErrorBanner error={catalog.error} />;
  const byArea = new Map<string, KpiDefinition[]>();
  catalog.data!.forEach((k) => byArea.set(k.area, [...(byArea.get(k.area) ?? []), k]));

  return (
    <>
      <PageHeader title="Catálogo de indicadores"
        description="Cada indicador documenta su fórmula, unidad, datos requeridos, tratamiento de faltantes y supuestos. Los objetivos los define tu organización; no se asumen estándares universales." />
      <div className="space-y-6">
        {[...byArea.entries()].map(([area, kpis]) => (
          <section key={area}>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{label(AREA_LABELS, area)}</h2>
            <div className="grid gap-3 lg:grid-cols-2">
              {kpis.map((k) => {
                const vals = (values.data ?? []).filter((v) => v.kpi_code === k.code);
                return (
                  <Card key={k.code}>
                    <CardBody className="space-y-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <h3 className="font-medium">{k.name}</h3>
                          <p className="text-xs text-muted">{k.description}</p>
                        </div>
                        <Badge>{DIRECTION_LABELS[k.direction]}</Badge>
                      </div>
                      <div className="rounded-md bg-slate-50 px-3 py-2 font-mono text-xs">{k.formula} <span className="text-muted">[{k.unit}]</span></div>
                      <details className="text-xs text-muted">
                        <summary className="cursor-pointer select-none">Requisitos y supuestos</summary>
                        <ul className="mt-2 list-disc space-y-1 pl-5">
                          <li><strong>Mínimo:</strong> {k.min_requirements}</li>
                          <li><strong>Faltantes:</strong> {k.missing_handling}</li>
                          <li><strong>Campos:</strong> {k.required_fields.join(", ")}</li>
                          <li><strong>Frecuencia:</strong> {k.frequency}{k.dimension ? ` · desglose por ${k.dimension}` : ""}</li>
                          {k.assumptions.map((a, i) => <li key={i}>{a}</li>)}
                        </ul>
                      </details>
                      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-sm">
                        <div>
                          {k.target ? (
                            <span>Objetivo: <strong>{fmtKpi(k.target.target_value, k.unit, currency)}</strong>
                              {k.target.tolerance ? ` ± ${fmtKpi(k.target.tolerance, k.unit, currency)}` : ""}
                              {k.target.owner_label ? <span className="text-muted"> · {k.target.owner_label}</span> : null}</span>
                          ) : <span className="text-muted">{k.direction === "neutral" ? "Indicador informativo" : "Sin objetivo definido"}</span>}
                        </div>
                        {can("kpi.manage") && k.direction !== "neutral" && (
                          <Button size="sm" variant="secondary" onClick={() => setEditing(k)}>{k.target ? "Editar objetivo" : "Definir objetivo"}</Button>
                        )}
                      </div>
                      {vals.length > 0 && (
                        <ul className="space-y-1 border-t border-line pt-3 text-sm">
                          {vals.map((v) => (
                            <li key={v.dataset_id} className="flex items-center justify-between gap-2">
                              <Link href={`/kpis/${k.code}?dataset=${v.dataset_id}`} className="min-w-0 truncate hover:underline">{v.dataset_name}</Link>
                              <span className="flex shrink-0 items-center gap-1.5">
                                {v.is_demo && <DemoBadge />}
                                {v.status === "ok" ? <strong className="tabular">{fmtKpi(v.value, v.unit, currency)}</strong> : <span className="text-xs text-amber-700" title={v.message ?? ""}>Datos insuficientes</span>}
                                {v.evaluation && <Badge tone={v.evaluation === "meets" ? "green" : "red"}>{v.evaluation === "meets" ? "Cumple" : "No cumple"}</Badge>}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </CardBody>
                  </Card>
                );
              })}
            </div>
          </section>
        ))}
      </div>
      {editing && <TargetDialog kpi={editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function TargetDialog({ kpi, onClose }: { kpi: KpiDefinition; onClose: () => void }) {
  const qc = useQueryClient();
  const [value, setValue] = useState(kpi.target ? String(kpi.target.target_value) : "");
  const [tolerance, setTolerance] = useState(kpi.target ? String(kpi.target.tolerance) : "0");
  const [owner, setOwner] = useState(kpi.target?.owner_label ?? "");
  const [notes, setNotes] = useState(kpi.target?.notes ?? "");
  const done = () => { qc.invalidateQueries(); onClose(); };
  const save = useMutation({
    mutationFn: () => api(`/kpis/${kpi.code}/target`, { method: "PUT", body: { target_value: Number(value), tolerance: Number(tolerance || 0), owner_label: owner || null, notes: notes || null } }),
    onSuccess: done,
  });
  const remove = useMutation({ mutationFn: () => api(`/kpis/${kpi.code}/target`, { method: "DELETE" }), onSuccess: done });
  const valid = value.trim() !== "" && !Number.isNaN(Number(value)) && Number(tolerance) >= 0;
  return (
    <Dialog open onClose={onClose} title={`Objetivo: ${kpi.name}`}
      footer={<>
        {kpi.target && <Button variant="ghost" loading={remove.isPending} onClick={() => remove.mutate()}>Quitar objetivo</Button>}
        <Button variant="secondary" onClick={onClose}>Cancelar</Button>
        <Button disabled={!valid} loading={save.isPending} onClick={() => save.mutate()}>Guardar</Button>
      </>}>
      <div className="space-y-3">
        <ErrorBanner error={save.error ?? remove.error} />
        <p className="text-sm text-muted">{DIRECTION_LABELS[kpi.direction]}. Al guardar, los conjuntos relacionados quedan marcados para un nuevo análisis, que generará o cerrará los hallazgos de desviación.</p>
        <Field label={`Valor objetivo (${kpi.unit})`} htmlFor="tv" required><Input id="tv" type="number" step="any" value={value} onChange={(e) => setValue(e.target.value)} /></Field>
        <Field label="Tolerancia" htmlFor="tol" hint="Margen permitido antes de reportar una desviación, en las mismas unidades."><Input id="tol" type="number" step="any" min="0" value={tolerance} onChange={(e) => setTolerance(e.target.value)} /></Field>
        <Field label="Responsable del indicador" htmlFor="own"><Input id="own" value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="Ej. Gerencia de planta" /></Field>
        <Field label="Notas / fuente del objetivo" htmlFor="notes"><Textarea id="notes" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      </div>
    </Dialog>
  );
}
