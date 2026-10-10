"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { fmtKpi, fmtMonth, fmtNumber } from "@/lib/format";

type Point = { period: string; value: number | null };

/** Monthly series with an optional target line and a plain-language reading of the change. */
export function TrendChart({ points, unit, target, direction, currency, height = 180 }: {
  points: Point[];
  unit: string;
  target?: number | null;
  direction?: string;
  currency?: string;
  height?: number;
}) {
  const data = points.filter((p) => p.value !== null).map((p) => ({ ...p, label: fmtMonth(p.period) }));
  return (
    <div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} width={48}
              tickFormatter={(v: number) => fmtNumber(v, 1)} domain={["auto", "auto"]} />
            <Tooltip
              formatter={(v) => [fmtKpi(Number(v), unit, currency), "Valor"]}
              labelStyle={{ fontSize: 12 }}
              contentStyle={{ fontSize: 12, borderRadius: 6 }}
            />
            {target !== null && target !== undefined && (
              <ReferenceLine y={target} stroke="#b45309" strokeDasharray="4 4" label={{ value: "Objetivo", fontSize: 10, fill: "#b45309", position: "insideTopRight" }} />
            )}
            <Line type="monotone" dataKey="value" stroke="var(--brand)" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-muted">{describe(data, unit, direction, currency)}</p>
    </div>
  );
}

function describe(data: Point[], unit: string, direction?: string, currency?: string): string {
  if (data.length < 2) return "Se necesitan al menos dos periodos para comparar.";
  const first = data[0].value as number;
  const last = data[data.length - 1].value as number;
  const diff = last - first;
  if (Math.abs(diff) < 1e-9) return `Sin cambio entre el primer y el último mes (${fmtKpi(last, unit, currency)}).`;
  const better = direction === "higher_is_better" ? diff > 0 : direction === "lower_is_better" ? diff < 0 : null;
  const verdict = better === null ? "" : better ? " — evolución favorable" : " — evolución desfavorable";
  return `Del primer al último mes pasó de ${fmtKpi(first, unit, currency)} a ${fmtKpi(last, unit, currency)}${verdict}. Una comparación de dos puntos no prueba una tendencia; revisa los hallazgos de tendencia para el análisis estadístico.`;
}
