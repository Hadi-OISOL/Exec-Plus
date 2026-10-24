/* Use case: Shapes the protected workspace usage report for display.
What it does: Fills every day of the reported window with exact server counts (missing days are zero) without estimating anything. */

export type DailyUsage = { from: string; to: string; kinds: string[]; rows: { day: string; kind: string; count: number }[] };
export type UsageDay = { day: string; counts: Record<string, number>; total: number };

export function dailyHistory(daily: DailyUsage): UsageDay[] {
  const counts = new Map(daily.rows.map(row => [`${row.day}|${row.kind}`, row.count]));
  const days: UsageDay[] = [];
  for (let day = new Date(`${daily.to}T00:00:00Z`); day >= new Date(`${daily.from}T00:00:00Z`); day.setUTCDate(day.getUTCDate() - 1)) {
    const key = day.toISOString().slice(0, 10);
    const values = Object.fromEntries(daily.kinds.map(kind => [kind, counts.get(`${key}|${kind}`) ?? 0]));
    days.push({ day: key, counts: values, total: Object.values(values).reduce((sum, value) => sum + value, 0) });
  }
  return days;
}

export function usedShare(used: number | null, limit: number | null): string {
  if (used === null || limit === null) return "No plan limit";
  if (limit === 0) return "100%";
  return `${Math.floor((used * 100) / limit)}%`;
}
