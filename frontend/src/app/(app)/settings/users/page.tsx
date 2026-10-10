"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus } from "lucide-react";
import { useState } from "react";

import { PASSWORD_HINT } from "@/components/password-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, PageHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorBanner, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/field";
import { Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { useCan, useMe } from "@/lib/session";
import type { Member } from "@/lib/types";

type Role = { role: string; label: string; permissions: string[] };

export default function UsersPage() {
  const can = useCan();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const members = useQuery({ queryKey: ["members"], queryFn: () => api<Member[]>("/organization/members") });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/organization/roles") });
  const [adding, setAdding] = useState(false);
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) => api<Member>(`/organization/members/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["members"] }),
  });
  const manage = can("users.manage");
  const assignable = (roles.data ?? []).filter((r) => r.role !== "org_admin" || me?.role === "org_admin");

  return (
    <>
      <PageHeader title="Usuarios" description="Solo se almacena el correo y un nombre para mostrar. Cada usuario ve únicamente los datos de las organizaciones a las que pertenece."
        actions={manage && <Button onClick={() => setAdding(true)}><UserPlus className="h-4 w-4" />Agregar usuario</Button>} />
      <ErrorBanner error={members.error ?? update.error} />
      <Card className="mb-4">
        {members.isLoading ? <Spinner /> : (
          <Table>
            <thead><tr><Th>Usuario</Th><Th>Rol</Th><Th>Estado</Th><Th>Último acceso</Th></tr></thead>
            <tbody className="divide-y divide-line">
              {members.data?.map((m) => {
                const self = m.user_id === me?.user.id;
                return (
                  <tr key={m.id}>
                    <Td><div className="font-medium">{m.display_name}{self && <span className="ml-1 text-xs text-muted">(tú)</span>}</div><div className="text-xs text-muted">{m.email}</div></Td>
                    <Td>
                      {manage && !self ? (
                        <Select aria-label={`Rol de ${m.email}`} value={m.role} className="w-56" onChange={(e) => update.mutate({ id: m.id, body: { role: e.target.value } })}>
                          {(m.role === "org_admin" && me?.role !== "org_admin" ? roles.data ?? [] : assignable).map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}
                        </Select>
                      ) : m.role_label}
                    </Td>
                    <Td>
                      <div className="flex flex-wrap items-center gap-2">
                        {m.is_active ? <Badge tone="green">Activo</Badge> : <Badge>Inactivo</Badge>}
                        {m.must_change_password && <Badge tone="amber">Contraseña temporal</Badge>}
                        {manage && !self && (
                          <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: m.id, body: { is_active: !m.is_active } })}>
                            {m.is_active ? "Desactivar" : "Activar"}
                          </Button>
                        )}
                      </div>
                    </Td>
                    <Td className="text-muted">{fmtDateTime(m.last_login_at)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
      <Card>
        <CardHeader title="Roles y permisos" description="Los permisos se verifican en el servidor en cada operación." />
        <CardBody>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {roles.data?.map((r) => (
              <details key={r.role} className="rounded-md border border-line px-3 py-2 text-sm">
                <summary className="cursor-pointer font-medium">{r.label}</summary>
                <ul className="mt-2 flex flex-wrap gap-1">{r.permissions.map((p) => <li key={p}><Badge>{p}</Badge></li>)}</ul>
              </details>
            ))}
          </div>
        </CardBody>
      </Card>
      {adding && <AddUserDialog roles={assignable} onClose={() => setAdding(false)} />}
    </>
  );
}

function AddUserDialog({ roles, onClose }: { roles: Role[]; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: "", display_name: "", role: "analyst", initial_password: "" });
  const add = useMutation({
    mutationFn: () => api("/organization/members", { body: { ...form, initial_password: form.initial_password || null } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["members"] }); onClose(); },
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <Dialog open onClose={onClose} title="Agregar usuario"
      footer={<><Button variant="secondary" onClick={onClose}>Cancelar</Button><Button loading={add.isPending} onClick={() => add.mutate()}>Agregar</Button></>}>
      <div className="space-y-3">
        <ErrorBanner error={add.error} />
        <Field label="Correo" htmlFor="ne" required><Input id="ne" type="email" value={form.email} onChange={set("email")} /></Field>
        <Field label="Nombre para mostrar" htmlFor="nn" required><Input id="nn" value={form.display_name} onChange={set("display_name")} /></Field>
        <Field label="Rol" htmlFor="nr">
          <Select id="nr" value={form.role} onChange={set("role")}>{roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}</Select>
        </Field>
        <Field label="Contraseña temporal" htmlFor="np" hint={`Solo para usuarios nuevos; deberán cambiarla al entrar. ${PASSWORD_HINT} Compártela por un canal seguro.`}>
          <Input id="np" type="password" autoComplete="new-password" value={form.initial_password} onChange={set("initial_password")} />
        </Field>
      </div>
    </Dialog>
  );
}
