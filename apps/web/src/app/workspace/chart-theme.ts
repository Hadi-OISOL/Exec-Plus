/* Use case: Makes chart labels and marks readable in both appearances.
What it does: Recolors presentation options only; data, callbacks and exact values remain intact. */
const darkColors: Record<string, string> = {
  "#deddd6": "#405950", "#e0e8e2": "#405950", "#a8bdb4": "#658b7e",
  "#53625f": "#bbcec7", "#304c43": "#bbcec7", "#929e99": "#bbcec7", "#8f8e88": "#bbcec7",
  "#173e3b": "#e8efee", "#213a32": "#e8efee", "#123e32": "#e8efee", "#23483d": "#e8efee",
  "#176c64": "#80dbc0", "#176b57": "#80dbc0", "#a56730": "#f5c080",
};
export function chartTheme<T>(value: T, dark: boolean, property = ""): T {
  if (!dark) return value;
  if (typeof value === "string") return ((property === "color" || property.endsWith("Color")) ? darkColors[value.toLowerCase()] ?? value : value) as T;
  if (Array.isArray(value)) return value.map(item => chartTheme(item, true, property)) as T;
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, chartTheme(item, true, key)])) as T;
  return value;
}
