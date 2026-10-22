/* Use case: Configures the Next.js application runtime.
What it does: Enables strict React checks, limits operator token sign-in to development/browser-test builds and produces a standalone deployment artifact. */

import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const nextConfig = (phase: string): NextConfig => ({
  env: {
    NEXT_PUBLIC_EXECPLUS_OPERATOR_SIGNIN:
      process.env.EXECPLUS_BROWSER_BUILD === "1" || phase === PHASE_DEVELOPMENT_SERVER
        ? "1"
        : "0",
  },
  distDir:
    process.env.EXECPLUS_BROWSER_BUILD === "1" ? ".next/browser" : ".next",
  output: "standalone",
  reactStrictMode: true,
  allowedDevOrigins: (process.env.EXECPLUS_WEB_DEV_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean),
});

export default nextConfig;
