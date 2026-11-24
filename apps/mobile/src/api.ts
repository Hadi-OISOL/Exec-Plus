/* Use case: Connects the Osalytix phone app to the live Osalytix API on the VPS.
What it does: Keeps the session token in secure storage and sends authenticated JSON or file requests, turning API errors into readable messages. */

import * as SecureStore from "expo-secure-store";

export const SITE = "https://syntelio.173-208-151-137.sslip.io";
export const API = `${SITE}/api`;
const TOKEN_KEY = "osalytix.session";
let token: string | null = null;

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export async function loadToken() {
  token = await SecureStore.getItemAsync(TOKEN_KEY);
  return token;
}

export async function saveToken(value: string | null) {
  token = value;
  if (value) await SecureStore.setItemAsync(TOKEN_KEY, value);
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
}

function messageOf(body: unknown, status: number) {
  const value = body as { error?: { message?: string }; detail?: unknown } | null;
  if (value?.error?.message) return value.error.message;
  if (typeof value?.detail === "string") return value.detail;
  if (Array.isArray(value?.detail)) return "Please check the details you entered.";
  if (status === 401) return "Your session has ended. Please sign in again.";
  return `Something went wrong (${status}).`;
}

export async function api<T = any>(
  path: string,
  options: { method?: string; body?: unknown; raw?: Blob; contentType?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = { Origin: SITE, Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (options.raw) {
    body = options.raw;
    headers["Content-Type"] = options.contentType ?? "application/octet-stream";
  } else if (options.body !== undefined) {
    body = JSON.stringify(options.body);
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(API + path, {
    method: options.method ?? (body ? "POST" : "GET"),
    headers,
    body,
  });
  const text = await response.text();
  const parsed = text ? safeJson(text) : null;
  if (!response.ok) throw new ApiError(messageOf(parsed, response.status), response.status);
  return parsed as T;
}

function safeJson(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function newRequestId() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export type Upload = {
  id: string;
  dataset_id: string;
  workspace_id: string;
  filename: string;
  size: number;
  row_count: number | null;
  column_count: number | null;
  created_at: string;
};
export type Source = { workspaceId: string; datasetId: string; datasetName: string; upload: Upload };

export const rootOf = (s: Source) =>
  `/workspaces/${s.workspaceId}/datasets/${s.datasetId}/uploads/${s.upload.id}`;
