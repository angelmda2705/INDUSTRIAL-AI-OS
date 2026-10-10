import type { ReactNode } from "react";

import { brand } from "@/lib/brand";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_minmax(420px,520px)]">
      <div className="hidden flex-col justify-between bg-slate-900 p-10 text-slate-200 lg:flex">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/logo.svg" alt="" className="h-9 w-9" />
          <div>
            <div className="font-semibold text-white">{brand.name}</div>
            <div className="text-sm text-slate-400">{brand.tagline}</div>
          </div>
        </div>
        <div className="max-w-md space-y-4">
          <p className="text-2xl font-semibold leading-snug text-white">De los datos al diagnóstico, con evidencia verificable.</p>
          <ul className="space-y-2 text-sm text-slate-300">
            <li>• Importa tus archivos de Excel o CSV y valida su calidad.</li>
            <li>• Indicadores con fórmula, supuestos y fuente documentados.</li>
            <li>• Hallazgos que distinguen hechos, anomalías e hipótesis.</li>
          </ul>
        </div>
        <p className="text-xs text-slate-500">Los datos de cada empresa están aislados y cada acción relevante queda auditada.</p>
      </div>
      <div className="flex items-center justify-center bg-panel px-6 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
