"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PasswordForm } from "@/components/password-form";
import { ErrorBanner, Notice } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { useMe } from "@/lib/session";

export default function ChangePasswordPage() {
  const { data: me } = useMe();
  const router = useRouter();
  const qc = useQueryClient();
  const [error, setError] = useState<unknown>(null);

  return (
    <>
      <h1 className="text-xl font-semibold">Cambiar contraseña</h1>
      <div className="mt-4 space-y-4">
        {me?.user.must_change_password && (
          <Notice tone="warn">Tu cuenta usa una contraseña temporal. Debes cambiarla antes de continuar.</Notice>
        )}
        <ErrorBanner error={error} />
        <PasswordForm
          askCurrent
          submitLabel="Cambiar contraseña"
          onSubmit={async (v) => {
            setError(null);
            try {
              await api("/auth/change-password", { body: { current_password: v.current ?? "", new_password: v.password } });
              await qc.invalidateQueries({ queryKey: ["me"] });
              router.replace("/dashboard");
            } catch (e) {
              setError(e);
            }
          }}
        />
        {!me?.user.must_change_password && (
          <Link href="/dashboard" className="inline-block text-sm text-brand hover:underline">
            Volver al panel
          </Link>
        )}
      </div>
    </>
  );
}
