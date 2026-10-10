"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge, DemoBadge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { EmptyState, ErrorBanner, Spinner } from "@/components/ui/feedback";
import { Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { TEMPLATE_LABELS, label } from "@/lib/labels";
import type { Dataset } from "@/lib/types";

export default function DatasetsPage() {
  const q = useQuery({ queryKey: ["datasets"], queryFn: () => api<Dataset[]>("/datasets") });
  return (
    <>
      <PageHeader title="Conjuntos de datos" description="Cada conjunto agrupa registros validados de una misma plantilla. Los indicadores y hallazgos se calculan por conjunto." />
      <ErrorBanner error={q.error} />
      <Card>
        {q.isLoading ? <Spinner /> : !q.data?.length ? (
          <EmptyState title="Sin conjuntos de datos" description="Se crean al confirmar una importación." actions={<ButtonLink href="/imports/new">Importar datos</ButtonLink>} />
        ) : (
          <Table>
            <thead><tr><Th>Nombre</Th><Th>Plantilla</Th><Th className="text-right">Registros</Th><Th>Último análisis</Th><Th>Estado</Th></tr></thead>
            <tbody className="divide-y divide-line">
              {q.data.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50">
                  <Td><Link href={`/datasets/${d.id}`} className="font-medium hover:underline">{d.name}</Link> {d.is_demo && <DemoBadge />}</Td>
                  <Td>{label(TEMPLATE_LABELS, d.template_code)}</Td>
                  <Td className="tabular text-right">{d.row_count.toLocaleString("es-MX")}</Td>
                  <Td className="text-muted">{fmtDateTime(d.last_analyzed_at)}</Td>
                  <Td>{d.analysis_stale ? <Badge tone="amber">Requiere nuevo análisis</Badge> : <Badge tone="green">Actualizado</Badge>}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
