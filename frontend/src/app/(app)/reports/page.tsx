"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { useState } from "react";

import { Badge, DemoBadge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardBody, CardHeader, PageHeader } from "@/components/ui/card";
import { EmptyState, ErrorBanner, Spinner } from "@/components/ui/feedback";
import { Checkbox, Field, Select } from "@/components/ui/field";
import { Table, Td, Th } from "@/components/ui/table";
import { api, downloadUrl } from "@/lib/api";
import { fmtBytes, fmtDateTime } from "@/lib/format";
import { REPORT_TYPE_LABELS, label } from "@/lib/labels";
import type { Report } from "@/lib/types";

export default function ReportsPage() {
  const qc = useQueryClient();
  const [type, setType] = useState("diagnostic");
  const [format, setFormat] = useState<"pdf" | "xlsx">("pdf");
  const [includeDemo, setIncludeDemo] = useState(true);
  const list = useQuery({ queryKey: ["reports"], queryFn: () => api<Report[]>("/reports") });
  const generate = useMutation({
    mutationFn: () => api<Report>("/reports", { body: { report_type: type, file_format: format, include_demo: includeDemo } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });
  return (
    <>
      <PageHeader title="Reportes"
        description="Se generan exclusivamente con los datos almacenados: incluyen periodo, fuentes con su huella SHA-256, indicadores, hallazgos con evidencia, limitaciones y acciones pendientes." />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Generar reporte" />
          <CardBody className="space-y-3">
            <ErrorBanner error={generate.error} />
            <Field label="Tipo" htmlFor="rtype">
              <Select id="rtype" value={type} onChange={(e) => setType(e.target.value)}>
                {Object.entries(REPORT_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            </Field>
            <fieldset className="space-y-1">
              <legend className="text-sm font-medium">Formato</legend>
              <div className="flex gap-4 text-sm">
                <label className="flex items-center gap-2"><input type="radio" checked={format === "pdf"} onChange={() => setFormat("pdf")} /> PDF</label>
                <label className="flex items-center gap-2"><input type="radio" checked={format === "xlsx"} onChange={() => setFormat("xlsx")} /> Excel</label>
              </div>
            </fieldset>
            <Checkbox label="Incluir datos de demostración" checked={includeDemo} onChange={(e) => setIncludeDemo(e.target.checked)} />
            <Button className="w-full" loading={generate.isPending} onClick={() => generate.mutate()}><FileText className="h-4 w-4" />Generar</Button>
          </CardBody>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Reportes generados" />
          {list.isLoading ? <Spinner /> : !list.data?.length ? (
            <EmptyState title="Aún no hay reportes" description="Los reportes generados se conservan aquí para descargarlos de nuevo." />
          ) : (
            <Table>
              <thead><tr><Th>Reporte</Th><Th>Formato</Th><Th>Periodo</Th><Th>Generado</Th><Th /></tr></thead>
              <tbody className="divide-y divide-line">
                {list.data.map((r) => (
                  <tr key={r.id}>
                    <Td>
                      <div className="font-medium">{label(REPORT_TYPE_LABELS, r.report_type)} {r.parameters.is_demo ? <DemoBadge /> : null}</div>
                      <div className="font-mono text-xs text-muted" title={r.file_sha256}>sha256 {r.file_sha256.slice(0, 12)}… · {fmtBytes(r.file_size)}</div>
                    </Td>
                    <Td><Badge>{r.file_format.toUpperCase()}</Badge></Td>
                    <Td className="text-xs">{String(r.parameters.period ?? "—")}</Td>
                    <Td className="whitespace-nowrap text-muted">{fmtDateTime(r.created_at)}</Td>
                    <Td><ButtonLink size="sm" variant="secondary" external href={downloadUrl(`/reports/${r.id}/download`)}><Download className="h-4 w-4" />Descargar</ButtonLink></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      </div>
    </>
  );
}
