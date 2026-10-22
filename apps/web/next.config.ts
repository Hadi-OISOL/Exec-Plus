/* Use case: Configures the Next.js application runtime.
What it does: Enables strict React checks, standalone output and anti-framing response headers. */

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
};

export default nextConfig;
