import { AlertTriangle, Info, Inbox } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api";

export function Spinner({ label = "Cargando…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-r-transparent" aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({ title, description, actions, icon }: { title: string; description?: ReactNode; actions?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 text-slate-400">{icon ?? <Inbox className="h-8 w-8" aria-hidden />}</div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {description && <div className="mt-1 max-w-lg text-sm text-muted">{description}</div>}
      {actions && <div className="mt-4 flex flex-wrap justify-center gap-2">{actions}</div>}
    </div>
  );
}

/** Explains an error and how to proceed; shows the request id for support. */
export function ErrorBanner({ error, title }: { error: unknown; title?: string }) {
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  const message = e?.message ?? (error instanceof Error ? error.message : "Ocurrió un error inesperado.");
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div className="min-w-0">
          <p className="font-medium">{title ?? message}</p>
          {title && <p>{message}</p>}
          {e && e.fieldErrors.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {e.fieldErrors.map((f, i) => (
                <li key={i}>
                  {f.field ? <span className="font-medium">{f.field}: </span> : null}
                  {f.message}
                </li>
              ))}
            </ul>
          )}
          {e?.requestId && <p className="mt-1 text-xs text-red-700">Identificador de solicitud: {e.requestId}</p>}
        </div>
      </div>
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "demo"; children: ReactNode }) {
  const styles = {
    info: "border-sky-200 bg-sky-50 text-sky-900",
    warn: "border-amber-200 bg-amber-50 text-amber-900",
    demo: "border-violet-200 bg-violet-50 text-violet-900",
  }[tone];
  return (
    <div className={`flex items-start gap-2 rounded-md border px-4 py-3 text-sm ${styles}`}>
      <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
