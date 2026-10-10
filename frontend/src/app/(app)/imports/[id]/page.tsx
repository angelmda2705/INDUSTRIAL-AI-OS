"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { DemoBadge, ImportStatusBadge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardBody, CardHeader, PageHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { fmtBytes, fmtDateTime } from "@/lib/format";
import { TEMPLATE_LABELS, label } from "@/lib/labels";
import { useCan } from "@/lib/session";
import type { ImportJob, ValidationSummary } from "@/lib/types";

export default function ImportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const can = useCan();
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState<"revert" | "discard" | null>(null);
  const q = useQuery({ queryKey: ["import", id], queryFn: () => api<ImportJob>(`/imports/${id}`) });
  const revert = useMutation({
    mutationFn: () => api(`/imports/${id}/revert`, { method: "POST" }),
    onSuccess: () => { setConfirm(null); qc.invalidateQueries(); },
  });
  const discard = useMutation({
    mutationFn: () => api(`/imports/${id}`, { method: "DELETE" }),
    onSuccess: () => { qc.invalidateQueries(); router.replace("/imports"); },
  });

  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBanner error={q.error} />;
  const j = q.data;
  const s = j.validation_summary as Partial<ValidationSummary>;

  return (
    <>
      <PageHeader
        title={`Importación #${j.id}`}
        description={j.original_filename}
        actions={
          <>
            {(j.status === "parsed" || j.status === "validated") && can("data.import") && (
              <>
                <ButtonLink href={`/imports/new?job=${j.id}`}>Continuar</ButtonLink>
                <Button variant="secondary" onClick={() => setConfirm("discard")}>Descartar</Button>
              </>
            )}
            {j.status === "committed" && can("data.delete") && (
              <Button variant="danger" onClick={() => setConfirm("revert")}>Revertir importación</Button>
            )}
          </>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Archivo y estado" />
          <CardBody>
            <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
              <dt className="text-muted">Estado</dt><dd className="flex gap-2"><ImportStatusBadge value={j.status} />{j.is_demo && <DemoBadge />}</dd>
              <dt className="text-muted">Tipo / tamaño</dt><dd>{j.file_type.toUpperCase()} · {fmtBytes(j.file_size)}</dd>
              <dt className="text-muted">SHA-256</dt><dd className="break-all font-mono text-xs">{j.file_sha256}</dd>
              <dt className="text-muted">Hoja</dt><dd>{j.sheet_name ?? "—"}</dd>
              <dt className="text-muted">Renglones</dt><dd>{j.total_rows}</dd>
              <dt className="text-muted">Plantilla</dt><dd>{j.template_code ? label(TEMPLATE_LABELS, j.template_code) : "—"}</dd>
              <dt className="text-muted">Destino</dt>
              <dd>{j.target_dataset_id ? <Link href={`/datasets/${j.target_dataset_id}`} className="underline">{j.target_dataset_name}</Link> : (j.target_dataset_name ?? "—")}</dd>
              <dt className="text-muted">Cargado</dt><dd>{fmtDateTime(j.created_at)}</dd>
              <dt className="text-muted">Confirmado</dt><dd>{fmtDateTime(j.committed_at)}</dd>
              <dt className="text-muted">Revertido</dt><dd>{fmtDateTime(j.reverted_at)}</dd>
              <dt className="text-muted">Opciones</dt><dd>Decimal «{j.parse_options.decimal_separator}», fechas {j.parse_options.date_format === "monthfirst" ? "mes/día" : "día/mes"}</dd>
            </dl>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Validación y mapeo" />
          <CardBody className="space-y-3 text-sm">
            {s.total_rows !== undefined ? (
              <p>
                {s.valid_rows} válidos · {s.invalid_rows} con errores · {s.duplicate_rows} duplicados
                {s.commit && <> · <strong>{s.commit.imported_rows} importados</strong> ({s.commit.skipped_invalid_rows} omitidos por error, {s.commit.skipped_duplicate_rows} por duplicado)</>}
              </p>
            ) : <p className="text-muted">Aún no se valida.</p>}
            {Object.keys(j.column_mapping).length > 0 && (
              <ul className="space-y-1">
                {Object.entries(j.column_mapping).map(([field, col]) => (
                  <li key={field} className="flex justify-between gap-3 border-b border-dashed border-line pb-1">
                    <span className="font-mono text-xs">{field}</span><span>{col}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
      {j.status === "reverted" && <div className="mt-4"><Notice tone="warn">Los registros de esta importación fueron eliminados del conjunto de datos; el registro de la importación se conserva para trazabilidad.</Notice></div>}

      <Dialog open={confirm === "revert"} onClose={() => setConfirm(null)} title="Revertir importación"
        footer={<><Button variant="secondary" onClick={() => setConfirm(null)}>Cancelar</Button><Button variant="danger" loading={revert.isPending} onClick={() => revert.mutate()}>Revertir</Button></>}>
        <ErrorBanner error={revert.error} />
        <p className="text-sm">Se eliminarán los {j.imported_rows} registros que agregó esta importación y se volverá a analizar el conjunto de datos. La acción queda registrada en auditoría.</p>
      </Dialog>
      <Dialog open={confirm === "discard"} onClose={() => setConfirm(null)} title="Descartar importación"
        footer={<><Button variant="secondary" onClick={() => setConfirm(null)}>Cancelar</Button><Button variant="danger" loading={discard.isPending} onClick={() => discard.mutate()}>Descartar</Button></>}>
        <ErrorBanner error={discard.error} />
        <p className="text-sm">Se eliminará el archivo cargado. No se ha importado ningún registro.</p>
      </Dialog>
    </>
  );
}
