/* Use case: Provides the Week 1 workspace and upload journey.
What it does: Supports local sign-in, invitations, team seats, datasets, and validated file uploads. */

"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import type { FormEvent } from "react";

import { ProfilePanel } from "./profile-panel";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Workspace = { id: string; name: string; seat_limit: number };
type Dataset = { id: string; name: string };
type Member = { user_id: string; role: string; email: string };
type Invitation = {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
};
type Upload = {
  id: string;
  filename: string;
  sample_id: string | null;
  size: number;
  row_count: number;
  column_count: number;
  status: string;
};
type User = { id: string; email: string };

export default function WorkspacePage() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [profileUpload, setProfileUpload] = useState("");
  const [usage, setUsage] = useState<{
    active_seats: number;
    seat_limit: number;
    uploads: number;
    storage_bytes: number;
  } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const role = members.find((member) => member.user_id === user?.id)?.role;
  const manager = role === "owner" || role === "admin";

  const request = useCallback(
    async function request<T>(
      path: string,
      options: RequestInit = {},
    ): Promise<T> {
      const response = await fetch(`${api}${path}`, {
        ...options,
        headers: { Authorization: `Bearer ${token}`, ...options.headers },
        cache: "no-store",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        if (response.status === 401) setUser(null);
        throw new Error(
          body.error?.message ?? "The request failed. Please try again.",
        );
      }
      return response.status === 204 ? (undefined as T) : response.json();
    },
    [token],
  );

  function json(method: string, body: object): RequestInit {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    };
  }

  async function run(action: () => Promise<void>) {
    setNow(Date.now());
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not connect. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function selectWorkspace(selected: Workspace, actorId = user?.id) {
    setWorkspace(selected);
    setUsage(null);
    setProfileUpload("");
    setDatasets([]);
    setDataset("");
    setUploads([]);
    setMembers([]);
    setInvitations([]);
    setFile(null);
    const prefix = `/workspaces/${selected.id}`;
    const [nextDatasets, nextMembers] = await Promise.all([
      request<Dataset[]>(`${prefix}/datasets`),
      request<Member[]>(`${prefix}/members`),
    ]);
    setDatasets(nextDatasets);
    setMembers(nextMembers);
    const nextRole = nextMembers.find(
      (member) => member.user_id === actorId,
    )?.role;
    if (nextRole === "owner" || nextRole === "admin") {
      setInvitations(await request<Invitation[]>(`${prefix}/invitations`));
    }
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const current = await request<User>("/auth/me");
      setUser(current);
      const available = await request<Workspace[]>("/workspaces");
      setWorkspaces(available);
      if (available.length) await selectWorkspace(available[0], current.id);
      else setWorkspace(null);
      setMessage(
        "Signed in. Create a workspace or accept an invitation to begin.",
      );
    });
  }

  async function createWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await run(async () => {
      const created = await request<Workspace>(
        "/workspaces",
        json("POST", {
          name: data.get("name"),
          seat_limit: Number(data.get("seats")),
        }),
      );
      setWorkspaces(await request<Workspace[]>("/workspaces"));
      await selectWorkspace(created);
      form.reset();
      setMessage("Workspace created. Invite your team or add a dataset.");
    });
  }

  async function createDataset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = new FormData(form).get("name");
    await run(async () => {
      const created = await request<Dataset>(
        `/workspaces/${workspace!.id}/datasets`,
        json("POST", { name }),
      );
      setDatasets(
        await request<Dataset[]>(`/workspaces/${workspace!.id}/datasets`),
      );
      setDataset(created.id);
      setProfileUpload("");
      setUploads([]);
      form.reset();
      setMessage("Dataset created. Choose a file to upload.");
    });
  }

  async function uploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    await run(async () => {
      if (!file) throw new Error("Choose a CSV or XLSX file.");
      if (file.size > 20 * 1024 * 1024)
        throw new Error("Files must be at most 20 MiB.");
      const mime = file.name.toLowerCase().endsWith(".csv")
        ? "text/csv"
        : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const prefix = `/workspaces/${workspace!.id}/datasets/${dataset}/uploads`;
      const stored = await request<Upload>(
        `${prefix}?filename=${encodeURIComponent(file.name)}`,
        {
          method: "POST",
          headers: { "Content-Type": mime },
          body: file,
        },
      );
      setUploads(await request<Upload[]>(prefix));
      setProfileUpload(stored.id);
      setMessage(
        `${stored.filename} uploaded successfully. Original file retained; structure validated.`,
      );
      setFile(null);
      form.reset();
    });
  }

  async function inviteMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await run(async () => {
      await request(
        `/workspaces/${workspace!.id}/invitations`,
        json("POST", { email: data.get("email"), role: data.get("role") }),
      );
      setInvitations(
        await request<Invitation[]>(`/workspaces/${workspace!.id}/invitations`),
      );
      form.reset();
      setMessage(
        "Invitation created and a seat reserved for seven days. Copy the invitation link to share it.",
      );
    });
  }

  async function acceptInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const value = String(new FormData(form).get("link"));
    await run(async () => {
      let link: URL;
      try {
        link = new URL(value);
      } catch {
        throw new Error("Paste a valid invitation link.");
      }
      const wid = link.searchParams.get("workspace");
      const iid = link.searchParams.get("invitation");
      const uuid =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (!wid || !iid || !uuid.test(wid) || !uuid.test(iid))
        throw new Error("The link is missing valid invitation details.");
      await request(`/workspaces/${wid}/invitations/${iid}/accept`, {
        method: "POST",
      });
      const available = await request<Workspace[]>("/workspaces");
      setWorkspaces(available);
      await selectWorkspace(available.find((item) => item.id === wid)!);
      form.reset();
      setMessage("Invitation accepted. You can now access this workspace.");
    });
  }

  return (
    <main className="workspaceApp">
      <nav aria-label="Primary navigation">
        <Link className="brand" href="/">
          E+ · ExecPlus
        </Link>
        <span className="phaseBadge">Secure data preparation</span>
      </nav>
      <header className="workspaceHeader">
        <p className="eyebrow">Your data starts here</p>
        <h1>Workspace & uploads</h1>
        <p>
          Create a team space, invite teammates, and securely store a
          single-table CSV or Excel file.
        </p>
      </header>
      <div aria-live="polite" role="status" className="notice">
        {busy ? "Working…" : message}
      </div>
      {error && (
        <p role="alert" aria-label="Request error" className="errorNotice">
          {error}
        </p>
      )}
      {!user ? (
        <section className="panel">
          <h2>Sign in</h2>
          <p>
            Use the development session token provided by your local operator.
            Sessions expire after eight hours.
          </p>
          <form onSubmit={signIn}>
            <label>
              Session token
              <input
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                required
                autoComplete="off"
              />
            </label>
            <button disabled={busy}>Sign in</button>
          </form>
        </section>
      ) : (
        <>
          <div className="sessionBar">
            <span>Signed in as {user.email}</span>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await request("/auth/logout", { method: "POST" });
                  setToken("");
                  setUser(null);
                  setWorkspace(null);
                  setWorkspaces([]);
                  setDatasets([]);
                  setDataset("");
                  setMembers([]);
                  setInvitations([]);
                  setUploads([]);
                  setFile(null);
                  setMessage("");
                  setError("");
                })
              }
            >
              Sign out
            </button>
          </div>
          <section className="panel" aria-label="Getting started">
            <h2>Getting started</h2>
            <ol>
              <li>
                {workspace
                  ? "✓ Workspace ready"
                  : "Create or join your workspace below."}
              </li>
              <li>
                {members.length > 1 || invitations.length
                  ? "✓ Team invitation started"
                  : "Invite a teammate from the Team section (owners and admins)."}
              </li>
              <li>
                Explore a synthetic sample to learn about profiles and quality.
              </li>
              <li>
                {uploads.some((item) => !item.sample_id)
                  ? "✓ File uploaded — review its profile below"
                  : "Create a dataset, then upload your first CSV or Excel file."}
              </li>
            </ol>
          </section>
          <div className="workspaceGrid">
            <section className="panel">
              <h2>1. Choose your workspace</h2>
              <label>
                Current workspace
                <select
                  value={workspace?.id ?? ""}
                  disabled={busy || !workspaces.length}
                  onChange={(event) =>
                    void run(() =>
                      selectWorkspace(
                        workspaces.find(
                          (item) => item.id === event.target.value,
                        )!,
                      ),
                    )
                  }
                >
                  <option value="" disabled>
                    Select workspace
                  </option>
                  {workspaces.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <form onSubmit={createWorkspace}>
                <h3>Create a workspace</h3>
                <label>
                  Workspace name
                  <input name="name" required maxLength={100} />
                </label>
                <label>
                  Seat limit
                  <input
                    name="seats"
                    type="number"
                    min={3}
                    max={50}
                    defaultValue={3}
                    required
                  />
                </label>
                <button disabled={busy}>Create workspace</button>
              </form>
              <form onSubmit={acceptInvitation}>
                <h3>Have an invitation?</h3>
                <label>
                  Invitation link
                  <input
                    name="link"
                    type="url"
                    required
                    defaultValue={
                      typeof window !== "undefined" &&
                      new URLSearchParams(window.location.search).has(
                        "invitation",
                      )
                        ? window.location.href
                        : ""
                    }
                  />
                </label>
                <button disabled={busy}>Accept invitation</button>
              </form>
            </section>
            <section className="panel">
              <h2>2. Choose a dataset</h2>
              <p>
                A dataset groups retained uploads of the same business table.
              </p>
              {workspace ? (
                <>
                  <label>
                    Dataset
                    <select
                      aria-label="Dataset"
                      value={dataset}
                      disabled={busy}
                      onChange={(event) => {
                        const id = event.target.value;
                        setDataset(id);
                        setProfileUpload("");
                        setUploads([]);
                        void run(async () =>
                          setUploads(
                            await request<Upload[]>(
                              `/workspaces/${workspace.id}/datasets/${id}/uploads`,
                            ),
                          ),
                        );
                      }}
                    >
                      <option value="" disabled>
                        Select dataset
                      </option>
                      {datasets.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <h3>Explore sample data</h3>
                  <p>
                    Fictional finance, sales and inventory examples, version 1.
                    Each creates a separate dataset in this workspace.
                  </p>
                  {["finance", "sales", "inventory"].map((kind) => (
                    <button
                      key={kind}
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const stored = await request<
                            Upload & { dataset_id: string }
                          >(`/workspaces/${workspace.id}/samples/${kind}-v1`, {
                            method: "POST",
                          });
                          setDatasets(
                            await request<Dataset[]>(
                              `/workspaces/${workspace.id}/datasets`,
                            ),
                          );
                          setDataset(stored.dataset_id);
                          setUploads([stored]);
                          setProfileUpload(stored.id);
                          setMessage(
                            "Sample ready. Review its profile and try previewing cleaning changes below.",
                          );
                        })
                      }
                    >
                      Try {kind} sample
                    </button>
                  ))}
                  <form onSubmit={createDataset}>
                    <label>
                      New dataset name
                      <input name="name" required maxLength={100} />
                    </label>
                    <button disabled={busy}>Create dataset</button>
                  </form>
                </>
              ) : (
                <p>Create or join a workspace first.</p>
              )}
            </section>
          </div>
          {workspace && (
            <section className="panel">
              <h2>3. Upload your file</h2>
              <p>
                CSV in UTF-8 or XLSX with one sheet, up to 20 MiB. Use unique
                headers, values only, and no merged cells. Maximum 100,000 rows,
                1,000 columns, and 1,000,000 cells including the header.
              </p>
              <form onSubmit={uploadFile}>
                <label>
                  CSV or Excel file
                  <input
                    key={workspace.id}
                    type="file"
                    accept=".csv,.xlsx"
                    required
                    disabled={!dataset || busy}
                    onChange={(event) =>
                      setFile(event.target.files?.[0] ?? null)
                    }
                  />
                </label>
                <button disabled={!dataset || !file || busy}>
                  {busy ? "Validating and storing…" : "Upload file"}
                </button>
              </form>
              {!dataset && <p>Choose a dataset before uploading.</p>}
              <h3>Retained uploads</h3>
              {uploads.length ? (
                <div className="tableScroll">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">File</th>
                        <th scope="col">Size</th>
                        <th scope="col">Rows</th>
                        <th scope="col">Columns</th>
                        <th scope="col">State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {uploads.map((item) => (
                        <tr key={item.id}>
                          <td>{item.filename}</td>
                          <td>{item.size.toLocaleString()} bytes</td>
                          <td>{item.row_count}</td>
                          <td>{item.column_count}</td>
                          <td>
                            {item.status === "stored"
                              ? "Validated and stored"
                              : item.status}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>No uploads in the selected dataset yet.</p>
              )}
              {uploads.length > 0 && (
                <label>
                  Profile upload
                  <select
                    value={profileUpload}
                    disabled={busy}
                    onChange={(event) => setProfileUpload(event.target.value)}
                  >
                    <option value="">Choose an upload to inspect</option>
                    {uploads.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.filename}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </section>
          )}
          {workspace && dataset && profileUpload && (
            <ProfilePanel
              key={`${workspace.id}/${dataset}/${profileUpload}`}
              root={`/workspaces/${workspace.id}/datasets/${dataset}/uploads/${profileUpload}`}
              request={request}
            />
          )}
          {workspace && manager && (
            <section className="panel">
              <h2>Workspace usage</h2>
              <button
                disabled={busy}
                onClick={() =>
                  void run(async () =>
                    setUsage(
                      await request(`/workspaces/${workspace.id}/usage`),
                    ),
                  )
                }
              >
                Refresh usage
              </button>
              {usage && (
                <p>
                  {usage.active_seats} of {usage.seat_limit} seats used ·{" "}
                  {usage.uploads} uploads ·{" "}
                  {usage.storage_bytes.toLocaleString()} bytes retained
                </p>
              )}
            </section>
          )}
          {workspace && (
            <section className="panel">
              <h2>Team · {workspace.name}</h2>
              <p>
                {members.length} active members · {workspace.seat_limit} seats.
                Pending invitations reserve seats until they expire or are
                revoked.
              </p>
              <ul className="memberList">
                {members.map((member) => (
                  <li key={member.user_id}>
                    <span>
                      {member.email} · {member.role}
                    </span>
                    {manager &&
                      member.role !== "owner" &&
                      (role === "owner" || member.role !== "admin") && (
                        <button
                          disabled={busy}
                          type="button"
                          onClick={() =>
                            void run(async () => {
                              await request(
                                `/workspaces/${workspace.id}/members/${member.user_id}`,
                                { method: "DELETE" },
                              );
                              setMembers(
                                await request<Member[]>(
                                  `/workspaces/${workspace.id}/members`,
                                ),
                              );
                              setMessage(
                                "Member removed. The seat is available.",
                              );
                            })
                          }
                        >
                          Remove {member.email}
                        </button>
                      )}
                  </li>
                ))}
              </ul>
              {role === "owner" && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    const seat_limit = Number(
                      new FormData(event.currentTarget).get("limit"),
                    );
                    void run(async () => {
                      await request(
                        `/workspaces/${workspace.id}/seats`,
                        json("PATCH", { seat_limit }),
                      );
                      setWorkspace({ ...workspace, seat_limit });
                      setWorkspaces(await request<Workspace[]>("/workspaces"));
                      setMessage("Seat limit updated.");
                    });
                  }}
                >
                  <label>
                    Update seat limit
                    <input
                      name="limit"
                      type="number"
                      min={3}
                      max={50}
                      defaultValue={workspace.seat_limit}
                      key={workspace.id}
                      required
                    />
                  </label>
                  <button disabled={busy}>Save seat limit</button>
                </form>
              )}
              {manager && (
                <>
                  <form onSubmit={inviteMember}>
                    <h3>Invite a teammate</h3>
                    <label>
                      Teammate email
                      <input type="email" name="email" required />
                    </label>
                    <label>
                      Role
                      <select name="role">
                        <option value="member">Member</option>
                        {role === "owner" && (
                          <option value="admin">Admin</option>
                        )}
                      </select>
                    </label>
                    <button disabled={busy}>Create invitation</button>
                  </form>
                  <h3>Invitations</h3>
                  {invitations.length ? (
                    <ul className="memberList">
                      {invitations.map((item) => (
                        <li key={item.id}>
                          <span>
                            {item.email} ·{" "}
                            {item.status === "pending" &&
                            Date.parse(item.expires_at) <= now
                              ? "expired"
                              : item.status}{" "}
                            · {item.role}
                          </span>
                          {item.status === "pending" &&
                            Date.parse(item.expires_at) > now && (
                              <div>
                                <button
                                  disabled={busy}
                                  onClick={() =>
                                    void run(async () => {
                                      const link = `${window.location.origin}/workspace?workspace=${workspace.id}&invitation=${item.id}`;
                                      if (!navigator.clipboard) {
                                        setMessage(
                                          `Copy this invitation link: ${link}`,
                                        );
                                        return;
                                      }
                                      await navigator.clipboard.writeText(link);
                                      setMessage(
                                        "Invitation link copied. Share it with the invited teammate.",
                                      );
                                    })
                                  }
                                >
                                  Copy link for {item.email}
                                </button>
                                <button
                                  disabled={busy}
                                  onClick={() =>
                                    void run(async () => {
                                      await request(
                                        `/workspaces/${workspace.id}/invitations/${item.id}`,
                                        { method: "DELETE" },
                                      );
                                      setInvitations(
                                        await request<Invitation[]>(
                                          `/workspaces/${workspace.id}/invitations`,
                                        ),
                                      );
                                      setMessage(
                                        "Invitation revoked. The reserved seat is available.",
                                      );
                                    })
                                  }
                                >
                                  Revoke {item.email}
                                </button>
                              </div>
                            )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>No invitations yet.</p>
                  )}
                </>
              )}
            </section>
          )}
        </>
      )}
      <footer>
        <span>ExecPlus · Secure ingestion foundation</span>
        <Link href="/">Project overview</Link>
      </footer>
    </main>
  );
}
