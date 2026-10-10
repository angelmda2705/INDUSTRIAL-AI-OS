"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PasswordForm } from "@/components/password-form";
import { ErrorBanner, Notice } from "@/components/ui/feedback";
import { api } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    // The token travels in the URL fragment so it is never sent to servers or written to access logs.
    const match = window.location.hash.match(/token=([^&]+)/);
    setToken(match ? decodeURIComponent(match[1]) : "");
    if (match) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  return (
    <>
      <h1 className="text-xl font-semibold">Restablecer contraseña</h1>
      <div className="mt-6 space-y-4">
        <ErrorBanner error={error} />
        {done ? (
          <Notice>
            Contraseña restablecida. Por seguridad se cerraron todas tus sesiones.{" "}
            <Link href="/login" className="font-medium underline">
              Inicia sesión
            </Link>
            .
          </Notice>
        ) : token === "" ? (
          <Notice tone="warn">
            El enlace no contiene un token válido.{" "}
            <Link href="/forgot-password" className="font-medium underline">
              Solicita uno nuevo
            </Link>
            .
          </Notice>
        ) : token ? (
          <PasswordForm
            submitLabel="Guardar nueva contraseña"
            onSubmit={async (v) => {
              setError(null);
              try {
                await api("/auth/password-reset/confirm", { body: { token, new_password: v.password } });
                setDone(true);
              } catch (e) {
                setError(e);
              }
            }}
          />
        ) : null}
      </div>
    </>
  );
}
