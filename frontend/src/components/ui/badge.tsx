import clsx from "clsx";
import type { ReactNode } from "react";

import { IMPORT_STATUS_LABELS, NATURE_HELP, NATURE_LABELS, PRIORITY_LABELS, STATUS_LABELS, label } from "@/lib/labels";

type Tone = "gray" | "green" | "amber" | "red" | "blue" | "violet" | "brand";

const tones: Record<Tone, string> = {
  gray: "bg-slate-100 text-slate-700 ring-slate-200",
  green: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  red: "bg-red-50 text-red-800 ring-red-200",
  blue: "bg-sky-50 text-sky-800 ring-sky-200",
  violet: "bg-violet-50 text-violet-800 ring-violet-200",
  brand: "bg-teal-50 text-teal-800 ring-teal-200",
};

export function Badge({ tone = "gray", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={clsx("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset", tones[tone])}
    >
      {children}
    </span>
  );
}

const PRIORITY_TONE: Record<string, Tone> = { critical: "red", high: "amber", medium: "blue", low: "gray" };
const NATURE_TONE: Record<string, Tone> = { confirmed_issue: "red", statistical_anomaly: "violet", hypothesis: "amber" };
const STATUS_TONE: Record<string, Tone> = {
  open: "red",
  in_review: "amber",
  action_planned: "blue",
  resolved: "green",
  dismissed: "gray",
};
const IMPORT_TONE: Record<string, Tone> = { parsed: "gray", validated: "blue", committed: "green", reverted: "amber", failed: "red" };

export const PriorityBadge = ({ value }: { value: string }) => <Badge tone={PRIORITY_TONE[value]}>{label(PRIORITY_LABELS, value)}</Badge>;
export const NatureBadge = ({ value }: { value: string }) => (
  <Badge tone={NATURE_TONE[value]} title={NATURE_HELP[value]}>
    {label(NATURE_LABELS, value)}
  </Badge>
);
export const StatusBadge = ({ value }: { value: string }) => <Badge tone={STATUS_TONE[value]}>{label(STATUS_LABELS, value)}</Badge>;
export const ImportStatusBadge = ({ value }: { value: string }) => (
  <Badge tone={IMPORT_TONE[value]}>{label(IMPORT_STATUS_LABELS, value)}</Badge>
);
export const DemoBadge = () => (
  <Badge tone="violet" title="Datos sintéticos de demostración: no pertenecen a la organización.">
    DEMO
  </Badge>
);
