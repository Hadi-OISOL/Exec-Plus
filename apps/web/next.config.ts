/* Use case: Configures the Next.js application runtime.
What it does: Enables strict React checks and produces a standalone deployment artifact. */

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir:
    process.env.EXECPLUS_BROWSER_BUILD === "1" ? ".next/browser" : ".next",
  output: "standalone",
  reactStrictMode: true,
  allowedDevOrigins: (process.env.EXECPLUS_WEB_DEV_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean),
};

export default nextConfig;
