/* Use case: Restricts private embedded dashboards to their explicitly approved host.
What it does: Fetches only a fixed API descriptor, denies missing grants and emits an exact frame-ancestors policy without putting credentials in URLs. */

import { NextRequest, NextResponse } from "next/server";

const internalApi = process.env.EXECPLUS_INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function proxy(request: NextRequest) {
  const grant = request.nextUrl.pathname.split("/")[2] ?? "";
  let host = "";
  try {
    if (!uuid.test(grant)) throw new Error("Invalid grant");
    const response = await fetch(`${internalApi}/embed/${grant}/descriptor`, { cache: "no-store", signal: AbortSignal.timeout(2500) });
    if (!response.ok) throw new Error("Unavailable grant");
    const value = await response.json();
    const parsed = new URL(value.host_origin);
    if (parsed.origin !== value.host_origin || !["https:", "http:"].includes(parsed.protocol)) throw new Error("Invalid origin");
    host = parsed.origin;
  } catch {
    return new NextResponse("This private dashboard link is unavailable.", { status: 404, headers: { "Cache-Control": "no-store", "Content-Security-Policy": "frame-ancestors 'none'", "Content-Type": "text/plain; charset=utf-8" } });
  }
  const headers = new Headers(request.headers);
  headers.set("x-execplus-embed-host", host);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", `frame-ancestors ${host}; object-src 'none'; base-uri 'self'`);
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("X-Content-Type-Options", "nosniff");
  return response;
}

export const config = { matcher: "/embed/:path*" };
