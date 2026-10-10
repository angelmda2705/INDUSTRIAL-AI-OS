"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, PageHeader } from "@/components/ui/card";
import { ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/field";
import { api } from "@/lib/api";
import { useCan } from "@/lib/session";

type Org = { id: number; name: string; slug: string; plan: string | null; modules: string[]; limits: Record<string, number>; settings: Record<string, unknown> };

const LIMIT_LABELS: Record<string, string> = {
  max_users: "Usuarios activos",
  max_imports_per_month: "Importaciones por mes",
  max_rows_per_import: "Renglones por importación",
};

export default function OrganizationSettingsPage() {
  const can = useCan();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["organization"], queryFn: () => api<Org>("/organization") });
  const [name, setName] = useState("");
  const [s, setS] = useState<Record<string, unknown>>({});
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (q.data) { setName(q.data.name); setS(q.data.settings); } }, [q.data]);
  const save = useMutation({
    mutationFn: () => {
      const thresholds = String(s.inventory_abc_thresholds ?? "0.8,0.95").split(",").map(Number);
      return api("/organization", {
        method: "PATCH",
        body: {
          name,
          settings: {
            currency: String(s.currency ?? "").toUpperCase(),
            timezone: s.timezone,
            date_format: s.date_format,
            decimal_separator: s.decimal_separator,
            inventory_service_level_z: Number(s.inventory_service_level_z),
            inventory_abc_thresholds: thresholds,
            inventory_obsolete_days: Number(s.inventory_obsolete_days),
            anomaly_robust_z_threshold: Number(s.anomaly_robust_z_threshold),
            preventive_tolerance_days: Number(s.preventive_tolerance_days),
          },
        },
      });
    },
    onSuccess: () => { setSaved(true); qc.invalidateQueries(); },
  });
  if (q.isLoading) return <Spinner />;
  if (q.error || !q.data) return <ErrorBanner error={q.error} />;
  const editable = can("org.settings.manage");
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setSaved(false); setS({ ...s, [k]: e.target.value }); };

  return (
    <>
      <PageHeader title="Organización" description="Datos generales y parámetros de análisis. Los cambios en parámetros afectan los siguientes análisis y quedan auditados." />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Configuración" />
          <CardBody className="space-y-4">
            {!editable && <Notice>Tu rol permite consultar la configuración, no modificarla.</Notice>}
            <ErrorBanner error={save.error} />
            {saved && <Notice>Cambios guardados. Vuelve a analizar los conjuntos de datos para aplicar nuevos parámetros.</Notice>}
            <fieldset disabled={!editable} className="grid gap-4 md:grid-cols-2">
              <Field label="Nombre" htmlFor="name"><Input id="name" value={name} onChange={(e) => setName(e.target.value)} /></Field>
              <Field label="Moneda (ISO 4217)" htmlFor="cur" hint="Ej. MXN, USD. Se usa en impactos y reportes."><Input id="cur" maxLength={3} value={String(s.currency ?? "")} onChange={set("currency")} /></Field>
              <Field label="Zona horaria" htmlFor="tz" hint="Las fechas importadas se interpretan en esta zona."><Input id="tz" value={String(s.timezone ?? "")} onChange={set("timezone")} /></Field>
              <Field label="Formato de fecha predeterminado" htmlFor="df">
                <Select id="df" value={String(s.date_format ?? "dayfirst")} onChange={set("date_format")}>
                  <option value="dayfirst">Día/mes/año</option><option value="monthfirst">Mes/día/año</option>
                </Select>
              </Field>
              <Field label="Separador decimal predeterminado" htmlFor="ds">
                <Select id="ds" value={String(s.decimal_separator ?? ".")} onChange={set("decimal_separator")}>
                  <option value=".">Punto</option><option value=",">Coma</option>
                </Select>
              </Field>
              <Field label="Nivel de servicio (z) para stock de seguridad" htmlFor="z" hint="1.645 ≈ 95 % de ciclo bajo demanda normal.">
                <Input id="z" type="number" step="0.001" value={String(s.inventory_service_level_z ?? "")} onChange={set("inventory_service_level_z")} />
              </Field>
              <Field label="Umbrales ABC (acumulado)" htmlFor="abc" hint="Dos proporciones separadas por coma, ej. 0.8,0.95.">
                <Input id="abc" value={Array.isArray(s.inventory_abc_thresholds) ? (s.inventory_abc_thresholds as number[]).join(",") : String(s.inventory_abc_thresholds ?? "")} onChange={set("inventory_abc_thresholds")} />
              </Field>
              <Field label="Días sin movimiento para revisar obsolescencia" htmlFor="obs">
                <Input id="obs" type="number" value={String(s.inventory_obsolete_days ?? "")} onChange={set("inventory_obsolete_days")} />
              </Field>
              <Field label="Umbral de anomalía (puntaje z robusto)" htmlFor="rz" hint="Valores mayores reportan menos anomalías.">
                <Input id="rz" type="number" step="0.1" value={String(s.anomaly_robust_z_threshold ?? "")} onChange={set("anomaly_robust_z_threshold")} />
              </Field>
              <Field label="Tolerancia del preventivo (días)" htmlFor="pt">
                <Input id="pt" type="number" value={String(s.preventive_tolerance_days ?? "")} onChange={set("preventive_tolerance_days")} />
              </Field>
            </fieldset>
            {editable && <div className="flex justify-end"><Button loading={save.isPending} onClick={() => save.mutate()}>Guardar cambios</Button></div>}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Plan y módulos" />
          <CardBody className="space-y-3 text-sm">
            <p>Plan: <strong>{q.data.plan ?? "—"}</strong></p>
            <div className="flex flex-wrap gap-1">{q.data.modules.map((m) => <Badge key={m} tone="brand">{m}</Badge>)}</div>
            <ul className="space-y-1">
              {Object.entries(q.data.limits).map(([k, v]) => <li key={k} className="flex justify-between"><span className="text-muted">{LIMIT_LABELS[k] ?? k}</span><span className="tabular">{v.toLocaleString("es-MX")}</span></li>)}
            </ul>
            <p className="text-xs text-muted">Los cambios de plan los realiza el administrador de la plataforma.</p>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
