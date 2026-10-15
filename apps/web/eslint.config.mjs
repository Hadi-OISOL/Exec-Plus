/* Use case: Defines static-analysis rules for the ExecPlus web application.
What it does: Applies the Next.js core-vitals and TypeScript rule sets with generated paths excluded. */

import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextCoreWebVitals,
  ...nextTypeScript,
  globalIgnores([".next/**", "out/**", "build/**", "test-results/**", "playwright-report/**", "next-env.d.ts"]),
]);

