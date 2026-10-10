"use client";

import { useQuery } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DemoBadge, ImportStatusBadge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { EmptyState, ErrorBanner, Spinner } from "@/components/ui/feedback";
import { Pagination, Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { TEMPLATE_LABELS, label } from "@/lib/labels";
import { useCan } from "@/lib/session";
import type { ImportJob, Page } from "@/lib/types";

export default function ImportsPage() {
  const can = useCan();
  const [page, setPage] = useState(1);
  const q = useQuery({ queryKey: ["imports", page], queryFn: () => api<Page<ImportJob>>("/imports", { query: { page, page_size: 25 } }) });
  return (
    <>
      <PageHeader title="Importaciones" description="Historial completo de archivos cargados, con su huella SHA-256, validación y resultado."
        actions={can("data.import") && <ButtonLink href="/imports/new"><Upload className="h-4 w-4" />Nueva importación</ButtonLink>} />
      <ErrorBanner error={q.error} />
      <Card>
        {q.isLoading ? <Spinner /> : !q.data?.items.length ? (
          <EmptyState title="Sin importaciones" description="Cuando cargues un archivo aparecerá aquí con su estado y trazabilidad." />
        ) : (
          <>
            <Table>
              <thead><tr><Th>#</Th><Th>Archivo</Th><Th>Plantilla</Th><Th>Estado</Th><Th className="text-right">Renglones</Th><Th className="text-right">Importados</Th><Th>Destino</Th><Th>Fecha</Th></tr></thead>
              <tbody className="divide-y divide-line">
                {q.data.items.map((j) => (
                  <tr key={j.id} className="hover:bg-slate-50">
                    <Td className="tabular text-muted">{j.id}</Td>
                    <Td><Link href={`/imports/${j.id}`} className="font-medium hover:underline">{j.original_filename}</Link> {j.is_demo && <DemoBadge />}</Td>
                    <Td>{j.template_code ? label(TEMPLATE_LABELS, j.template_code) : "—"}</Td>
                    <Td><ImportStatusBadge value={j.status} /></Td>
                    <Td className="tabular text-right">{j.total_rows}</Td>
                    <Td className="tabular text-right">{j.imported_rows || "—"}</Td>
                    <Td>{j.target_dataset_id ? <Link className="hover:underline" href={`/datasets/${j.target_dataset_id}`}>{j.target_dataset_name}</Link> : (j.target_dataset_name ?? "—")}</Td>
                    <Td className="whitespace-nowrap text-muted">{fmtDateTime(j.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} pageSize={25} total={q.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
