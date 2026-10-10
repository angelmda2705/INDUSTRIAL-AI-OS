const LOCALE = "es-MX";

export function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(value);
}

export function fmtMoney(value: number | null | undefined, currency = "MXN"): string {
  if (value === null || value === undefined) return "—";
  try {
    return new Intl.NumberFormat(LOCALE, { style: "currency", currency, maximumFractionDigits: 0 }).format(value);
  } catch {
    return `${fmtNumber(value, 0)} ${currency}`;
  }
}

export function fmtKpi(value: number | null | undefined, unit: string, currency = "MXN"): string {
  if (value === null || value === undefined) return "—";
  if (unit === "moneda") return fmtMoney(value, currency);
  if (unit === "moneda/km") return `${fmtNumber(value, 2)} ${currency}/km`;
  if (unit === "%") return `${fmtNumber(value, 1)} %`;
  return `${fmtNumber(value, 2)} ${unit}`;
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(LOCALE, { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString(LOCALE, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function fmtMonth(value: string): string {
  const d = new Date(`${value.slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString(LOCALE, { month: "short", year: "2-digit" });
}

export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function fmtCell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return fmtNumber(value, 3);
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
