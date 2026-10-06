/* Use case: Projects exact returned values into safe, bounded chart geometry.
What it does: Preserves original cells and null gaps while deriving only approximate plot coordinates, never business totals. */

export type VisualizationCell = string | number | boolean | null;
export type PlotPoint = {
  row: VisualizationCell[];
  label: string;
  raw: VisualizationCell;
  value: number | null;
};

export function exactCell(value: VisualizationCell | undefined): string {
  return value === null || value === undefined ? "Missing" : String(value);
}

export function plotNumber(
  value: VisualizationCell | undefined,
): number | null {
  if (typeof value === "boolean" || value === null || value === undefined)
    return null;
  if (
    typeof value === "string" &&
    !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value)
  )
    return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function chartEligible(
  columns: string[],
  rows: VisualizationCell[][],
  category = 0,
  measure = 1,
): boolean {
  return (
    category !== measure &&
    category >= 0 &&
    measure >= 0 &&
    category < columns.length &&
    measure < columns.length &&
    rows.length > 0 &&
    rows.some((row) => plotNumber(row[measure]) !== null) &&
    rows.every(
      (row) => row[measure] === null || plotNumber(row[measure]) !== null,
    )
  );
}

export function plotPoints(
  rows: VisualizationCell[][],
  category: number,
  measure: number,
  limit = 30,
): PlotPoint[] {
  return rows
    .slice(0, Math.max(1, Math.min(100, limit)))
    .map((row) => ({
      row,
      label: exactCell(row[category]),
      raw: row[measure] ?? null,
      value: plotNumber(row[measure]),
    }));
}

export function plotScale(points: PlotPoint[]): {
  position: (value: number) => number;
  zero: number;
} {
  const values = points.flatMap((point) =>
    point.value === null ? [] : [point.value],
  );
  const magnitude = Math.max(...values.map(Math.abs), Number.MIN_VALUE);
  const minimum = Math.min(0, ...values.map((value) => value / magnitude));
  const maximum = Math.max(0, ...values.map((value) => value / magnitude));
  const width = maximum - minimum || 1;
  const position = (value: number) =>
    ((value / magnitude - minimum) / width) * 100;
  return { position, zero: position(0) };
}

export function lineSegments(
  points: PlotPoint[],
): { x: number; y: number; index: number }[][] {
  const scale = plotScale(points);
  const segments: { x: number; y: number; index: number }[][] = [];
  let segment: { x: number; y: number; index: number }[] = [];
  points.forEach((point, index) => {
    if (point.value === null) {
      if (segment.length) segments.push(segment);
      segment = [];
    } else {
      segment.push({
        x: points.length < 2 ? 50 : (index / (points.length - 1)) * 100,
        y: 100 - scale.position(point.value),
        index,
      });
    }
  });
  if (segment.length) segments.push(segment);
  return segments;
}

function decimalParts(value: VisualizationCell) {
  if (plotNumber(value) === null) return null;
  const parts = String(value).match(
    /^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/,
  );
  if (!parts) return null;
  const all = parts[2] + (parts[3] ?? "");
  const digits = all.replace(/^0+/, "").replace(/0+$/, "");
  return {
    sign: digits ? (parts[1] === "-" ? -1 : 1) : 0,
    digits,
    order:
      parts[2].length -
      (all.length - all.replace(/^0+/, "").length) +
      Number(parts[4] ?? 0),
  };
}

export function compareExactNumeric(
  left: VisualizationCell,
  right: VisualizationCell,
): number {
  const a = decimalParts(left);
  const b = decimalParts(right);
  if (!a || !b) return a ? 1 : b ? -1 : 0;
  if (a.sign !== b.sign) return a.sign - b.sign;
  if (!a.sign) return 0;
  if (a.order !== b.order) return Math.sign(a.order - b.order) * a.sign;
  const width = Math.max(a.digits.length, b.digits.length);
  const first = a.digits.padEnd(width, "0");
  const second = b.digits.padEnd(width, "0");
  return (first < second ? -1 : first > second ? 1 : 0) * a.sign;
}
