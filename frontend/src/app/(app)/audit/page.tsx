"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Card, PageHeader } from "@/components/ui/card";
import { EmptyState, ErrorBanner, Spinner } from "@/components/ui/feedback";
import { Input } from "@/components/ui/field";
import { Pagination, Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import type { AuditEntry, Page } from "@/lib/types";

export default function AuditPage() {
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["audit", action, actor, from, to, page],
    queryFn: () => api<Page<AuditEntry>>("/audit", {
      query: { action, actor, date_from: from ? `${from}T00:00:00Z` : "", date_to: to ? `${to}T23:59:59Z` : "", page, page_size: 50 },
    }),
  });
  return (
    <>
      <PageHeader title="Auditoría" description="Registro inalterable de acciones relevantes: accesos, importaciones, análisis, cambios de configuración y seguimiento de hallazgos." />
      <Card className="mb-4 px-4 py-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="w-52 text-xs text-muted">Acción (prefijo)<Input className="mt-1" placeholder="ej. import." value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} /></label>
          <label className="w-52 text-xs text-muted">Usuario<Input className="mt-1" value={actor} onChange={(e) => { setActor(e.target.value); setPage(1); }} /></label>
          <label className="w-40 text-xs text-muted">Desde<Input className="mt-1" type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} /></label>
          <label className="w-40 text-xs text-muted">Hasta<Input className="mt-1" type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} /></label>
        </div>
      </Card>
      <ErrorBanner error={q.error} />
      <Card>
        {q.isLoading ? <Spinner /> : !q.data?.items.length ? <EmptyState title="Sin eventos" /> : (
          <>
            <Table>
              <thead><tr><Th>Fecha</Th><Th>Usuario</Th><Th>Acción</Th><Th>Entidad</Th><Th>Detalle</Th><Th>IP / solicitud</Th></tr></thead>
              <tbody className="divide-y divide-line">
                {q.data.items.map((a) => (
                  <tr key={a.id}>
                    <Td className="whitespace-nowrap text-muted">{fmtDateTime(a.created_at)}</Td>
                    <Td>{a.actor_label}</Td>
                    <Td className="font-mono text-xs">{a.action}</Td>
                    <Td className="text-xs">{a.entity_type ? `${a.entity_type} #${a.entity_id}` : "—"}</Td>
                    <Td className="max-w-md">
                      {Object.keys(a.details).length > 0 && (
                        <details className="text-xs">
                          <summary className="cursor-pointer text-muted">Ver</summary>
                          <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all rounded bg-slate-50 p-2">{JSON.stringify(a.details, null, 2)}</pre>
                        </details>
                      )}
                    </Td>
                    <Td className="font-mono text-[11px] text-muted">{a.ip_address ?? "—"}<br />{a.request_id?.slice(0, 12)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} pageSize={50} total={q.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
