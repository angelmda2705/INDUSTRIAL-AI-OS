"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PASSWORD_HINT } from "@/components/password-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, PageHeader } from "@/components/ui/card";
import { ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/field";
import { Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { useMe } from "@/lib/session";

type OrgRow = { id: number; name: string; slug: string; plan: string | null; modules: string[]; is_active: boolean; active_users: number; created_at: string };
type Plan = { code: string; name: string; limits: Record<string, number>; modules: string[] };

export default function PlatformPage() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const orgs = useQuery({ queryKey: ["platform-orgs"], queryFn: () => api<OrgRow[]>("/platform/organizations"), enabled: !!me?.user.is_platform_admin });
  const plans = useQuery({ queryKey: ["plans"], queryFn: () => api<Plan[]>("/platform/plans"), enabled: !!me?.user.is_platform_admin });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) => api(`/platform/organizations/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform-orgs"] }),
  });
  const [form, setForm] = useState({ name: "", admin_email: "", admin_name: "", admin_password: "", plan_code: "starter" });
  const create = useMutation({
    mutationFn: () => api("/platform/organizations", { body: { ...form, admin_password: form.admin_password || null } }),
    onSuccess: () => { setForm({ name: "", admin_email: "", admin_name: "", admin_password: "", plan_code: "starter" }); qc.invalidateQueries({ queryKey: ["platform-orgs"] }); },
  });

  if (!me?.user.is_platform_admin) return <Notice tone="warn">Esta sección es solo para administradores de la plataforma.</Notice>;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <PageHeader title="Administración de plataforma" description="Organizaciones cliente, planes y estado. Esta vista no da acceso a los datos operativos de ningún cliente." />
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Organizaciones" />
          <ErrorBanner error={orgs.error ?? update.error} />
          {orgs.isLoading ? <Spinner /> : (
            <Table>
              <thead><tr><Th>Organización</Th><Th>Plan</Th><Th className="text-right">Usuarios</Th><Th>Alta</Th><Th>Estado</Th></tr></thead>
              <tbody className="divide-y divide-line">
                {orgs.data?.map((o) => (
                  <tr key={o.id}>
                    <Td><div className="font-medium">{o.name}</div><div className="text-xs text-muted">{o.slug}</div></Td>
                    <Td>
                      <Select aria-label={`Plan de ${o.name}`} className="w-40" value={o.plan ?? ""} onChange={(e) => update.mutate({ id: o.id, body: { plan_code: e.target.value } })}>
                        {plans.data?.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
                      </Select>
                    </Td>
                    <Td className="tabular text-right">{o.active_users}</Td>
                    <Td className="text-muted">{fmtDate(o.created_at)}</Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        {o.is_active ? <Badge tone="green">Activa</Badge> : <Badge tone="red">Suspendida</Badge>}
                        <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: o.id, body: { is_active: !o.is_active } })}>{o.is_active ? "Suspender" : "Reactivar"}</Button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
        <Card>
          <CardHeader title="Nueva organización" />
          <CardBody className="space-y-3">
            <ErrorBanner error={create.error} />
            <Field label="Nombre" htmlFor="on" required><Input id="on" value={form.name} onChange={set("name")} /></Field>
            <Field label="Plan" htmlFor="op"><Select id="op" value={form.plan_code} onChange={set("plan_code")}>{plans.data?.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</Select></Field>
            <Field label="Correo del administrador" htmlFor="oe" required><Input id="oe" type="email" value={form.admin_email} onChange={set("admin_email")} /></Field>
            <Field label="Nombre del administrador" htmlFor="oa" required><Input id="oa" value={form.admin_name} onChange={set("admin_name")} /></Field>
            <Field label="Contraseña inicial" htmlFor="ow" hint={`Solo si el usuario no existe. ${PASSWORD_HINT}`}><Input id="ow" type="password" value={form.admin_password} onChange={set("admin_password")} /></Field>
            <Button className="w-full" loading={create.isPending} onClick={() => create.mutate()}>Crear organización</Button>
          </CardBody>
        </Card>
      </div>
    </>
  );
}
