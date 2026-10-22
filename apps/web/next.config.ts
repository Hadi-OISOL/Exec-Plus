/* Use case: Configures the Next.js application runtime.
What it does: Enables strict React checks, anti-framing response headers, limits operator token sign-in to development/browser-test builds and produces a standalone deployment artifact. */

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
  poweredByHeader: false,
  async headers() {
    const shared = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    ];
    const unframed = [
      ...shared,
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
    ];
    return [
      { source: "/", headers: unframed },
      { source: "/workspace/:path*", headers: unframed },
      { source: "/embed/:path*", headers: shared },
    ];
  },
  allowedDevOrigins: (process.env.EXECPLUS_WEB_DEV_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean),
});

export default nextConfig;
