"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Evidence } from "@/components/evidence";
import { Badge, DemoBadge, NatureBadge, PriorityBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { api } from "@/lib/api";
import { fmtDateTime, fmtMoney } from "@/lib/format";
import {
  AREA_LABELS,
  CATEGORY_LABELS,
  EVENT_LABELS,
  IMPACT_KIND_HELP,
  IMPACT_KIND_LABELS,
  NATURE_HELP,
  STATUS_LABELS,
  STATUS_TRANSITIONS,
  label,
} from "@/lib/labels";
import { useCan } from "@/lib/session";
import type { FindingDetail, Member } from "@/lib/types";

export default function FindingPage() {
  const { id } = useParams<{ id: string }>();
  const can = useCan();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["finding", id], queryFn: () => api<FindingDetail>(`/findings/${id}`) });
  const members = useQuery({ queryKey: ["members"], queryFn: () => api<Member[]>("/organization/members"), enabled: can("users.read") });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBanner error={q.error} />;
  const f = q.data;
  const onSaved = (updated: FindingDetail) => {
    qc.setQueryData(["finding", id], updated);
    qc.invalidateQueries({ queryKey: ["findings"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  return (
    <div className="space-y-4">
      <div>
        <Link href="/findings" className="text-sm text-muted hover:underline">← Hallazgos</Link>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-muted">{f.code}</span>
          <PriorityBadge value={f.priority} />
          <NatureBadge value={f.nature} />
          <StatusBadge value={f.status} />
          <Badge>{label(AREA_LABELS, f.area)} · {label(CATEGORY_LABELS, f.category)}</Badge>
          {f.is_demo && <DemoBadge />}
        </div>
        <h1 className="mt-2 text-xl font-semibold">{f.title}</h1>
        <p className="mt-1 text-sm text-muted">
          Detectado {fmtDateTime(f.first_detected_at)} · última detección {fmtDateTime(f.last_detected_at)}
          {f.dataset_name && <> · fuente: <Link className="underline" href={`/datasets/${f.dataset_id}`}>{f.dataset_name}</Link></>}
          {f.last_analysis_run_id && <> · análisis #{f.last_analysis_run_id}</>}
        </p>
      </div>
      {!f.condition_active && (
        <Notice>El análisis más reciente ya no detecta esta condición con los datos disponibles. Úsalo como verificación del resultado antes de cerrarlo.</Notice>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Card>
            <CardHeader title="Descripción" />
            <CardBody className="space-y-3 text-sm">
              <p>{f.description}</p>
              <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-muted"><strong>{label({ confirmed_issue: "Hecho verificado", statistical_anomaly: "Anomalía estadística", hypothesis: "Hipótesis" }, f.nature)}:</strong> {NATURE_HELP[f.nature]}</p>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Evidencia" description="Datos exactos que respaldan el hallazgo (filas de origen del archivo importado)." />
            <CardBody><Evidence evidence={f.evidence} /></CardBody>
          </Card>
          <Card>
            <CardHeader title="Método y recomendación" />
            <CardBody className="space-y-3 text-sm">
              <div><div className="text-xs font-semibold uppercase tracking-wide text-muted">Regla / método</div><p className="mt-1"><span className="font-mono text-xs">{f.rule_code}</span> — {f.method}</p></div>
              {f.confidence && (
                <div><div className="text-xs font-semibold uppercase tracking-wide text-muted">Confianza</div><p className="mt-1"><strong>{f.confidence}</strong>. {f.confidence_basis}</p></div>
              )}
              <div><div className="text-xs font-semibold uppercase tracking-wide text-muted">Impacto económico</div>
                {f.impact_amount !== null ? (
                  <div className="mt-1 space-y-1">
                    <p><strong>{fmtMoney(f.impact_amount, f.impact_currency ?? "MXN")}</strong> · {label(IMPACT_KIND_LABELS, f.impact_kind)}</p>
                    <p className="text-xs text-muted">{f.impact_kind ? IMPACT_KIND_HELP[f.impact_kind] : ""} Base de cálculo: {f.impact_basis}</p>
                  </div>
                ) : <p className="mt-1">No calculable con los datos disponibles.</p>}
              </div>
              <div><div className="text-xs font-semibold uppercase tracking-wide text-muted">Recomendación</div><p className="mt-1">{f.recommendation}</p></div>
            </CardBody>
          </Card>
        </div>
        <div className="space-y-4">
          {can("findings.update") ? (
            <Workflow finding={f} members={members.data ?? []} canAssign={can("users.read")} onSaved={onSaved} />
          ) : (
            <Card><CardBody className="text-sm text-muted">Tu rol permite consultar este hallazgo, pero no modificarlo.</CardBody></Card>
          )}
          <Card>
            <CardHeader title="Historial" />
            <ol className="divide-y divide-line text-sm">
              {[...f.events].reverse().map((e) => (
                <li key={e.id} className="px-5 py-3">
                  <div className="flex justify-between gap-2 text-xs text-muted"><span>{e.actor_label}</span><span>{fmtDateTime(e.created_at)}</span></div>
                  <div className="mt-0.5 font-medium">
                    {label(EVENT_LABELS, e.event_type)}
                    {e.from_status && e.to_status && <span className="font-normal text-muted"> · {label(STATUS_LABELS, e.from_status)} → {label(STATUS_LABELS, e.to_status)}</span>}
                  </div>
                  {e.note && <p className="mt-1 whitespace-pre-wrap text-sm">{e.note}</p>}
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Workflow({ finding, members, canAssign, onSaved }: { finding: FindingDetail; members: Member[]; canAssign: boolean; onSaved: (f: FindingDetail) => void }) {
  const [status, setStatus] = useState("");
  const [note, setNote] = useState("");
  const [owner, setOwner] = useState(finding.owner_user_id ? String(finding.owner_user_id) : "");
  const [due, setDue] = useState(finding.due_date ?? "");
  useEffect(() => { setOwner(finding.owner_user_id ? String(finding.owner_user_id) : ""); setDue(finding.due_date ?? ""); }, [finding]);
  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      if (status) body.status = status;
      if (note.trim()) body.note = note.trim();
      if (canAssign && owner !== (finding.owner_user_id ? String(finding.owner_user_id) : "")) body.owner_user_id = owner ? Number(owner) : null;
      if (due !== (finding.due_date ?? "")) body.due_date = due || null;
      return api<FindingDetail>(`/findings/${finding.id}`, { method: "PATCH", body });
    },
    onSuccess: (f) => { setStatus(""); setNote(""); onSaved(f); },
  });
  const needsNote = status === "resolved" || status === "dismissed";
  return (
    <Card>
      <CardHeader title="Seguimiento" description="Los cambios quedan en el historial y en auditoría." />
      <CardBody className="space-y-3">
        <ErrorBanner error={save.error} />
        <Field label="Cambiar estado" htmlFor="status">
          <Select id="status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Mantener «{label(STATUS_LABELS, finding.status)}»</option>
            {STATUS_TRANSITIONS[finding.status].map((s) => <option key={s} value={s}>{label(STATUS_LABELS, s)}</option>)}
          </Select>
        </Field>
        {canAssign && (
          <Field label="Responsable" htmlFor="owner">
            <Select id="owner" value={owner} onChange={(e) => setOwner(e.target.value)}>
              <option value="">Sin asignar</option>
              {members.filter((m) => m.is_active).map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name} ({m.role_label})</option>)}
            </Select>
          </Field>
        )}
        <Field label="Fecha límite" htmlFor="due"><Input id="due" type="date" value={due} onChange={(e) => setDue(e.target.value)} /></Field>
        <Field label={needsNote ? "Nota (obligatoria)" : "Comentario"} htmlFor="note"
          hint={needsNote ? "Explica la resolución con evidencia, o el motivo del descarte." : undefined}>
          <Textarea id="note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <Button className="w-full" loading={save.isPending} disabled={needsNote && !note.trim()} onClick={() => save.mutate()}>Guardar</Button>
      </CardBody>
    </Card>
  );
}
