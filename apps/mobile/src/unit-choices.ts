/* Use case: Offers likely units for a measure column while the owner answers file questions on the phone.
What it does: Mirrors apps/web/src/app/workspace/unit-choices.ts so both apps suggest the same units; keep them in step. */

const hints: [string[], string[]][] = [
  [["score", "rating", "rank", "index", "level", "grade", "points"], ["unitless", "points"]],
  [["count", "number", "num", "qty", "quantity", "visits", "orders", "clicks", "leads"], ["count", "unitless"]],
  [["price", "cost", "revenue", "sales", "amount", "amt", "salary", "profit", "income", "spend", "budget", "fee", "paid", "value"], ["USD", "PKR", "EUR", "GBP"]],
  [["area", "hectare", "acre"], ["hectare", "acre", "m²"]],
  [["rain", "rainfall", "precipitation"], ["mm", "cm"]],
  [["temp", "temperature"], ["°C", "°F"]],
  [["humidity", "moisture", "pct", "percent", "rate", "share", "ratio", "margin"], ["%", "unitless"]],
  [["weight", "mass", "yield", "kg"], ["kg", "tonnes", "lb"]],
  [["duration", "hours", "minutes", "time", "age", "days", "tenure"], ["hours", "minutes", "days", "years"]],
  [["distance", "length", "height", "depth", "width"], ["m", "cm", "km"]],
  [["ph"], ["pH"]],
  [["ec", "conductivity"], ["dS/m"]],
  [["nitrogen", "phosphorus", "potassium", "ppm"], ["ppm", "kg/ha"]],
];
const common = ["unitless", "%", "count", "USD", "PKR", "kg", "hours", "days"];

function matches(token: string, word: string) {
  return token === word || (word.length > 3 && token.startsWith(word));
}

export function unitChoices(column: string, suggested = ""): string[] {
  const tokens = column.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  const picks = hints
    .filter(([words]) => tokens.some((token) => words.some((word) => matches(token, word))))
    .flatMap(([, units]) => units);
  return [...new Set([suggested, ...picks, ...common].filter(Boolean))].slice(0, 12);
}
