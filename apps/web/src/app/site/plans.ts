/* Use case: Static plan data for the public pricing section.
What it does: Mirrors the backend plan catalog (apps/api/src/execplus/domain/plans.py CATALOG and PRICE_USD_MONTH) as human-readable strings; no billing. */

// shortcut: placeholder prices; owner will set real values, keep in step with GET /plans/public
export type Plan = {
  key: "demo" | "starter" | "growth" | "enterprise";
  name: string;
  priceUsdMonth: number | null;
  headline: string;
  limits: {
    seats: string;
    datasets: string;
    uploadSize: string;
    storage: string;
    savedStudies: string;
    processingPerMonth: string;
    exports: string;
    forecasts: string;
    aiAttempts: string;
  };
};

export const PLANS: readonly Plan[] = [
  {
    key: "demo",
    name: "Free",
    priceUsdMonth: 0,
    headline: "Everything a new account gets today.",
    limits: {
      seats: "5 team seats",
      datasets: "10 datasets",
      uploadSize: "500 MiB per file",
      storage: "5 GiB storage",
      savedStudies: "100 saved studies",
      processingPerMonth: "10,000 processing operations a month",
      exports: "100 exports",
      forecasts: "100 forecasts",
      aiAttempts: "500 AI attempts",
    },
  },
  {
    key: "starter",
    name: "Pro",
    priceUsdMonth: 50,
    headline: "More room for a working team.",
    limits: {
      seats: "10 team seats",
      datasets: "50 datasets",
      uploadSize: "500 MiB per file",
      storage: "10 GiB storage",
      savedStudies: "500 saved studies",
      processingPerMonth: "50,000 processing operations a month",
      exports: "500 exports",
      forecasts: "500 forecasts",
      aiAttempts: "2,000 AI attempts",
    },
  },
  {
    key: "growth",
    name: "Team",
    priceUsdMonth: 100,
    headline: "Several teams, many datasets.",
    limits: {
      seats: "30 team seats",
      datasets: "200 datasets",
      uploadSize: "500 MiB per file",
      storage: "50 GiB storage",
      savedStudies: "2,000 saved studies",
      processingPerMonth: "200,000 processing operations a month",
      exports: "2,000 exports",
      forecasts: "2,000 forecasts",
      aiAttempts: "10,000 AI attempts",
    },
  },
  {
    key: "enterprise",
    name: "Enterprise",
    priceUsdMonth: null,
    headline: "Contact us for the largest allowances.",
    limits: {
      seats: "100 team seats",
      datasets: "1,000 datasets",
      uploadSize: "500 MiB per file",
      storage: "200 GiB storage",
      savedStudies: "10,000 saved studies",
      processingPerMonth: "1,000,000 processing operations a month",
      exports: "10,000 exports",
      forecasts: "10,000 forecasts",
      aiAttempts: "50,000 AI attempts",
    },
  },
];
