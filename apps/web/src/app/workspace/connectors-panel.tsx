/* Use case: Lets a signed-in user connect accounting systems and databases and import one source.
What it does: Lists the configured platforms, runs each connect step, browses sources and hands the choice to the page. */

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./connectors-panel.module.css";

type Field = { name: string; label: string; secret: boolean; placeholder: string };
type Platform = {
  id: string;
  label: string;
  kind: "oauth" | "credentials" | "unavailable";
  description: string;
  fields: Field[];
  connected: boolean;
  account: string;
  configured?: boolean;
};
type Item = { id: string; label: string; container: boolean };
type Crumb = { id: string | null; label: string };
export type ConnectorChoice = {
  provider: string;
  sourceId: string;
  platform: string;
  title: string;
};

export function ConnectorsPanel({
  request,
  disabled,
  onImport,
}: {
  request: ApiRequest;
  disabled: boolean;
  onImport: (choice: ConnectorChoice) => Promise<void>;
}) {
  const [platforms, setPlatforms] = useState<Platform[] | null>(null);
  const [form, setForm] = useState<{ id: string; values: Record<string, string> } | null>(null);
  const [browsing, setBrowsing] = useState<{ platform: Platform; trail: Crumb[]; items: Item[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    try {
      setPlatforms(await request<Platform[]>("/connectors"));
    } catch (cause) {
      setPlatforms(null);
      setBrowsing(null);
      setForm(null);
      throw cause;
    }
  }, [request]);

  useEffect(() => {
    let active = true;
    request<Platform[]>("/connectors")
      .then(value => {
        if (active) setPlatforms(value);
      })
      .catch(() => {
        if (active) {
          setPlatforms([]);
          setBrowsing(null);
          setForm(null);
        }
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
      if ([401, 403, 404, 409].includes((cause as { status?: number })?.status ?? 0)) {
        setPlatforms(null);
        setBrowsing(null);
        setForm(null);
      }
      setError(cause instanceof Error ? cause.message : "The platform could not be reached.");
    } finally {
      setBusy(false);
    }
  }

  function connect(platform: Platform) {
    if (platform.kind === "credentials") {
      setForm({ id: platform.id, values: {} });
      return Promise.resolve();
    }
    return attempt(async () => {
      const { url } = await request<{ url: string }>(`/connectors/${platform.id}/connect`, {
        method: "POST",
        credentials: "include",
      });
      window.location.assign(url);
    });
  }

  function submit(event: FormEvent<HTMLFormElement>, platform: Platform) {
    event.preventDefault();
    return attempt(async () => {
      await request(`/connectors/${platform.id}/credentials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values: form?.values ?? {} }),
      });
      setForm(null);
      await reload();
    });
  }

  function disconnect(platform: Platform) {
    return attempt(async () => {
      await request(`/connectors/${platform.id}`, { method: "DELETE" });
      setBrowsing(null);
      await reload();
    });
  }

  async function list(platform: Platform, trail: Crumb[]) {
    setBrowsing(null);
    const parent = trail[trail.length - 1]?.id ?? null;
    const query = parent ? `?parent=${encodeURIComponent(parent)}` : "";
    try {
      const items = await request<Item[]>(`/connectors/${platform.id}/sources${query}`);
      setBrowsing({ platform, trail, items });
    } catch (cause) {
      setPlatforms(null);
      setForm(null);
      throw cause;
    }
  }

  function choose(item: Item) {
    if (!browsing) return Promise.resolve();
    if (item.container)
      return attempt(() => list(browsing.platform, [...browsing.trail, { id: item.id, label: item.label }]));
    return attempt(() =>
      onImport({
        provider: browsing.platform.id,
        sourceId: item.id,
        platform: browsing.platform.label,
        title: `${browsing.platform.label} - ${item.label}`,
      }).then(() => setBrowsing(null)),
    );
  }

  if (!platforms?.length && !error) return null;
  const ready = (platforms ?? []).filter(platform => platform.configured !== false);
  const unavailable = (platforms ?? []).filter(platform => platform.configured === false);

  return (
    <section className={styles.connectors} aria-label="Connect your data">
      <h3>Or connect an accounting system or database</h3>
      <p>
        Pick a platform, sign in once, then choose what to copy. Syntelio only reads
        a snapshot and you can disconnect at any time.
      </p>
      {!ready.length && <p>No data platforms are set up on this server yet.</p>}
      <ul className={styles.list}>
        {ready.map(platform => (
          <li key={platform.id} className={styles.card}>
            <div>
              <strong>{platform.label}</strong>
              <span>{platform.description}</span>
              {platform.connected && <em>Connected as {platform.account}</em>}
            </div>
            <div className={styles.actions}>
              {!platform.connected ? (
                <button type="button" disabled={busy || disabled} onClick={() => connect(platform)}>
                  Connect {platform.label}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    disabled={busy || disabled}
                    onClick={() => attempt(() => list(platform, []))}
                  >
                    Choose data
                  </button>
                  <button
                    type="button"
                    className={styles.secondary}
                    disabled={busy || disabled}
                    onClick={() => disconnect(platform)}
                  >
                    Disconnect
                  </button>
                </>
              )}
            </div>
            {form?.id === platform.id && (
              <form className={styles.form} onSubmit={event => submit(event, platform)}>
                {platform.fields.map(field => (
                  <label key={field.name}>
                    {field.label}
                    <input
                      type={field.secret ? "password" : "text"}
                      placeholder={field.placeholder}
                      autoComplete="off"
                      value={form.values[field.name] ?? ""}
                      onChange={event =>
                        setForm({
                          id: platform.id,
                          values: { ...form.values, [field.name]: event.target.value },
                        })
                      }
                    />
                  </label>
                ))}
                <div className={styles.actions}>
                  <button disabled={busy || disabled}>Connect</button>
                  <button type="button" className={styles.secondary} onClick={() => setForm(null)}>
                    Cancel
                  </button>
                </div>
              </form>
            )}
            {browsing?.platform.id === platform.id && (
              <div className={styles.browser}>
                <nav aria-label="Where you are">
                  <button type="button" className={styles.link} onClick={() => attempt(() => list(platform, []))}>
                    {platform.label}
                  </button>
                  {browsing.trail.map((crumb, index) => (
                    <button
                      key={crumb.id}
                      type="button"
                      className={styles.link}
                      onClick={() => attempt(() => list(platform, browsing.trail.slice(0, index + 1)))}
                    >
                      / {crumb.label}
                    </button>
                  ))}
                </nav>
                <ul>
                  {browsing.items.map(item => (
                    <li key={item.id}>
                      <button type="button" disabled={busy || disabled} onClick={() => choose(item)}>
                        {item.container ? `${item.label} ›` : `Import ${item.label}`}
                      </button>
                    </li>
                  ))}
                  {!browsing.items.length && <li>Nothing to show here.</li>}
                </ul>
              </div>
            )}
          </li>
        ))}
      </ul>
      {unavailable.length > 0 && (
        <details className={styles.unavailable}>
          <summary>Not set up on this server ({unavailable.length})</summary>
          <ul aria-label="Platforms not set up">
            {unavailable.map(platform => (
              <li key={platform.id}>
                <strong>{platform.label}</strong> <span>{platform.description}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
    </section>
  );
}
