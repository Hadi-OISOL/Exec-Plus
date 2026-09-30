/* Use case: Provides the interactive data exploration workspace.
What it does: Connects uploads, verified insights, conversations, preparation and team administration. */

"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import type { FormEvent } from "react";

import { ActivationPanel } from "./activation-panel";
import { KnowledgePanel } from "./knowledge-panel";
import type { ChatHandle } from "./ask-panel";
import { CatalogPanel } from "./catalog-panel";
import { DatasetMap, Icon } from "./explore-components";
import { AskPanel } from "./ask-panel";
import { DashboardPanel } from "./dashboard-panel";
import { SavedPanel } from "./saved-panel";
import { ProfilePanel } from "./profile-panel";
import { UnderstandingPanel, domains } from "./understanding-panel";
import { RefreshPanel } from "./refresh-panel";
import { StudiesPanel } from "./studies-panel";
import { OrganizationPanel } from "./organization-panel";

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
  const [section, setSection] = useState("overview");
  const chat = useRef<ChatHandle>(null);
  const [revisionTick, setRevisionTick] = useState(0);
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
  const [uploadDomain, setUploadDomain] = useState("auto");
  const [uploadGoal, setUploadGoal] = useState("");
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
    setUploadDomain("auto");
    setUploadGoal("");
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
    if (nextDatasets.length) {
      await selectDataset(selected.id, nextDatasets[0].id);
    } else setSection("data");
    const nextRole = nextMembers.find(
      (member) => member.user_id === actorId,
    )?.role;
    if (nextRole === "owner" || nextRole === "admin") {
      setInvitations(await request<Invitation[]>(`${prefix}/invitations`));
    }
  }

  async function selectDataset(workspaceId: string, datasetId: string) {
    setDataset(datasetId);
    setProfileUpload("");
    setUploads([]);
    const available = await request<Upload[]>(
      `/workspaces/${workspaceId}/datasets/${datasetId}/uploads`,
    );
    setUploads(available);
    setProfileUpload(available[0]?.id ?? "");
    setSection(available.length ? "overview" : "data");
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const current = await request<User>("/auth/me");
      setUser(current);
      const available = await request<Workspace[]>("/workspaces");
      setWorkspaces(available);
      const params = new URLSearchParams(window.location.search);
      const selected =
        available.find((item) => item.id === params.get("workspace")) ??
        available[0];
      if (selected) {
        await selectWorkspace(selected, current.id);
        if (params.get("saved")) {
          const item = await request<{ dataset_id: string; upload_id: string }>(
            `/workspaces/${selected.id}/saved-items/${encodeURIComponent(params.get("saved")!)}`,
          );
          setDataset(item.dataset_id);
          setUploads(
            await request<Upload[]>(
              `/workspaces/${selected.id}/datasets/${item.dataset_id}/uploads`,
            ),
          );
          setProfileUpload(item.upload_id);
          setSection("saved");
        }
      } else {
        setWorkspace(null);
        setSection("team");
      }
      setMessage(
        selected ? "" : "Create a workspace or accept an invitation to begin.",
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
      setSection("team");
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
      setSection("data");
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
      if (!/\.(csv|xlsx)$/i.test(file.name))
        throw new Error("Choose a CSV or XLSX file.");
      let targetDataset = dataset;
      if (!targetDataset) {
        const created = await request<Dataset>(
          `/workspaces/${workspace!.id}/datasets`,
          json("POST", {
            name: file.name.replace(/\.[^.]+$/, "").slice(0, 100) || "My data",
          }),
        );
        targetDataset = created.id;
        setDataset(created.id);
        setDatasets(
          await request<Dataset[]>(`/workspaces/${workspace!.id}/datasets`),
        );
      }
      const mime = file.name.toLowerCase().endsWith(".csv")
        ? "text/csv"
        : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const prefix = `/workspaces/${workspace!.id}/datasets/${targetDataset}/uploads`;
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
      setSection("overview");
      setMessage(
        `${stored.filename} uploaded successfully. Original file retained; structure validated.`,
      );
      setFile(null);
      form.reset();
      if (uploadDomain !== "auto" || uploadGoal.trim()) {
        try {
          await request(
            `/workspaces/${workspace!.id}/datasets/${targetDataset}/preferences`,
            json("POST", { domain_hint: uploadDomain, goal: uploadGoal }),
          );
          setRevisionTick((value) => value + 1);
        } catch {
          setMessage(
            "File uploaded successfully. Your optional context could not be saved; add it under Data understanding.",
          );
        }
      }
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

  const selectedUpload = uploads.find((item) => item.id === profileUpload);
  const root =
    workspace && dataset && profileUpload
      ? `/workspaces/${workspace.id}/datasets/${dataset}/uploads/${profileUpload}`
      : "";
  const sections = [
    { id: "overview", name: "Overview" },
    { id: "data", name: "Data library" },
    { id: "prepare", name: "Prepare data" },
    { id: "documents", name: "Documents" },
    { id: "saved", name: "Saved work" },
    { id: "studies", name: "Studies & dashboards" },
    { id: "refresh", name: "Refresh & alerts" },
    { id: "team", name: "Team & settings" },
  ];
  return (
    <main
      className={`workspaceApp workbench ${user ? "isSignedIn" : "isSignedOut"}`}
    >
      <aside className="workbenchRail">
        <Link className="brand" href="/">
          <span className="brandMark">
            E<span>+</span>
          </span>
          <span>
            ExecPlus<small>YOUR DATA. CLEARER.</small>
          </span>
        </Link>
        <div className="railCaption">WORKSPACE</div>
        <nav aria-label="Workspace navigation">
          {sections.map((item) => (
            <button
              type="button"
              key={item.id}
              disabled={!user || busy}
              aria-current={section === item.id ? "page" : undefined}
              onClick={() => setSection(item.id)}
            >
              <Icon name={item.id} />
              <span>{item.name}</span>
              {section === item.id && <span className="navActiveDot" />}
            </button>
          ))}
        </nav>
        <div className="railNote">
          <Icon name="check" />
          <strong>Every answer has a source.</strong>
          <p>Explore the evidence behind your business numbers.</p>
          <span>Private demo</span>
        </div>
      </aside>
      <div className="workbenchBody">
        <header className="workbenchTop">
          <div>
            <span className="topBreadcrumb">
              Workspace / {sections.find((item) => item.id === section)?.name}
            </span>
            <span className="privateBadge">
              <span className="liveDot" /> Private workspace
            </span>
          </div>
          {user && (
            <div className="sessionBar">
              <span className="userIdentity">
                <span className="userAvatar">
                  {user.email.slice(0, 1).toUpperCase()}
                </span>
                <span>Signed in as {user.email}</span>
              </span>
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
          )}
        </header>
        <div className="workbenchContent">
          <header className="workspaceHeader">
            <div>
              <p className="eyebrow">YOUR DECISION SPACE</p>
              <h1>
                {!user
                  ? "Meet your data."
                  : section === "overview"
                    ? "A clearer picture."
                    : sections.find((item) => item.id === section)?.name}
              </h1>
              <p>
                {section === "overview"
                  ? "From raw data to answers you can act on."
                  : "Everything you need to explore, prepare and share your data."}
              </p>
            </div>
            {user && (
              <button
                type="button"
                className="uploadShortcut"
                disabled={busy}
                onClick={() => setSection("data")}
              >
                <Icon name="upload" /> Add data
              </button>
            )}
          </header>
          <div
            aria-live="polite"
            role="status"
            className={`notice ${!busy && !message ? "noticeEmpty" : ""}`}
          >
            {busy ? "Working…" : message}
          </div>
          {error && (
            <p role="alert" aria-label="Request error" className="errorNotice">
              {error}
            </p>
          )}
          {!user ? (
            <section className="panel loginPanel">
              <h2>Sign in</h2>
              <p>
                Use the development session token provided by your local
                operator. Sessions expire after eight hours.
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
              {workspace && (
                <section className="datasetToolbar" aria-label="Selected data">
                  <label>
                    Current workspace
                    <select
                      value={workspace.id}
                      disabled={busy}
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
                      {workspaces.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Dataset
                    <select
                      aria-label="Dataset"
                      value={dataset}
                      disabled={busy || !datasets.length}
                      onChange={(event) =>
                        void run(() =>
                          selectDataset(workspace.id, event.target.value),
                        )
                      }
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
                  <label>
                    Profile upload
                    <select
                      value={profileUpload}
                      disabled={busy || !uploads.length}
                      onChange={(event) => setProfileUpload(event.target.value)}
                    >
                      <option value="" disabled>
                        Select upload
                      </option>
                      {uploads.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.filename}
                        </option>
                      ))}
                    </select>
                  </label>
                  {selectedUpload && (
                    <span className="sourceStats">
                      <strong>
                        {selectedUpload.row_count.toLocaleString()}
                      </strong>{" "}
                      source rows
                      <span>
                        {selectedUpload.sample_id
                          ? "Fictional sample"
                          : "Your upload"}
                      </span>
                    </span>
                  )}
                </section>
              )}
              <div hidden={section !== "data"} className="dataLibraryGrid">
                {" "}
                <section className="panel">
                  <h2>Data library</h2>
                  <p>
                    A dataset groups retained uploads of the same business
                    table.
                  </p>
                  {workspace ? (
                    <>
                      <CatalogPanel
                        key={workspace.id}
                        workspaceId={workspace.id}
                        request={request}
                        select={async (id) => {
                          await selectDataset(workspace.id, id);
                          setSection("overview");
                        }}
                      />
                      <h3>Explore sample data</h3>
                      <p>
                        Fictional city sales, finance and inventory examples,
                        version 1. Each creates a separate dataset in this
                        workspace.
                      </p>
                      {["cities", "finance", "sales", "inventory"].map(
                        (kind) => (
                          <button
                            key={kind}
                            disabled={busy}
                            onClick={() =>
                              void run(async () => {
                                const stored = await request<
                                  Upload & { dataset_id: string }
                                >(
                                  `/workspaces/${workspace.id}/samples/${kind}-v1`,
                                  {
                                    method: "POST",
                                  },
                                );
                                setDatasets(
                                  await request<Dataset[]>(
                                    `/workspaces/${workspace.id}/datasets`,
                                  ),
                                );
                                setDataset(stored.dataset_id);
                                setUploads([stored]);
                                setProfileUpload(stored.id);
                                setSection("overview");
                                setMessage(
                                  "Sample ready. Review its profile and try previewing cleaning changes below.",
                                );
                              })
                            }
                          >
                            Try {kind} sample
                          </button>
                        ),
                      )}
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
                {workspace && (
                  <section className="panel">
                    <h2>Upload a file</h2>
                    <p>
                      CSV in UTF-8 or XLSX with one sheet, up to 20 MiB. Use
                      unique headers, values only, and no merged cells. Maximum
                      100,000 rows, 1,000 columns, and 1,000,000 cells including
                      the header.
                    </p>
                    <form onSubmit={uploadFile}>
                      <label>
                        What is this data about? (optional)
                        <select
                          disabled={busy}
                          value={uploadDomain}
                          onChange={(event) =>
                            setUploadDomain(event.target.value)
                          }
                        >
                          {domains.map((item) => (
                            <option key={item} value={item}>
                              {item === "auto" ? "Detect automatically" : item}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        What would you like to understand? (private, optional)
                        <input
                          disabled={busy}
                          value={uploadGoal}
                          maxLength={500}
                          onChange={(event) =>
                            setUploadGoal(event.target.value)
                          }
                        />
                      </label>
                      <label>
                        CSV or Excel file
                        <input
                          key={workspace.id}
                          type="file"
                          accept=".csv,.xlsx"
                          required
                          disabled={busy}
                          onChange={(event) =>
                            setFile(event.target.files?.[0] ?? null)
                          }
                        />
                      </label>
                      <button disabled={!file || busy}>
                        {busy ? "Validating and storing…" : "Upload file"}
                      </button>
                    </form>
                    {!dataset && (
                      <p>A new dataset will be created from your filename.</p>
                    )}
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
                  </section>
                )}
              </div>
              <div hidden={section !== "team"}>
                {" "}
                <section className="panel">
                  <h2>Your workspaces</h2>
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
                      {members.length} active members · {workspace.seat_limit}{" "}
                      seats. Pending invitations reserve seats until they expire
                      or are revoked.
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
                            setWorkspaces(
                              await request<Workspace[]>("/workspaces"),
                            );
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
                                            await navigator.clipboard.writeText(
                                              link,
                                            );
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
              </div>
              {workspace && section === "team" && (
                <OrganizationPanel
                  key={workspace.id}
                  workspaceId={workspace.id}
                  actorId={user.id}
                  owner={role === "owner"}
                  request={request}
                  onSelect={(id) => {
                    const selected = workspaces.find((item) => item.id === id);
                    if (selected) void run(() => selectWorkspace(selected));
                  }}
                />
              )}
              {root ? (
                <>
                  <div hidden={section !== "overview"}>
                    <UnderstandingPanel
                      key={`understanding-${root}-${revisionTick}`}
                      root={root}
                      request={request}
                      onChange={() => setRevisionTick((value) => value + 1)}
                    />
                    <DatasetMap
                      key={`map-${root}-${revisionTick}`}
                      root={root}
                      filename={selectedUpload?.filename ?? "Selected upload"}
                      request={request}
                      onQuestion={(text) => chat.current?.ask(text)}
                    />
                    <div className="exploreLayout">
                      <div className="insightCanvas">
                        <DashboardPanel
                          key={`dashboard-${root}-${revisionTick}`}
                          root={root}
                          request={request}
                        />
                        <ActivationPanel
                          key={`insights-${root}-${revisionTick}`}
                          root={root}
                          request={request}
                        />
                      </div>
                      <AskPanel
                        ref={chat}
                        key={`chat-${root}-${revisionTick}`}
                        root={root}
                        request={request}
                        filename={selectedUpload?.filename ?? "Selected upload"}
                      />
                    </div>
                  </div>
                  {section === "prepare" && (
                    <ProfilePanel
                      onRevisionChange={() =>
                        setRevisionTick((value) => value + 1)
                      }
                      key={root}
                      root={root}
                      request={request}
                    />
                  )}
                  {section === "documents" && (
                    <KnowledgePanel key={root} root={root} request={request} />
                  )}
                  {section === "saved" && (
                    <SavedPanel key={root} root={root} request={request} />
                  )}
                  {section === "refresh" && (
                    <RefreshPanel
                      key={`refresh-${root}-${revisionTick}`}
                      root={root}
                      request={request}
                      onReview={() => setSection("overview")}
                      onActivated={async (id) => {
                        const available = await request<Upload[]>(
                          `${root.split("/uploads/")[0]}/uploads`,
                        );
                        setUploads(available);
                        setProfileUpload(id);
                        setRevisionTick((value) => value + 1);
                      }}
                    />
                  )}
                  {section === "studies" && (
                    <StudiesPanel
                      key={`studies-${root}-${revisionTick}`}
                      root={root}
                      request={request}
                      actorId={user.id}
                      onReview={() => setSection("overview")}
                    />
                  )}
                </>
              ) : (
                !["team", "data"].includes(section) && (
                  <section className="emptyWorkspace">
                    <div className="emptyOrbit">
                      <Icon name="data" size={44} />
                      <span />
                      <span />
                    </div>
                    <h2>Your next insight starts with a file.</h2>
                    <p>
                      Upload a CSV or Excel file, or try a fictional sample.
                      We&apos;ll map its columns and build your first overview.
                    </p>
                    <button
                      type="button"
                      onClick={() => setSection(workspace ? "data" : "team")}
                    >
                      {workspace
                        ? "Explore data options"
                        : "Create a workspace"}
                      <Icon name="arrow" />
                    </button>
                    <div className="emptyFlow">
                      Upload <Icon name="arrow" size={16} /> Explore{" "}
                      <Icon name="arrow" size={16} /> Ask
                    </div>
                  </section>
                )
              )}
            </>
          )}
          <footer>
            <span>ExecPlus · Clarity backed by evidence</span>
            <Link href="/">About this demo</Link>
          </footer>
        </div>
      </div>
    </main>
  );
}
