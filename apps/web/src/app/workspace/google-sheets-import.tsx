/* Use case: Lets a signed-in user connect Google and import one sheet they choose with Google's picker.
What it does: Handles the connection, the picker, tab choice and hands the choice to the page for import. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./google-sheets-import.module.css";

type PickerData = { action: string; docs?: { id: string }[] };
type PickerApi = {
  ViewId: { SPREADSHEETS: string };
  Action: { PICKED: string };
  DocsView: new (viewId: string) => object;
  PickerBuilder: new () => {
    addView: (view: object) => unknown;
    setOAuthToken: (token: string) => unknown;
    setDeveloperKey: (key: string) => unknown;
    setAppId: (id: string) => unknown;
    setCallback: (callback: (data: PickerData) => void) => unknown;
    build: () => { setVisible: (visible: boolean) => void };
  };
};
declare global {
  interface Window {
    gapi?: { load: (name: string, callback: () => void) => void };
    google?: { picker?: PickerApi };
  }
}
type Config = { enabled: boolean; picker: { api_key: string; app_id: string } | null };
type Status = { connected: boolean; email: string };
type Tab = { id: number; title: string; rows: number; columns: number };
type Pending = { id: string; title: string; tabs: Tab[]; tabId: number | null };
export type SheetChoice = { spreadsheetId: string; sheetId: number | null; title: string };

const pickerScript = "https://apis.google.com/js/api.js";

function loadPicker(): Promise<PickerApi> {
  return new Promise((resolve, reject) => {
    const ready = () => {
      const picker = window.google?.picker;
      if (picker) resolve(picker);
      else reject(new Error("Google's picker could not be loaded."));
    };
    if (window.google?.picker) return ready();
    const start = () => {
      if (!window.gapi) return reject(new Error("Google's picker could not be loaded."));
      window.gapi.load("picker", ready);
    };
    if (window.gapi) return start();
    const script = document.createElement("script");
    script.src = pickerScript;
    script.async = true;
    script.onload = start;
    script.onerror = () => reject(new Error("Google's picker could not be loaded."));
    document.head.appendChild(script);
  });
}

export function GoogleSheetsImport({
  request,
  disabled,
  onConnecting,
  onImport,
}: {
  request: ApiRequest;
  disabled: boolean;
  onConnecting: () => void;
  onImport: (choice: SheetChoice) => Promise<void>;
}) {
  const [config, setConfig] = useState<Config | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      request<Config>("/auth/google/config"),
      request<Status>("/integrations/google/status").catch(() => ({
        connected: false,
        email: "",
      })),
    ])
      .then(([loaded, state]) => {
        if (!active) return;
        setConfig(loaded);
        setStatus(state);
      })
      .catch(() => {
        if (active) setConfig({ enabled: false, picker: null });
      });
    return () => {
      active = false;
    };
  }, [request]);

  async function attempt(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Google could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  async function connect() {
    await attempt(async () => {
      const { url } = await request<{ url: string }>("/integrations/google/connect", {
        method: "POST",
      });
      onConnecting();
      window.location.assign(url);
    });
  }

  async function disconnect() {
    await attempt(async () => {
      await request("/integrations/google", { method: "DELETE" });
      setStatus({ connected: false, email: "" });
      setPending(null);
    });
  }

  async function choose(id: string) {
    const sheet = await request<{ title: string; tabs: Tab[] }>(
      `/integrations/google/spreadsheets/${encodeURIComponent(id)}`,
    );
    if (sheet.tabs.length > 1) {
      setPending({ id, title: sheet.title, tabs: sheet.tabs, tabId: sheet.tabs[0].id });
      return;
    }
    await onImport({
      spreadsheetId: id,
      sheetId: sheet.tabs[0]?.id ?? null,
      title: sheet.title,
    });
  }

  async function pick() {
    await attempt(async () => {
      if (!config?.picker) throw new Error("Google's picker is not configured.");
      const key = config.picker;
      const [{ access_token: token }, picker] = await Promise.all([
        request<{ access_token: string }>("/integrations/google/picker-token"),
        loadPicker(),
      ]);
      const builder = new picker.PickerBuilder();
      builder.addView(new picker.DocsView(picker.ViewId.SPREADSHEETS));
      builder.setOAuthToken(token);
      builder.setDeveloperKey(key.api_key);
      builder.setAppId(key.app_id);
      builder.setCallback((data: PickerData) => {
        const id = data.action === picker.Action.PICKED ? data.docs?.[0]?.id : undefined;
        if (id) void attempt(() => choose(id));
      });
      builder.build().setVisible(true);
    });
  }

  if (!config?.enabled) return null;

  return (
    <section className={styles.google} aria-label="Import from Google Sheets">
      <h3>Or import from Google Sheets</h3>
      <p>
        Pick a sheet in Google&apos;s own chooser. ExecPlus can open only the sheets you
        choose, and you can disconnect at any time.
      </p>
      {!status?.connected ? (
        <button type="button" disabled={busy || disabled} onClick={connect}>
          Connect Google
        </button>
      ) : (
        <div className={styles.row}>
          <button type="button" disabled={busy || disabled} onClick={pick}>
            {busy ? "Working…" : "Choose a Google Sheet"}
          </button>
          <button
            type="button"
            className={styles.secondary}
            disabled={busy || disabled}
            onClick={disconnect}
          >
            Disconnect {status.email}
          </button>
        </div>
      )}
      {pending && (
        <div className={styles.tabs}>
          <label>
            Which tab should be imported from “{pending.title}”?
            <select
              value={pending.tabId ?? ""}
              onChange={(event) =>
                setPending({ ...pending, tabId: Number(event.target.value) })
              }
            >
              {pending.tabs.map((tab) => (
                <option key={tab.id} value={tab.id}>
                  {tab.title}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || disabled}
            onClick={() =>
              attempt(async () => {
                await onImport({
                  spreadsheetId: pending.id,
                  sheetId: pending.tabId,
                  title: pending.title,
                });
                setPending(null);
              })
            }
          >
            Import this tab
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
    </section>
  );
}
