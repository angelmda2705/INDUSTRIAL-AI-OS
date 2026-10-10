"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, FileSpreadsheet, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card, CardBody, CardHeader, PageHeader, Stat } from "@/components/ui/card";
import { ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Checkbox, Field, Input, Select } from "@/components/ui/field";
import { Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtBytes, fmtCell } from "@/lib/format";
import { AREA_LABELS, label } from "@/lib/labels";
import type { AnalysisRun, Dataset, ImportJob, Preview, Template, ValidationSummary } from "@/lib/types";

const STEPS = ["Cargar archivo", "Revisar y mapear", "Validar", "Confirmar"];

function Stepper({ current }: { current: number }) {
  return (
    <ol className="mb-6 flex flex-wrap gap-2 text-xs">
      {STEPS.map((s, i) => (
        <li
          key={s}
          className={clsx(
            "flex items-center gap-2 rounded-full border px-3 py-1",
            i === current ? "border-brand bg-teal-50 font-medium text-teal-900" : i < current ? "border-line text-ink" : "border-line text-muted",
          )}
        >
          <span className="tabular">{i + 1}</span>
          {s}
        </li>
      ))}
    </ol>
  );
}

function UploadStep({ onUploaded }: { onUploaded: (job: ImportJob) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const upload = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData();
      form.append("file", f);
      return api<ImportJob>("/imports", { form });
    },
    onSuccess: onUploaded,
  });
  return (
    <Card>
      <CardHeader title="1. Cargar archivo" description="Formatos aceptados: Excel (.xlsx) sin macros o CSV (UTF-8 o Windows-1252), hasta 20 MB." />
      <CardBody className="space-y-4">
        <ErrorBanner error={upload.error} />
        <label
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); }}
          className={clsx(
            "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center",
            drag ? "border-brand bg-teal-50" : "border-line hover:bg-slate-50",
          )}
        >
          <UploadCloud className="mb-2 h-8 w-8 text-slate-400" aria-hidden />
          <span className="text-sm font-medium">{file ? file.name : "Arrastra el archivo aquí o haz clic para elegirlo"}</span>
          <span className="mt-1 text-xs text-muted">{file ? fmtBytes(file.size) : "La primera fila no vacía debe contener los encabezados."}</span>
          <input type="file" accept=".csv,.xlsx,.txt" className="sr-only" data-testid="file-input"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <div className="flex justify-end">
          <Button disabled={!file} loading={upload.isPending} onClick={() => file && upload.mutate(file)}>
            Cargar y analizar columnas
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function MappingStep({ job, onValidated }: { job: ImportJob; onValidated: (job: ImportJob, summary: ValidationSummary) => void }) {
  const [sheet, setSheet] = useState<string | null>(job.sheet_name);
  const preview = useQuery({
    queryKey: ["preview", job.id, sheet],
    queryFn: () => api<Preview>(`/imports/${job.id}/preview`, { query: { sheet: sheet ?? undefined } }),
  });
  const templates = useQuery({ queryKey: ["templates"], queryFn: () => api<Template[]>("/imports/templates") });
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: () => api<Dataset[]>("/datasets") });

  const [templateCode, setTemplateCode] = useState<string>(job.template_code ?? "");
  const [mapping, setMapping] = useState<Record<string, string>>(job.column_mapping ?? {});
  const [decimal, setDecimal] = useState(job.parse_options.decimal_separator ?? ".");
  const [dateFormat, setDateFormat] = useState(job.parse_options.date_format ?? "dayfirst");
  const [destination, setDestination] = useState<"new" | "existing">(job.target_dataset_id ? "existing" : "new");
  const [datasetName, setDatasetName] = useState(job.target_dataset_name ?? job.original_filename.replace(/\.[^.]+$/, ""));
  const [datasetId, setDatasetId] = useState<string>(job.target_dataset_id ? String(job.target_dataset_id) : "");

  const template = templates.data?.find((t) => t.code === templateCode);
  const compatible = (datasets.data ?? []).filter((d) => d.template_code === templateCode);
  const columns = preview.data?.columns.map((c) => c.name) ?? [];

  const chooseTemplate = (code: string) => {
    setTemplateCode(code);
    setMapping(preview.data?.suggested_mappings[code] ?? {});
    setDatasetId("");
  };

  const validate = useMutation({
    mutationFn: () =>
      api<{ job: ImportJob; summary: ValidationSummary }>(`/imports/${job.id}/validate`, {
        body: {
          template_code: templateCode,
          mapping,
          sheet_name: sheet,
          decimal_separator: decimal,
          date_format: dateFormat,
          dataset_id: destination === "existing" && datasetId ? Number(datasetId) : null,
          dataset_name: destination === "new" ? datasetName : null,
        },
      }),
    onSuccess: (res) => onValidated(res.job, res.summary),
  });

  if (preview.isLoading || templates.isLoading) return <Spinner />;
  if (preview.error) return <ErrorBanner error={preview.error} />;
  const p = preview.data!;
  const missingRequired = template && !template.generic ? template.fields.filter((f) => f.required && !mapping[f.name]) : [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2"><FileSpreadsheet className="h-4 w-4" />{job.original_filename}</span>}
          description={`${p.total_rows.toLocaleString("es-MX")} renglones con datos · ${columns.length} columnas · SHA-256 ${job.file_sha256.slice(0, 12)}…`}
          actions={p.sheet_names.length > 1 && (
            <label className="flex items-center gap-2 text-xs text-muted">
              Hoja
              <Select value={sheet ?? ""} onChange={(e) => setSheet(e.target.value)} className="w-40">
                {p.sheet_names.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </label>
          )}
        />
        {p.same_file_committed_import_ids.length > 0 && (
          <div className="px-5 pt-4">
            <Notice tone="warn">
              Este mismo archivo ya se importó antes (importación #{p.same_file_committed_import_ids.join(", #")}). Los renglones
              repetidos se detectarán como duplicados si los agregas al mismo conjunto de datos.
            </Notice>
          </div>
        )}
        <CardBody>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Vista previa (primeros {p.rows.length} renglones)</div>
          <Table className="max-h-80 rounded border border-line">
            <thead>
              <tr>
                <Th>Fila</Th>
                {p.columns.map((c) => (
                  <Th key={c.name}>
                    <div>{c.name}</div>
                    <div className="font-normal normal-case text-slate-400">{c.kind}{c.missing ? ` · ${c.missing} vacíos` : ""}</div>
                  </Th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {p.rows.map((r) => (
                <tr key={r.row}>
                  <Td className="tabular text-muted">{r.row}</Td>
                  {r.values.map((v, i) => <Td key={i} className="whitespace-nowrap">{fmtCell(v)}</Td>)}
                </tr>
              ))}
            </tbody>
          </Table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="2. ¿Qué tipo de datos contiene?" description="La plantilla define los campos, sus tipos y los indicadores que se podrán calcular." />
        <CardBody>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3" role="radiogroup">
            {templates.data?.map((t) => (
              <button
                key={t.code}
                type="button"
                role="radio"
                aria-checked={templateCode === t.code}
                onClick={() => chooseTemplate(t.code)}
                className={clsx(
                  "rounded-lg border px-4 py-3 text-left text-sm",
                  templateCode === t.code ? "border-brand bg-teal-50 ring-1 ring-brand" : "border-line hover:bg-slate-50",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{t.name}</span>
                  <Badge>{label(AREA_LABELS, t.area)}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted">{t.description}</p>
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {template && (
        <Card>
          <CardHeader title="3. Relacionar columnas y validar"
            description={template.generic ? "La tabla genérica conserva todas las columnas tal como vienen." : "Se sugirieron columnas por nombre; revisa cada campo. Los campos con * son obligatorios."} />
          <CardBody className="space-y-5">
            {!template.generic && (
              <div className="grid gap-x-6 gap-y-3 md:grid-cols-2">
                {template.fields.map((f) => (
                  <Field key={f.name} label={f.label} required={f.required} htmlFor={`map-${f.name}`}
                    hint={[f.description, f.choices.length ? `Valores: ${f.choices.join(", ")}` : ""].filter(Boolean).join(" ")}>
                    <Select id={`map-${f.name}`} value={mapping[f.name] ?? ""}
                      onChange={(e) => setMapping({ ...mapping, [f.name]: e.target.value })}>
                      <option value="">— Sin columna —</option>
                      {columns.map((c) => <option key={c} value={c}>{c}</option>)}
                    </Select>
                  </Field>
                ))}
              </div>
            )}
            <div className="grid gap-4 border-t border-line pt-4 md:grid-cols-2">
              <Field label="Separador decimal" htmlFor="decimal" hint="Cómo se escriben los números en el archivo.">
                <Select id="decimal" value={decimal ?? "."} onChange={(e) => setDecimal(e.target.value)}>
                  <option value=".">Punto: 1,234.50</option>
                  <option value=",">Coma: 1.234,50</option>
                </Select>
              </Field>
              <Field label="Formato de fecha" htmlFor="datefmt" hint="Solo aplica a fechas escritas como texto; las fechas de Excel se leen directamente.">
                <Select id="datefmt" value={dateFormat ?? "dayfirst"} onChange={(e) => setDateFormat(e.target.value)}>
                  <option value="dayfirst">Día/mes/año (31/12/2024)</option>
                  <option value="monthfirst">Mes/día/año (12/31/2024)</option>
                </Select>
              </Field>
            </div>
            <fieldset className="space-y-3 border-t border-line pt-4">
              <legend className="text-sm font-medium">Destino</legend>
              <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input type="radio" checked={destination === "new"} onChange={() => setDestination("new")} /> Nuevo conjunto de datos
                </label>
                <label className={clsx("flex items-center gap-2", !compatible.length && "text-muted")}>
                  <input type="radio" disabled={!compatible.length} checked={destination === "existing"} onChange={() => setDestination("existing")} />
                  Agregar a un conjunto existente {compatible.length ? "" : "(no hay compatibles)"}
                </label>
              </div>
              {destination === "new" ? (
                <Field label="Nombre del conjunto" htmlFor="dsname" hint="Ej. «Producción planta norte 2024». Debe ser único.">
                  <Input id="dsname" value={datasetName} onChange={(e) => setDatasetName(e.target.value)} />
                </Field>
              ) : (
                <Field label="Conjunto existente" htmlFor="dsid" hint="Los renglones ya existentes se detectan como duplicados.">
                  <Select id="dsid" value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
                    <option value="">Selecciona…</option>
                    {compatible.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.row_count} registros)</option>)}
                  </Select>
                </Field>
              )}
            </fieldset>
            <ErrorBanner error={validate.error} />
            <div className="flex flex-wrap items-center justify-end gap-3">
              {missingRequired.length > 0 && (
                <span className="text-xs text-amber-700">Falta asignar: {missingRequired.map((f) => f.label).join(", ")}</span>
              )}
              <Button loading={validate.isPending} disabled={missingRequired.length > 0} onClick={() => validate.mutate()}>
                Validar todos los renglones
              </Button>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

function SummaryStep({ job, summary, onCommitted }: { job: ImportJob; summary: ValidationSummary; onCommitted: (job: ImportJob, run: AnalysisRun | null) => void }) {
  const [skipInvalid, setSkipInvalid] = useState(true);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const commit = useMutation({
    mutationFn: () => api<{ job: ImportJob; analysis_run: AnalysisRun | null }>(`/imports/${job.id}/commit`, {
      body: { skip_invalid: skipInvalid, skip_duplicates: skipDuplicates },
    }),
    onSuccess: (r) => onCommitted(r.job, r.analysis_run),
  });
  const toImport =
    (skipDuplicates ? summary.importable_rows_without_duplicates : summary.valid_rows);
  const missing = Object.entries(summary.missing_by_field).filter(([, v]) => v > 0);
  return (
    <Card>
      <CardHeader title="4. Resultado de la validación" description={`Duplicados detectados con base en: ${summary.duplicate_basis.join(" + ")}.`} />
      <CardBody className="space-y-5">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Renglones" value={summary.total_rows} />
          <Stat label="Válidos" value={summary.valid_rows} />
          <Stat label="Con errores" value={summary.invalid_rows} tone={summary.invalid_rows ? "bad" : "default"} />
          <Stat label="Duplicados" value={summary.duplicate_rows} tone={summary.duplicate_rows ? "warn" : "default"} />
        </div>
        {summary.errors.length > 0 && (
          <div>
            <div className="mb-2 text-sm font-medium">Errores por renglón {summary.errors_truncated && "(se muestran los primeros 500)"}</div>
            <Table className="max-h-72 rounded border border-line">
              <thead><tr><Th>Fila</Th><Th>Campo</Th><Th>Columna</Th><Th>Valor</Th><Th>Problema y cómo corregirlo</Th></tr></thead>
              <tbody className="divide-y divide-line">
                {summary.errors.slice(0, 200).map((e, i) => (
                  <tr key={i}>
                    <Td className="tabular">{e.row}</Td><Td>{e.field_label}</Td><Td>{e.column ?? "—"}</Td>
                    <Td className="font-mono text-xs">{fmtCell(e.value)}</Td><Td>{e.message}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
        {summary.duplicates_in_file.length > 0 && (
          <p className="text-sm text-muted">
            Duplicados dentro del archivo: {summary.duplicates_in_file.slice(0, 20).map((d) => `fila ${d.row} = fila ${d.duplicate_of_row}`).join("; ")}
            {summary.duplicates_in_file.length > 20 ? "…" : ""}
          </p>
        )}
        {summary.duplicates_existing_rows.length > 0 && (
          <p className="text-sm text-muted">{summary.duplicates_existing_rows.length} renglones ya existen en el conjunto de datos destino.</p>
        )}
        {missing.length > 0 && (
          <p className="text-sm text-muted">Valores vacíos por campo: {missing.map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
        )}
        {summary.unmapped_columns.length > 0 && (
          <p className="text-sm text-muted">Columnas no utilizadas: {summary.unmapped_columns.join(", ")}</p>
        )}
        <div className="flex flex-col gap-2 border-t border-line pt-4">
          <Checkbox label="Omitir renglones con errores" checked={skipInvalid} onChange={(e) => setSkipInvalid(e.target.checked)} />
          <Checkbox label="Omitir duplicados" checked={skipDuplicates} onChange={(e) => setSkipDuplicates(e.target.checked)} />
        </div>
        <ErrorBanner error={commit.error} />
        <div className="flex flex-wrap items-center justify-end gap-3">
          <span className="text-sm text-muted">Se importarán <strong className="text-ink">{toImport}</strong> renglones en «{job.target_dataset_name}».</span>
          <Button loading={commit.isPending} disabled={toImport === 0 || (!skipInvalid && summary.invalid_rows > 0)} onClick={() => commit.mutate()}>
            Confirmar importación
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function ResultStep({ job, run }: { job: ImportJob; run: AnalysisRun | null }) {
  return (
    <Card>
      <CardBody className="space-y-4">
        <div className="flex items-center gap-2 text-emerald-700">
          <CheckCircle2 className="h-5 w-5" aria-hidden />
          <span className="font-medium">Importación confirmada: {job.imported_rows} renglones en «{job.target_dataset_name}».</span>
        </div>
        {run ? (
          run.status === "completed" ? (
            <p className="text-sm text-muted">
              Análisis #{run.id}: {run.summary.kpis_computed ?? 0} indicadores calculados, {run.summary.kpis_insufficient ?? 0} sin datos suficientes,
              {" "}{run.summary.findings_created ?? 0} hallazgos nuevos y {run.summary.findings_updated ?? 0} actualizados.
            </p>
          ) : (
            <Notice tone="warn">El análisis automático falló ({run.error_message}). Los datos quedaron importados; puedes reintentar el análisis desde el conjunto de datos.</Notice>
          )
        ) : (
          <p className="text-sm text-muted">El análisis no se ejecutó automáticamente.</p>
        )}
        <div className="flex flex-wrap gap-2">
          <ButtonLink href={`/datasets/${job.target_dataset_id}`}>Ver conjunto de datos</ButtonLink>
          <ButtonLink href="/findings" variant="secondary">Ver hallazgos</ButtonLink>
          <ButtonLink href="/dashboard" variant="secondary">Ir al panel</ButtonLink>
          <ButtonLink href="/imports/new" variant="ghost" external>Importar otro archivo</ButtonLink>
        </div>
      </CardBody>
    </Card>
  );
}

function Wizard() {
  const params = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();
  const jobParam = params.get("job");
  const existing = useQuery({
    queryKey: ["import", jobParam],
    queryFn: () => api<ImportJob>(`/imports/${jobParam}`),
    enabled: !!jobParam,
  });
  const [job, setJob] = useState<ImportJob | null>(null);
  const [summary, setSummary] = useState<ValidationSummary | null>(null);
  const [run, setRun] = useState<AnalysisRun | null>(null);

  useEffect(() => {
    if (existing.data && !job) {
      setJob(existing.data);
      if (existing.data.status === "validated" && "valid_rows" in existing.data.validation_summary) {
        setSummary(existing.data.validation_summary as ValidationSummary);
      }
    }
  }, [existing.data, job]);

  const step = useMemo(() => {
    if (!job) return 0;
    if (job.status === "committed") return 3;
    if (summary) return 2;
    return 1;
  }, [job, summary]);

  if (jobParam && existing.isLoading) return <Spinner />;
  if (existing.error) return <ErrorBanner error={existing.error} />;

  return (
    <>
      <Stepper current={step} />
      {!job && (
        <UploadStep onUploaded={(j) => { setJob(j); router.replace(`/imports/new?job=${j.id}`); }} />
      )}
      {job && job.status !== "committed" && job.status !== "reverted" && (
        <div className="space-y-4">
          <MappingStep key={job.id} job={job} onValidated={(j, s) => { setJob(j); setSummary(s); }} />
          {summary && job.status === "validated" && (
            <SummaryStep job={job} summary={summary} onCommitted={(j, r) => { setJob(j); setRun(r); qc.invalidateQueries(); }} />
          )}
        </div>
      )}
      {job && job.status === "committed" && <ResultStep job={job} run={run} />}
      {job && job.status === "reverted" && (
        <Notice tone="warn">Esta importación fue revertida. <Link className="underline" href={`/imports/${job.id}`}>Ver detalle</Link></Notice>
      )}
    </>
  );
}

export default function NewImportPage() {
  return (
    <>
      <PageHeader title="Importar datos"
        description="Carga un archivo, relaciona sus columnas con una plantilla, revisa los errores y confirma. Nada se guarda en los datos de análisis hasta que confirmes." />
      <Suspense fallback={<Spinner />}>
        <Wizard />
      </Suspense>
    </>
  );
}
