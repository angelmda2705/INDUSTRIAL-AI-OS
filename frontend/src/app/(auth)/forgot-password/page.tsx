"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ErrorBanner, Notice } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api<{ message: string }>("/auth/password-reset/request", { body: { email } });
      setSent(res.message);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h1 className="text-xl font-semibold">Recuperar acceso</h1>
      <p className="mt-1 text-sm text-muted">Te enviaremos un enlace de un solo uso, válido por tiempo limitado.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <ErrorBanner error={error} />
        {sent ? (
          <Notice>{sent}</Notice>
        ) : (
          <>
            <Field label="Correo electrónico" htmlFor="email">
              <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Button type="submit" className="w-full" loading={loading}>
              Enviar enlace
            </Button>
          </>
        )}
      </form>
      <Link href="/login" className="mt-6 inline-block text-sm text-brand hover:underline">
        Volver a iniciar sesión
      </Link>
    </>
  );
}
