"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PASSWORD_HINT } from "@/components/password-form";
import { Button } from "@/components/ui/button";
import { ErrorBanner, Notice, Spinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";
import type { Me } from "@/lib/types";

export default function SignupPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const branding = useQuery({ queryKey: ["branding"], queryFn: () => api<{ allow_self_signup: boolean }>("/system/branding") });
  const [form, setForm] = useState({ organization_name: "", display_name: "", email: "", password: "" });
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  if (branding.isLoading) return <Spinner />;
  if (!branding.data?.allow_self_signup) {
    return (
      <Notice tone="warn">
        El registro de organizaciones está deshabilitado. Contacta al administrador de la plataforma.{" "}
        <Link href="/login" className="underline">
          Volver
        </Link>
      </Notice>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api<{ me: Me }>("/auth/signup", { body: form });
      qc.setQueryData(["me"], res.me);
      router.replace("/dashboard");
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <h1 className="text-xl font-semibold">Registrar empresa</h1>
      <p className="mt-1 text-sm text-muted">Crearás la organización y su primer usuario administrador.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <ErrorBanner error={error} />
        <Field label="Nombre de la empresa" htmlFor="org" required>
          <Input id="org" required value={form.organization_name} onChange={set("organization_name")} />
        </Field>
        <Field label="Tu nombre" htmlFor="name" required>
          <Input id="name" required value={form.display_name} onChange={set("display_name")} />
        </Field>
        <Field label="Correo electrónico" htmlFor="email" required>
          <Input id="email" type="email" required value={form.email} onChange={set("email")} />
        </Field>
        <Field label="Contraseña" htmlFor="password" hint={PASSWORD_HINT} required>
          <Input id="password" type="password" autoComplete="new-password" required value={form.password} onChange={set("password")} />
        </Field>
        <Button type="submit" className="w-full" loading={loading}>
          Crear organización
        </Button>
      </form>
      <Link href="/login" className="mt-6 inline-block text-sm text-brand hover:underline">
        Ya tengo cuenta
      </Link>
    </>
  );
}
