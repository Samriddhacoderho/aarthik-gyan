export function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function scoreValue(score: Record<string, unknown> | null | undefined, key: string): number | null {
  return asNumber(score?.[key]);
}

export function fmtNumber(value: unknown, digits = 2): string {
  const number = asNumber(value);
  if (number === null) return "—";
  return number.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtRatio(value: unknown): string {
  return fmtNumber(value, 2);
}

export function fmtPercent(value: unknown): string {
  const number = asNumber(value);
  if (number === null) return "—";
  return `${(number * 100).toFixed(1)}%`;
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 19).replace("T", " ");
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function fmtBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export function shortHash(hash: string | null | undefined, length = 10): string {
  if (!hash) return "—";
  return hash.length <= length ? hash : hash.slice(0, length);
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function riskLevel(value: unknown): "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN" {
  const level = String(value ?? "UNKNOWN").toUpperCase();
  if (level === "LOW" || level === "MEDIUM" || level === "HIGH") return level;
  return "UNKNOWN";
}
