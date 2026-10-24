/* Use case: Supplies pure helpers for change investigations and scheduled allocations.
What it does: Builds calendar-month windows, re-checks exact fractions add back with BigInt
and groups saved scheduled actions by period without calculating any business number. */

export type ExactFraction = { numerator: string; denominator: string };
export type MonthComparison = "previous" | "year";

const pad = (value: number) => String(value).padStart(2, "0");
const monthStart = (year: number, month: number) => `${year}-${pad(month)}-01`;
const monthEnd = (year: number, month: number) => `${year}-${pad(month)}-${pad(new Date(Date.UTC(year, month, 0)).getUTCDate())}`;

export function monthWindows(month: string, against: MonthComparison): [string, string, string, string] | null {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return null;
  const year = Number(match[1]);
  const current = Number(match[2]);
  if (current < 1 || current > 12) return null;
  const [baseYear, baseMonth] = against === "year" ? [year - 1, current] : current === 1 ? [year - 1, 12] : [year, current - 1];
  return [monthStart(baseYear, baseMonth), monthEnd(baseYear, baseMonth), monthStart(year, current), monthEnd(year, current)];
}

export function addsBack(parts: ExactFraction[], total: ExactFraction): boolean {
  let numerator = BigInt(0);
  let denominator = BigInt(1);
  for (const part of parts) {
    const n = BigInt(part.numerator);
    const d = BigInt(part.denominator);
    numerator = numerator * d + n * denominator;
    denominator *= d;
  }
  return numerator * BigInt(total.denominator) === BigInt(total.numerator) * denominator;
}

export function byPeriod<T extends { period?: number | null }>(rows: T[], periods: number): T[][] {
  return Array.from({ length: periods }, (_, index) => rows.filter(row => row.period === index + 1));
}
