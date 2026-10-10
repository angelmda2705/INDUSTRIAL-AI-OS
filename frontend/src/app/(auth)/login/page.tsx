"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";
import type { Me } from "@/lib/types";

const schema = z.object({
  email: z.string().trim().email("Escribe un correo válido."),
  password: z.string().min(1, "Escribe tu contraseña."),
});
type Form = z.infer<typeof schema>;

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [error, setError] = useState<unknown>(null);
  const branding = useQuery({
    queryKey: ["branding"],
    queryFn: () => api<{ allow_self_signup: boolean }>("/system/branding"),
  });
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: Form) => {
    setError(null);
    try {
      const res = await api<{ me: Me }>("/auth/login", { body: values });
      qc.setQueryData(["me"], res.me);
      const next = params.get("next");
      if (res.me.user.must_change_password) router.replace("/change-password");
      else router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
    } catch (e) {
      setError(e);
    }
  };

  return (
    <>
      <h1 className="text-xl font-semibold">Iniciar sesión</h1>
      <p className="mt-1 text-sm text-muted">Usa el correo con el que te registró tu organización.</p>
      <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
        <ErrorBanner error={error} />
        <Field label="Correo electrónico" htmlFor="email" error={formState.errors.email?.message}>
          <Input id="email" type="email" autoComplete="username" {...register("email")} />
        </Field>
        <Field label="Contraseña" htmlFor="password" error={formState.errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
        </Field>
        <Button type="submit" className="w-full" loading={formState.isSubmitting}>
          Entrar
        </Button>
      </form>
      <div className="mt-6 flex justify-between text-sm">
        <Link href="/forgot-password" className="text-brand hover:underline">
          ¿Olvidaste tu contraseña?
        </Link>
        {branding.data?.allow_self_signup && (
          <Link href="/signup" className="text-brand hover:underline">
            Registrar empresa
          </Link>
        )}
      </div>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
