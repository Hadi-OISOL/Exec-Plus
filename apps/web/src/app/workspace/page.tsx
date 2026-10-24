/* Use case: Provides the interactive data exploration workspace.
What it does: Connects uploads, verified insights, conversations, preparation and team administration. */

"use client";

import { allowedExportPath } from "./export-path";
import { WorkspaceSelect } from "./workspace-select";
import { AccountAccess } from "./account-access";
import { AccountSecurity, InvitationIdentityApproval } from "./account-security";
import { OnboardingGuide } from "./onboarding-guide";
import type { ApiRequest } from "./profile-panel";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import type { FormEvent } from "react";
import type { SheetChoice } from "./google-sheets-import";
import type { ConnectorChoice } from "./connectors-panel";

import type { ChatHandle } from "./ask-panel";
import { CatalogPanel } from "./catalog-panel";
import { DatasetMap, Icon } from "./explore-components";
import { AskPanel } from "./ask-panel";
import { DatasetAccessNotice } from "./dataset-access-notice";
import { UsageNotice } from "./usage-notice";
import { ExportDownloadContext, type ExportDownload } from "./result-export-actions";
import { UnderstandingPanel, domains } from "./understanding-panel";
import { DiscoveryPanel } from "./discovery-panel";
import type { StaffRole } from "./support-panel";
import { AnalyticsHome } from "./analytics-home";
import { WorkspaceLoading } from "./workspace-loading";
import { ThemeControl } from "../theme-control";

const loadingView = () => <WorkspaceLoading />;
const SourcesPanel = dynamic(
  () => import("./sources-panel").then(module => module.SourcesPanel),
  { loading: loadingView },
);
const IntegrationsPanel = dynamic(
  () => import("./integrations-panel").then(module => module.IntegrationsPanel),
  { loading: loadingView },
);
const DatasetAccessPanel = dynamic(
  () => import("./dataset-access-panel").then(module => module.DatasetAccessPanel),
  { loading: loadingView },
);
const AgentMemoryPanel = dynamic(
  () => import("./agent-memory-panel").then(module => module.AgentMemoryPanel),
  { loading: loadingView },
);
const GuidedReview = dynamic(
  () => import("./guided-review").then(module => module.GuidedReview),
  { loading: loadingView },
);
const ConnectorsPanel = dynamic(
  () => import("./connectors-panel").then(module => module.ConnectorsPanel),
  { loading: loadingView },
);
const GoogleSheetsImport = dynamic(
  () => import("./google-sheets-import").then(module => module.GoogleSheetsImport),
  { loading: loadingView },
);
const DataBriefReview = dynamic(
  () => import("./data-brief-review").then(module => module.DataBriefReview),
  { loading: loadingView },
);
const ActivationPanel = dynamic(
  () => import("./activation-panel").then((module) => module.ActivationPanel),
  { loading: loadingView },
);
const KnowledgePanel = dynamic(
  () => import("./knowledge-panel").then((module) => module.KnowledgePanel),
  { loading: loadingView },
);
const DashboardPanel = dynamic(
  () => import("./dashboard-panel").then((module) => module.DashboardPanel),
  { loading: loadingView },
);
const SavedPanel = dynamic(
  () => import("./saved-panel").then((module) => module.SavedPanel),
  { loading: loadingView },
);
const ProfilePanel = dynamic(
  () => import("./profile-panel").then((module) => module.ProfilePanel),
  { loading: loadingView },
);
const RefreshPanel = dynamic(
  () => import("./refresh-panel").then((module) => module.RefreshPanel),
  { loading: loadingView },
);
const StudiesPanel = dynamic(
  () => import("./studies-panel").then((module) => module.StudiesPanel),
  { loading: loadingView },
);
const ConsolidationPanel = dynamic(
  () => import("./consolidation-panel").then(module => module.ConsolidationPanel),
);
const OrganizationPanel = dynamic(
  () =>
    import("./organization-panel").then((module) => module.OrganizationPanel),
  { loading: loadingView },
);
const SourceDetails = dynamic(
  () => import("./source-details").then((module) => module.SourceDetails),
  { loading: loadingView },
);
const ForecastPanel = dynamic(
  () => import("./forecast-panel").then((module) => module.ForecastPanel),
  { loading: loadingView },
);
const DecisionPanel = dynamic(
  () => import("./decision-panel").then((module) => module.DecisionPanel),
  { loading: loadingView },
);
const AuditPanel = dynamic(
  () => import("./audit-panel").then((module) => module.AuditPanel),
  { loading: loadingView },
);
const AdminPanel = dynamic(
  () => import("./admin-panel").then((module) => module.AdminPanel),
  { loading: loadingView },
);
const SupportPanel = dynamic(
  () => import("./support-panel").then((module) => module.SupportPanel),
  { loading: loadingView },
);
const UsagePanel = dynamic(
  () => import("./usage-panel").then((module) => module.UsagePanel),
  { loading: loadingView },
);

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const googleFailures: Record<string, string> = {
  oauth_state_invalid: "This sign-in expired or was already used. Please try again.",
  native_account_requires_password: "Use password sign-in for this existing account.",
  google_denied: "Google sign-in was cancelled.",
  google_state_invalid: "The Google sign-in expired. Please try again.",
  google_identity_invalid: "Google could not confirm your identity.",
  google_exchange_failed: "Google could not complete the request. Please try again.",
  google_wrong_account: "Choose the Google account that matches your Syntelio email.",
  google_scope_missing: "Allow Syntelio to open the sheets you choose, then try again.",
  connector_denied: "The connection was cancelled.",
  connector_state_invalid: "The connection expired. Please try again.",
  connector_credentials_rejected: "The platform did not accept the sign-in.",
  connector_no_refresh: "The platform did not return a lasting connection. Try again.",
  connector_forbidden: "That account is not allowed to read this data.",
  connector_invalid_request: "The platform could not complete the request.",
  connector_unavailable: "The platform is unavailable. Try again shortly.",
};
function oauthFailure(code: string): string {
  return Object.hasOwn(googleFailures, code)
    ? googleFailures[code]
    : "Sign-in could not be completed. Please try again.";
}
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
  size: number | null;
  access_limited?: boolean;
  row_count: number;
  column_count: number;
  status: string;
};
type User = { id: string; email: string };

export default function WorkspacePage() {
  const [section, setSection] = useState("overview");
  const [nativeAccount, setNativeAccount] = useState(false);
  const [savedSelection, setSavedSelection] = useState<{ root: string; id: string } | null>(null);
  const chat = useRef<ChatHandle>(null);
  const reviewDisclosure = useRef<HTMLDetailsElement>(null);
  const [revisionTick, setRevisionTick] = useState(0);
  const [guidedFor, setGuidedFor] = useState("");
  const [briefFor, setBriefFor] = useState("");
  const [briefManual, setBriefManual] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const oauthHandled = useRef(false);
  const oauthSessionRef = useRef<(sessionToken: string) => Promise<void>>(async () => undefined);
  const skippedBriefs = useRef(new Set<string>());
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [staffRole, setStaffRole] = useState<StaffRole>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [invitationError, setInvitationError] = useState("");
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [importReload, setImportReload] = useState<{ actor: string; workspace: string; dataset: string } | null>(null);
  const [profileUpload, setProfileUpload] = useState("");
  const [usage, setUsage] = useState<{
    active_seats: number;
    seat_limit: number;
    uploads: number;
    storage_bytes: number;
  } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploadTarget, setUploadTarget] = useState("new");
  const [uploadDomain, setUploadDomain] = useState("auto");
  const [uploadGoal, setUploadGoal] = useState("");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [toolSelection, setToolSelection] = useState<{root: string; tool: string; metric?: string; aggregation?: "avg" | "sum"; scenario_mode?: "daily_change"} | null>(null);
  const [starterQuestions, setStarterQuestions] = useState<string[]>([]);
  const [expert, setExpert] = useState(false);
  const [analysisIntent, setAnalysisIntent] = useState("descriptive");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [topQuestion, setTopQuestion] = useState("");
  const role = members.find((member) => member.user_id === user?.id)?.role;
  const manager = role === "owner" || role === "admin";
  const limitedUpload = uploads.find(item => item.id === profileUpload)?.access_limited === true;

  function reviewUnderstanding() {
    setSection("overview");
    setBriefFor("");
    setGuidedFor("");
    setReviewOpen(true);
    window.requestAnimationFrame(() =>
      reviewDisclosure.current?.scrollIntoView({
        block: "start",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      }),
    );
  }

  const authorizedResponse = useCallback(
    async function authorizedResponse(
      path: string,
      options: RequestInit = {},
      sessionToken: string = token,
    ): Promise<Response> {
      const response = await fetch(`${api}${path}`, {
        ...options,
        headers: sessionToken ? { Authorization: `Bearer ${sessionToken}`, ...options.headers } : { "X-ExecPlus-Request": "1", ...options.headers },
        credentials: options.credentials ?? (sessionToken ? "same-origin" : "include"),
        cache: "no-store",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        if (response.status === 401) {
          setGuidedFor("");
          setUser(null);
          setWorkspace(null);
          setWorkspaces([]);
          setMembers([]);
          setStaffRole(null);
          setSavedSelection(null);
          setSection("data");
        }
        throw Object.assign(
          new Error(
            body.error?.message ?? "The request failed. Please try again.",
          ),
          { status: response.status, code: body.error?.code },
        );
      }
      return response;
    },
    [token],
  );

  const request = useCallback(async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await authorizedResponse(path, options);
    return response.status === 204 ? (undefined as T) : response.json();
  }, [authorizedResponse]);

  const downloadExport = useCallback<ExportDownload>(async (path, format, signal, body) => {
    if (!allowedExportPath(path)) throw new Error("This download is unavailable.");
    const media = { pdf: "application/pdf", xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", csv: "application/zip", png: "image/png" }[format];
    const response = await authorizedResponse(path, { signal, ...(body ? { method: "POST", body: JSON.stringify(body) } : {}), headers: { Accept: media, ...(body ? { "Content-Type": "application/json" } : {}) } });
    if (!response.headers.get("Content-Type")?.toLowerCase().startsWith(media)) throw new Error("The server did not return the selected file type. Please try again.");
    const blob = await response.blob();
    if (signal.aborted) return;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const filename = response.headers.get("Content-Disposition")?.match(/filename="([a-zA-Z0-9.-]+)"/)?.[1];
    link.href = url; link.download = filename ?? `syntelio-result.${format === "csv" ? "zip" : format}`;
    document.body.appendChild(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
  }, [authorizedResponse]);
  const downloadPdf = useCallback((path: string, signal: AbortSignal) => downloadExport(path, "pdf", signal), [downloadExport]);

  function json(method: string, body: object): RequestInit {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    };
  }

  async function run(action: () => Promise<void>, propagate = false) {
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
      if (propagate) throw cause;
    } finally {
      setBusy(false);
    }
  }

  useLayoutEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [user?.id, section]);

  useEffect(() => {
    if (!profileUpload || !user || limitedUpload) return;
    let seen = skippedBriefs.current.has(profileUpload);
    try {
      seen = seen || Boolean(window.localStorage.getItem(`execplus.brief.${profileUpload}`));
    } catch {
      seen = skippedBriefs.current.has(profileUpload);
    }
    if (seen) return;
    let active = true;
    Promise.resolve().then(() => {
      if (active) setBriefFor(profileUpload);
    });
    return () => {
      active = false;
    };
  }, [profileUpload, user, limitedUpload]);

  function closeBrief(changed: boolean, finished: boolean) {
    if (finished) {
      try {
        window.localStorage.setItem(`execplus.brief.${profileUpload}`, "1");
      } catch {
        setGuidedFor("");
      }
    } else {
      skippedBriefs.current.add(profileUpload);
    }
    setBriefFor("");
    setBriefManual(false);
    setGuidedFor("");
    if (changed) setRevisionTick(value => value + 1);
  }

  function openBrief() {
    if (limitedUpload) {
      reviewUnderstanding();
      return;
    }
    setBriefManual(true);
    setReviewOpen(false);
    setGuidedFor("");
    setBriefFor(profileUpload);
    setSection("overview");
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${api}/auth/google/config`, { signal: controller.signal, cache: "no-store" })
      .then(response => (response.ok ? response.json() : { enabled: false }))
      .then(value => setGoogleEnabled(Boolean(value.enabled)))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    // Delay URL consumption so React's development effect replay cannot lose a return.
    Promise.resolve().then(async () => {
      if (!active || oauthHandled.current) return;
      oauthHandled.current = true;
      const fragment = new URLSearchParams(window.location.hash.slice(1));
      const query = new URLSearchParams(window.location.search);
      const exchange = query.get("oauth") === "complete";
      const failure = fragment.get("google_error") ?? query.get("oauth_error") ?? query.get("google_error") ?? query.get("connector_error");
      // Old bearer fragments and stored resume credentials are discarded, never adopted.
      try { window.sessionStorage.removeItem("execplus.resume"); } catch { /* Storage can be disabled. */ }
      const returnKeys = ["oauth", "oauth_error", "google", "google_error", "connector_connected", "connector_error", "connector"];
      const restore = async () => {
        const probe = await fetch(`${api}/auth/me`, { credentials: "include", headers: { "X-ExecPlus-Request": "1" }, cache: "no-store", signal: controller.signal }).catch(() => null);
        await probe?.text().catch(() => "");
        if (!active || probe?.status === 401) return;
        if (!probe?.ok) { setError("We could not restore your session. Check your connection and reload the page."); return; }
        setBusy(true);
        try { await oauthSessionRef.current(""); }
        catch (cause) { if (active && (cause as { status?: number }).status !== 401) setError("We could not restore your session. Check your connection and reload the page."); }
        finally { if (active) setBusy(false); }
      };
      if (!fragment.has("session") && !failure && !returnKeys.some(key => query.has(key))) return restore();
      for (const key of returnKeys) query.delete(key);
      const rest = query.toString();
      window.history.replaceState(null, "", window.location.pathname + (rest ? `?${rest}` : ""));
      if (!exchange) {
        if (!fragment.has("session")) await restore();
        if (failure && active) setError(oauthFailure(failure));
        return;
      }
      setBusy(true);
      setError("");
      setMessage("");
      try {
        const response = await fetch(`${api}/auth/oauth/exchange`, {
          method: "POST", credentials: "include", cache: "no-store",
          headers: { "Content-Type": "application/json" }, body: "{}", signal: controller.signal,
        });
        if (!response.ok) {
          if (active) setError("This sign-in expired or was already used. Please try again.");
          return;
        }
        const result: { token?: string; error?: string; provider?: string } = await response.json();
        if (!active) return;
        if (typeof result.token === "string" && result.token) {
          await oauthSessionRef.current(result.token);
          if (!active) return;
          if (result.provider && !result.error) {
            setSection("data");
            setMessage("Connected. Choose what to import.");
          }
        } else if (!result.error) {
          throw new Error("Sign-in could not be completed. Please try again.");
        }
        if (result.error) setError(oauthFailure(result.error));
      } catch {
        if (active) setError("Sign-in could not be completed. Please try again.");
      } finally {
        if (active) setBusy(false);
      }
    });
    return () => { active = false; controller.abort(); };
  }, []);

  useEffect(() => {
    oauthSessionRef.current = loadTokenSession;
  });

  useEffect(() => {
    if (!workspace || !manager || section !== "team") return;
    const controller = new AbortController();
    Promise.resolve()
      .then(() =>
        request<Invitation[]>(`/workspaces/${workspace.id}/invitations`, {
          signal: controller.signal,
        }),
      )
      .then((items) => {
        if (!controller.signal.aborted) setInvitations(items);
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setInvitationError(
            cause instanceof Error
              ? cause.message
              : "Invitations could not be loaded.",
          );
      });
    return () => controller.abort();
  }, [workspace, manager, section, request]);

  async function selectWorkspace(selected: Workspace, sessionRequest: ApiRequest = request) {
    setGuidedFor("");
    setBriefFor("");
    setBriefManual(false);
    setReviewOpen(false);
    setUploadTarget("new");
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
    setInvitationError("");
    setFile(null);
    const prefix = `/workspaces/${selected.id}`;
    const [nextDatasets, nextMembers] = await Promise.all([
      sessionRequest<Dataset[]>(`${prefix}/datasets`),
      sessionRequest<Member[]>(`${prefix}/members`),
    ]);
    setDatasets(nextDatasets);
    setMembers(nextMembers);
    if (nextDatasets.length) {
      await selectDataset(selected.id, nextDatasets[0].id, sessionRequest);
    } else setSection("data");
  }

  async function selectDataset(workspaceId: string, datasetId: string, sessionRequest: ApiRequest = request) {
    setGuidedFor("");
    setBriefFor("");
    setBriefManual(false);
    setSavedSelection(null);
    setAnalysisIntent("descriptive");
    setReviewOpen(false);
    setStarterQuestions([]);
    setUploadTarget("new");
    setDataset(datasetId);
    setProfileUpload("");
    setUploads([]);
    const available = await sessionRequest<Upload[]>(
      `/workspaces/${workspaceId}/datasets/${datasetId}/uploads`,
    );
    setUploads(available);
    setProfileUpload(available[0]?.id ?? "");
    setSection(available.length ? "overview" : "data");
  }

  async function loadSession(sessionRequest: ApiRequest) {
      const current = await sessionRequest<User>("/auth/me");
      const [available, access, account] = await Promise.all([
        sessionRequest<Workspace[]>("/workspaces"),
        sessionRequest<{ role: StaffRole }>("/admin/access"),
        sessionRequest<{ kind: string }>("/auth/account"),
      ]);
      setUser(current);
      setStaffRole(access.role);
      setNativeAccount(account.kind === "local_password");
      setWorkspaces(available);
      const params = new URLSearchParams(window.location.search);
      const selected =
        available.find((item) => item.id === params.get("workspace")) ??
        available[0];
      if (selected) {
        await selectWorkspace(selected, sessionRequest);
        if (params.get("saved")) {
          const item = await sessionRequest<{ dataset_id: string; upload_id: string }>(
            `/workspaces/${selected.id}/saved-items/${encodeURIComponent(params.get("saved")!)}`,
          );
          setDataset(item.dataset_id);
          setUploads(
            await sessionRequest<Upload[]>(
              `/workspaces/${selected.id}/datasets/${item.dataset_id}/uploads`,
            ),
          );
          setProfileUpload(item.upload_id);
          setSection("saved");
        }
      } else {
        setWorkspace(null);
        setSection("data");
      }
      setMessage(
        selected
          ? ""
          : "Start with a file. We’ll organize it and find a starting point for you.",
      );
  }

  async function finishImport(stored: Upload, workspaceId: string, datasetId: string, platform: string) {
    setImportReload(null);
    setUploads([]);
    setProfileUpload("");
    setGuidedFor("");
    setBriefFor("");
    setReviewOpen(false);
    setStarterQuestions([]);
    setUploadTarget("new");
    setAnalysisIntent("descriptive");
    try {
      const available = await request<Upload[]>(`/workspaces/${workspaceId}/datasets/${datasetId}/uploads`);
      setUploads(available);
    } catch {
      setSection("data");
      setMessage("Import saved, but the updated data could not be loaded. Reload saved data to continue.");
      setImportReload({ actor: user!.id, workspace: workspaceId, dataset: datasetId });
      return;
    }
    setProfileUpload(stored.id);
    setGuidedFor(stored.id);
    setBriefFor(stored.id);
    setSection("overview");
    setMessage(`${stored.filename} imported from ${platform}. Your first findings are being prepared below.`);
  }

  async function reloadImportedData() {
    if (!importReload || user?.id !== importReload.actor || workspace?.id !== importReload.workspace || dataset !== importReload.dataset) return;
    await run(async () => {
      await selectDataset(importReload.workspace, importReload.dataset);
      setImportReload(null);
      setMessage("Saved import loaded.");
    });
  }

  async function importGoogleSheet(choice: SheetChoice) {
    await run(async () => {
      let targetWorkspace = workspace;
      if (!targetWorkspace) {
        targetWorkspace = await request<Workspace>(
          "/workspaces",
          json("POST", { name: "My workspace", seat_limit: 3 }),
        );
        setWorkspace(targetWorkspace);
        setWorkspaces(await request<Workspace[]>("/workspaces"));
        setMembers(
          await request<Member[]>(`/workspaces/${targetWorkspace.id}/members`),
        );
      }
      let targetDataset = uploadTarget === "existing" ? dataset : "";
      if (!targetDataset) {
        const created = await request<Dataset>(
          `/workspaces/${targetWorkspace.id}/datasets`,
          json("POST", { name: choice.title.slice(0, 100) || "My data" }),
        );
        targetDataset = created.id;
        setDataset(created.id);
        setUploads([]);
        setProfileUpload("");
        setUploadTarget("existing");
        setDatasets(
          await request<Dataset[]>(`/workspaces/${targetWorkspace.id}/datasets`),
        );
      }
      const prefix = `/workspaces/${targetWorkspace.id}/datasets/${targetDataset}`;
      const stored = await request<Upload>(
        `${prefix}/google-sheets/import`,
        json("POST", {
          spreadsheet_id: choice.spreadsheetId,
          sheet_id: choice.sheetId,
        }),
      );
      await finishImport(stored, targetWorkspace.id, targetDataset, "Google Sheets");
    }, true);
  }

  async function importConnector(choice: ConnectorChoice) {
    await run(async () => {
      let targetWorkspace = workspace;
      if (!targetWorkspace) {
        targetWorkspace = await request<Workspace>(
          "/workspaces",
          json("POST", { name: "My workspace", seat_limit: 3 }),
        );
        setWorkspace(targetWorkspace);
        setWorkspaces(await request<Workspace[]>("/workspaces"));
        setMembers(
          await request<Member[]>(`/workspaces/${targetWorkspace.id}/members`),
        );
      }
      let targetDataset = uploadTarget === "existing" ? dataset : "";
      if (!targetDataset) {
        const created = await request<Dataset>(
          `/workspaces/${targetWorkspace.id}/datasets`,
          json("POST", { name: choice.title.slice(0, 100) || "My data" }),
        );
        targetDataset = created.id;
        setDataset(created.id);
        setUploads([]);
        setProfileUpload("");
        setUploadTarget("existing");
        setDatasets(
          await request<Dataset[]>(`/workspaces/${targetWorkspace.id}/datasets`),
        );
      }
      const prefix = `/workspaces/${targetWorkspace.id}/datasets/${targetDataset}`;
      const stored = await request<Upload>(
        `${prefix}/connectors/${choice.provider}/import`,
        json("POST", { source_id: choice.sourceId }),
      );
      await finishImport(stored, targetWorkspace.id, targetDataset, choice.platform);
    }, true);
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(() => loadSession(request));
  }

  async function loadTokenSession(sessionToken: string) {
    setToken(sessionToken);
    const sessionRequest: ApiRequest = async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
      const response = await authorizedResponse(path, options, sessionToken);
      return response.status === 204 ? (undefined as T) : response.json();
    };
    try { await loadSession(sessionRequest); }
    catch (cause) { clearSession(); throw cause; }
  }

  async function signInWithPassword(created: boolean, sessionToken: string) {
    await run(async () => {
      await loadTokenSession(sessionToken);
      if (created) setMessage("Welcome! Your private workspace is ready. Your setup guide is open — start by adding a CSV or Excel file below.");
    });
  }

  async function signOut() {
    await run(async () => {
      // shortcut: a failed revoke (offline, 404 or expired) still signs this browser out; the server session then ends at expiry.
      await request("/auth/logout", { method: "POST", credentials: "include" }).catch(() => undefined);
      clearSession();
    });
  }

  function clearSession() {
    setToken(""); setUser(null); setWorkspace(null); setWorkspaces([]); setDatasets([]); setDataset("");
    setMembers([]); setStaffRole(null); setSavedSelection(null); setInvitations([]); setUploads([]);
    setFile(null); setMessage(""); setError(""); setNativeAccount(false); setSection("data");
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
      setUploadTarget("existing");
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
      let targetWorkspace = workspace;
      if (!targetWorkspace) {
        targetWorkspace = await request<Workspace>(
          "/workspaces",
          json("POST", {
            name: "My workspace",
            seat_limit: 3,
          }),
        );
        setWorkspace(targetWorkspace);
        setWorkspaces(await request<Workspace[]>("/workspaces"));
        setMembers(
          await request<Member[]>(`/workspaces/${targetWorkspace.id}/members`),
        );
      }
      let targetDataset = uploadTarget === "existing" ? dataset : "";
      if (!targetDataset) {
        const created = await request<Dataset>(
          `/workspaces/${targetWorkspace.id}/datasets`,
          json("POST", {
            name: file.name.replace(/\.[^.]+$/, "").slice(0, 100) || "My data",
          }),
        );
        targetDataset = created.id;
        setDataset(created.id);
        setUploads([]);
        setProfileUpload("");
        setUploadTarget("existing");
        setDatasets(
          await request<Dataset[]>(
            `/workspaces/${targetWorkspace.id}/datasets`,
          ),
        );
      }
      const mime = file.name.toLowerCase().endsWith(".csv")
        ? "text/csv"
        : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      const prefix = `/workspaces/${targetWorkspace.id}/datasets/${targetDataset}/uploads`;
      const stored = await request<Upload>(
        `${prefix}?filename=${encodeURIComponent(file.name)}`,
        {
          method: "POST",
          headers: { "Content-Type": mime },
          body: file,
        },
      );
      let contextSaved = true;
      if (uploadDomain !== "auto" || uploadGoal.trim()) {
        try {
          await request(
            `/workspaces/${targetWorkspace.id}/datasets/${targetDataset}/preferences`,
            json("POST", { domain_hint: uploadDomain, goal: uploadGoal }),
          );
          setRevisionTick((value) => value + 1);
        } catch { contextSaved = false; }
      }
      setUploads(await request<Upload[]>(prefix));
      setProfileUpload(stored.id);
      setGuidedFor(stored.id);
      setBriefFor(stored.id);
      setReviewOpen(false);
      setStarterQuestions([]);
      setUploadTarget("new");
      setAnalysisIntent("descriptive");
      setSection("overview");
      setMessage(
        contextSaved ? `${stored.filename} is ready. Let’s check what it means together.` : "File uploaded successfully. Your optional context could not be saved; add it under Data understanding.",
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

  const selectedUpload = uploads.find((item) => item.id === profileUpload);
  const root =
    workspace && dataset && profileUpload
      ? `/workspaces/${workspace.id}/datasets/${dataset}/uploads/${profileUpload}`
      : "";
  const briefActive = Boolean(root && user && !limitedUpload && briefFor === profileUpload && !reviewOpen);
  const guidedActive = Boolean(root && user && !limitedUpload && guidedFor === profileUpload && !briefActive && !reviewOpen);
  const reviewing = ["overview", "ask"].includes(section) && (guidedActive || reviewOpen || (section === "overview" && briefActive && briefManual));
  const sections = [
    { id: "overview", name: "Overview", group: "Analyze" },
    { id: "ask", name: "Ask Syntelio", group: "Analyze" },
    { id: "search", name: "Search data", group: "Analyze" },
    { id: "forecasts", name: "Forecasts", group: "Analyze" },
    { id: "decisions", name: "Anomalies & decisions", group: "Analyze" },
    { id: "studies", name: "Studies & dashboards", group: "Library" },
    { id: "saved", name: "Saved work", group: "Library" },
    { id: "refresh", name: "Refresh & alerts", group: "Library" },
    { id: "data", name: "Data library", group: "Data" },
    { id: "prepare", name: "Prepare data", group: "Data" },
    { id: "documents", name: "Documents", group: "Data" },
    { id: "team", name: "Team & settings", group: "Workspace" },
    { id: "memory", name: "My memory", group: "More" },
    { id: "audit", name: "Audit history", group: "More" },
    ...(manager ? [{ id: "usage", name: "Usage & retention", group: "More" }] : []),
    { id: "support", name: "Support", group: "More" },
    ...(staffRole ? [{ id: "admin", name: "Admin console", group: "More" }] : []),
  ];
  const current = sections.find((item) => item.id === section);
  const moreVisible = moreOpen || current?.group === "More";
  const navButton = (item: { id: string; name: string }) => (
    <button
      type="button"
      key={item.id}
      disabled={!user || busy}
      aria-current={section === item.id ? "page" : undefined}
      onClick={() => navigate(item.id)}
    >
      <Icon name={item.id === "ask" ? "chat" : item.id === "search" ? "search" : item.id} size={18} />
      <span>{item.name}</span>
    </button>
  );
  function loadSample(kind: string) {
    if (!workspace) return;
    void run(async () => {
      const stored = await request<Upload & { dataset_id: string }>(`/workspaces/${workspace.id}/samples/${kind}-v1`, { method: "POST" });
      setDatasets(await request<Dataset[]>(`/workspaces/${workspace.id}/datasets`));
      setDataset(stored.dataset_id);
      setUploads([stored]);
      setProfileUpload(stored.id);
      setReviewOpen(false);
      setStarterQuestions([]);
      setAnalysisIntent("descriptive");
      setSection("overview");
      setMessage("Sample ready. Explore its findings or ask a question.");
    });
  }
  function navigate(next: string) {
    setToolSelection(null);
    setReviewOpen(false);
    setSection(next);
    setMessage("");
    setError("");
    setSavedSelection(null);
    if (next === "forecasts") setAnalysisIntent("predictive");
    if (next === "decisions") setAnalysisIntent("descriptive");
    if (next === "overview") setAnalysisIntent("descriptive");
  }
  function askFromHome(text: string) {
    setReviewOpen(false);
    setSection("ask");
    window.requestAnimationFrame(() => chat.current?.ask(text));
  }
  const analysisFocusControl = (
    <div className="analysisIntent">
      <WorkspaceSelect
        id="analysis-focus"
        label="Analysis focus"
        value={analysisIntent}
        disabled={busy}
        onValueChange={(value) => {
          setAnalysisIntent(value);
          setSection(value === "predictive" ? "forecasts" : value === "prescriptive" ? "decisions" : "overview");
        }}
        options={[
          { value: "descriptive", label: "Descriptive · understand actual data", description: "Explore recorded values, groups and patterns." },
          { value: "predictive", label: "Predictive · basic forecasts", description: "Estimate future periods when your data supports it." },
          { value: "all", label: "All supported · explore and forecast", description: "Explore your data and see available forecasting tools." },
          { value: "prescriptive", label: "Prescriptive · bounded budget allocation", description: "Compare allocations using your declared assumptions." },
        ]}
      />
      <p>
        {analysisIntent === "predictive"
          ? "Basic daily or monthly forecasting requires reviewed meanings and complete periods."
          : analysisIntent === "prescriptive" ? "Compare declared budget allocations with explicit per-unit costs, linear benefits and human review. No action runs automatically." : "Start with observed facts. Forecasting and unusual-value checks are optional; budget recommendations require declared assumptions."}
      </p>
    </div>
  );
  return (
    <ExportDownloadContext.Provider value={downloadExport}><main
      className={`workspaceApp workbench analyticsShell ${user ? "isSignedIn" : "isSignedOut"}`}
      data-section={section}
      data-reviewing={reviewing}
    >
      <aside className="workbenchRail">
        <Link className="brand" href="/">
          <span className="brandMark" aria-hidden="true">S</span>
          <span>Syntelio</span>
        </Link>
        <nav aria-label="Workspace navigation">
          {["Analyze", "Library", "Data"].map((group) => (
            <div className="navGroup" key={group}>
              <div className="railCaption">{group}</div>
              {sections.filter((item) => item.group === group).map(navButton)}
            </div>
          ))}
          <div className="navGroup">
            <div className="railCaption">Workspace</div>
            {sections.filter((item) => item.group === "Workspace").map(navButton)}
            <button type="button" className="navMoreToggle" aria-expanded={moreVisible} aria-controls="workspace-more-navigation" onClick={() => setMoreOpen((open) => !open)}>
              <Icon name="more" size={18} /><span>More</span>
            </button>
            <div id="workspace-more-navigation" className="navMoreItems" hidden={!moreVisible}>
              {sections.filter((item) => item.group === "More").map(navButton)}
            </div>
          </div>
        </nav>
      </aside>
      <div className="workbenchBody">
        <header className="workbenchTop">
          <span className="topBreadcrumb">
            {current?.group ?? "Syntelio"} <span aria-hidden="true">/</span> <strong>{current?.name}</strong>
          </span>
          {user && section !== "ask" && (
            <form className="topAsk" role="search" onSubmit={(event) => {
              event.preventDefault();
              const text = topQuestion.trim();
              if (!text) return;
              setTopQuestion("");
              if (root) askFromHome(text);
              else { navigate("data"); setMessage("Add a data file first, then ask your question."); }
            }}>
              <Icon name="sparkle" size={17} />
              <input
                aria-label="Ask anything about your data"
                placeholder={root ? "Ask anything about your data…" : "Add data to start asking…"}
                value={topQuestion}
                maxLength={500}
                onChange={(event) => setTopQuestion(event.target.value)}
              />
              <button type="submit" aria-label="Submit question" disabled={!topQuestion.trim()}><Icon name="arrow" size={16} /></button>
            </form>
          )}
          <div className="topActions">
            {user && <button className="headerSearch" type="button" aria-label="Search your data" title="Search your data" onClick={() => navigate("search")}>
              <Icon name="search" size={17} />
            </button>}
            <ThemeControl />
            {user && (
              <div className="sessionBar">
                <span className="userIdentity">
                  <span className="userAvatar" aria-hidden="true">
                    {user.email.slice(0, 1).toUpperCase()}
                  </span>
                  <span>Signed in as {user.email}</span>
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void signOut()}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </header>
        <div className="workbenchContent">
          <header className="workspaceHeader" hidden={Boolean(user && reviewing && ["overview", "ask"].includes(section))}>
            <div>
              <h1>
                {!user
                  ? "Meet your data."
                  : section === "overview" && selectedUpload ? selectedUpload.filename : current?.name}
              </h1>
              <p>
                {!user
                  ? "Sign in to explore, prepare and share your data."
                  : section === "overview" && selectedUpload
                    ? `${selectedUpload.row_count.toLocaleString()} ${selectedUpload.access_limited ? "rows in your view" : "rows"} · ${selectedUpload.column_count.toLocaleString()} columns · ${selectedUpload.sample_id ? "Fictional sample" : "Your upload"}`
                  : section === "overview"
                    ? "Explore, ask and build on what you discover."
                  : section === "memory"
                    ? "Your private preferences for clearer explanations."
                  : section === "prepare"
                    ? "Check your file, review its meaning and choose any changes."
                  : section === "ask"
                    ? "Follow a question, explore the answer, check the evidence."
                  : section === "forecasts"
                    ? "Look ahead with your data and clearly stated assumptions."
                  : section === "decisions"
                    ? "Explore unusual values and compare the choices available to you."
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
                <Icon name="upload" size={17} /> Add data
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
          {importReload && user?.id === importReload.actor && workspace?.id === importReload.workspace && dataset === importReload.dataset && (
            <button type="button" disabled={busy} onClick={() => void reloadImportedData()}>Reload saved data</button>
          )}
          {error && (
            <p role="alert" aria-label="Request error" className="errorNotice">
              {error}
            </p>
          )}
          {!user ? (
            <section className="panel loginPanel">
              <AccountAccess api={api} onSession={signInWithPassword} />
              {googleEnabled && (
                <form method="get" action={`${api}/auth/google/start`}>
                  <button type="submit" className="secondaryAction" disabled={busy}>
                    Continue with Google
                  </button>
                </form>
              )}
              {process.env.NEXT_PUBLIC_EXECPLUS_OPERATOR_SIGNIN === "1" && (
              <form onSubmit={signIn} className="operatorSession" aria-label="Operator session">
                <h3>Operator session</h3>
                <p>
                  For development: paste the session token from your local
                  operator. Sessions expire after eight hours.
                </p>
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
                <button className="secondaryAction" disabled={busy}>Sign in</button>
              </form>
              )}
            </section>
          ) : (
            <>
              {workspace && !["admin", "memory"].includes(section) && (
                <section className="datasetToolbar" aria-label="Selected data">
                  <label>
                    <span>Current workspace</span>
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
                  {datasets.length > 0 && <>
                  <label>
                    <span>Dataset</span>
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
                    <span>Profile upload</span>
                    <select
                      value={profileUpload}
                      disabled={busy || !uploads.length}
                      onChange={(event) => {
                        setProfileUpload(event.target.value);
                        setSavedSelection(null);
                        setStarterQuestions([]);
                        setReviewOpen(false);
                      }}
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
                  </>}
                  {["overview", "data", "team"].includes(section) && <OnboardingGuide key={`setup-${workspace.id}-${user.id}`} workspaceId={workspace.id} request={request} defaultOpen={nativeAccount} onNavigate={navigate} />}
                  {selectedUpload && section !== "overview" && (
                    <span className="sourceStats">
                      <strong>
                        {selectedUpload.row_count.toLocaleString()}
                      </strong>{" "}
                      {selectedUpload.access_limited ? "rows in your view" : "source rows"}
                      <span>
                        {selectedUpload.sample_id
                          ? "Fictional sample"
                          : "Your upload"}
                      </span>
                    </span>
                  )}
                </section>
              )}
              {workspace && manager && !["admin", "usage"].includes(section) && <UsageNotice workspaceId={workspace.id} view={section} request={request} />}
              {workspace && dataset && !["admin", "memory", "team"].includes(section) && <DatasetAccessNotice root={`/workspaces/${workspace.id}/datasets/${dataset}`} view={section} request={request} />}
              <div hidden={section !== "data"} className="dataLibraryGrid">
                <section
                  className="panel uploadStart"
                  aria-label="Add a data file"
                >
                  <div className="uploadIntroIcon">
                    <Icon name="upload" size={28} />
                  </div>
                  <p className="eyebrow">START WITH YOUR DATA</p>
                  <h2>Start with a file.</h2>
                  <p>
                    We’ll read it with you, ask about anything unclear, and help
                    you find useful answers.
                  </p>
                  <form onSubmit={uploadFile}>
                    <label className="fileDropzone">
                      <Icon name="upload" size={26} />
                      CSV or Excel file
                      <input
                        key={workspace?.id ?? "first-upload"}
                        type="file"
                        accept=".csv,.xlsx"
                        required
                        disabled={busy}
                        onChange={(event) =>
                          setFile(event.target.files?.[0] ?? null)
                        }
                      />
                      <span>
                        {file
                          ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB`
                          : "Drop a .csv or .xlsx file here, or click to browse · up to 20 MiB"}
                      </span>
                    </label>
                    <label>What is this data about? (optional)<select disabled={busy} value={uploadDomain} onChange={event => setUploadDomain(event.target.value)}>{domains.map(item => <option key={item} value={item}>{item === "auto" ? "Help me work it out" : item}</option>)}</select></label>
                    <label>What would you like to do first? (private, optional)<select disabled={busy} value={["", "Understand what this data means", "Find patterns and unusual values", "Compare results and choose next steps"].includes(uploadGoal) ? uploadGoal : "custom"} onChange={event => { if (event.target.value !== "custom") setUploadGoal(event.target.value); }}><option value="">Help me choose</option><option>Understand what this data means</option><option>Find patterns and unusual values</option><option>Compare results and choose next steps</option><option value="custom" disabled>My own question (under optional context)</option></select></label>
                    <button className="uploadPrimary" disabled={!file || busy}>
                      <Icon name="sparkle" size={18} />
                      {busy ? "Reading your file…" : "Upload file"}
                    </button>
                    <details className="uploadOptions">
                      <summary>
                        Add context or choose where to save (optional)
                      </summary>
                      {dataset && (
                        <label>
                          Save this file
                          <select
                            value={uploadTarget}
                            disabled={busy}
                            onChange={(event) =>
                              setUploadTarget(event.target.value)
                            }
                          >
                            <option value="new">
                              As a new dataset — named from the file
                            </option>
                            <option value="existing">
                              In the selected dataset
                            </option>
                          </select>
                        </label>
                      )}
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
                    </details>
                  </form>
                  {googleEnabled && (
                    <GoogleSheetsImport
                      request={request}
                      disabled={busy}
                      onImport={importGoogleSheet}
                    />
                  )}
                  <ConnectorsPanel
                    request={request}
                    disabled={busy}
                    onImport={importConnector}
                  />
                  <div
                    className="uploadPromises"
                    aria-label="What happens next"
                  >
                    <span>
                      <Icon name="data" size={16} /> Read the structure
                    </span>
                    <span>
                      <Icon name="overview" size={16} /> Find starting insights
                    </span>
                    <span>
                      <Icon name="chat" size={16} /> Explore together
                    </span>
                  </div>
                  <details className="uploadOptions">
                    <summary>Supported files & limits</summary>
                    <p>
                      CSV in UTF-8 or XLSX with one sheet, up to 20 MiB. Use
                      unique headers, values only, and no merged cells. Maximum
                      100,000 rows, 1,000 columns, and 1,000,000 cells including
                      the header. Your original file is retained.
                    </p>
                  </details>
                  {workspace && uploads.length > 0 && (
                    <details className="retainedFiles">
                      <summary>
                        Retained uploads in the selected dataset (
                        {uploads.length})
                      </summary>
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
                                <td>{item.size === null ? "Original file restricted" : `${item.size.toLocaleString()} bytes`}</td>
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
                    </details>
                  )}
                </section>
                <section className="panel dataLibrarySidebar">
                  <h2>Your data library</h2>
                  <section className="studioDemoPack" aria-label="Practice with demo data">
                    <span className="studioEyebrow"><Icon name="sparkle" size={15} /> READY TO EXPLORE</span>
                    <h3>A dataset made for your first discovery.</h3>
                    <p>Fictional data with dates, clear units and patterns to explore. Each demo opens as a separate dataset.</p>
                    <button type="button" disabled={busy || !workspace} onClick={() => loadSample("retail")}><Icon name="data" size={17} /><span><strong>Explore retail demo</strong><small>Daily sales, patterns & forecasts</small></span><Icon name="arrow" size={16} /></button>
                    <button type="button" disabled={busy || !workspace} onClick={() => loadSample("actions")}><Icon name="decisions" size={17} /><span><strong>Try decision demo</strong><small>Six actions, budgets & selection rules</small></span><Icon name="arrow" size={16} /></button>
                    {!workspace && <p>Create your workspace below to try a demo.</p>}
                  </section>
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
                      <details className="sampleChoices">
                        <summary>Try a fictional example</summary>
                        <p>Explore a sample in its own dataset.</p>
                        {[
                          "cities",
                          "finance",
                          "sales",
                          "inventory",
                          "forecast",
                        ].map((kind) => (
                          <button
                            key={kind}
                            disabled={busy}
                            onClick={() => loadSample(kind)}
                          >
                            {kind === "forecast"
                              ? "Try forecasting sample"
                              : `Try ${kind} sample`}
                          </button>
                        ))}
                      </details>
                      <details className="manualDataset">
                        <summary>Create a named dataset manually</summary>
                        <form onSubmit={createDataset}>
                          <label>
                            New dataset name
                            <input name="name" required maxLength={100} />
                          </label>
                          <button disabled={busy}>Create dataset</button>
                        </form>
                      </details>
                    </>
                  ) : (
                    <>
                      <p>
                        Your first upload will create your workspace and name
                        the dataset from your file. Team settings and shared
                        access are available when you need them.
                      </p>
                      <p>Already invited by a teammate?</p>
                      <button type="button" onClick={() => setSection("team")}>
                        Join or set up a workspace
                      </button>
                    </>
                  )}
                </section>
              </div>
              {workspace && role === "owner" && section === "data" && <SourcesPanel
                key={`sources-${workspace.id}-${dataset}`}
                workspaceId={workspace.id} datasetId={dataset} request={request}
                onImported={async id => {
                  const available = await request<Upload[]>(`/workspaces/${workspace.id}/datasets/${dataset}/uploads`);
                  setUploads(available); setProfileUpload(id); setStarterQuestions([]);
                  setRevisionTick(value => value + 1);
                }}
                onReview={id => { setProfileUpload(id); setSection("prepare"); }}
                onRefresh={() => setSection("refresh")}
              />}
              {section === "team" && <AccountSecurity request={request} onSession={setToken} onDisabled={clearSession} />}
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
                {workspace && role === "owner" && (
                  <DatasetAccessPanel key={workspace.id} workspaceId={workspace.id} request={request} />
                )}
                {workspace && role === "owner" && section === "team" && (
                  <IntegrationsPanel key={`integrations-${workspace.id}`} workspaceId={workspace.id} request={request} />
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
                        {invitationError && (
                          <p role="alert">{invitationError}</p>
                        )}
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
                                      <InvitationIdentityApproval request={request} workspaceId={workspace.id} invitationId={item.id} email={item.email} />
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
              {workspace && section === "memory" && <AgentMemoryPanel key={`${workspace.id}-${user.id}`} workspaceId={workspace.id} request={request} />}
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
              {workspace && section === "team" && <ConsolidationPanel key={`consolidation-${workspace.id}-${user.id}`} request={request} actorId={user.id} />}
              {workspace && section === "audit" && (
                <AuditPanel
                  key={workspace.id}
                  workspaceId={workspace.id}
                  request={request}
                />
              )}
              {section === "support" && (
                <SupportPanel
                  key={workspace?.id ?? "no-workspace"}
                  workspaceId={workspace?.id}
                  request={request}
                />
              )}
              {workspace && manager && section === "usage" && (
                <UsagePanel
                  key={workspace.id}
                  workspaceId={workspace.id}
                  owner={role === "owner"}
                  request={request}
                />
              )}
              {staffRole && section === "admin" && (
                <AdminPanel
                  key={staffRole}
                  role={staffRole}
                  request={request}
                />
              )}
              {section === "search" && workspace && <div className="searchDataWorkspace">
                <CatalogPanel workspaceId={workspace.id} request={request} select={async (id) => {
                  await run(async () => { await selectDataset(workspace.id, id); setSection("search"); });
                }} />
                {root && <DashboardPanel key={`search-${root}-${revisionTick}`} root={root} request={request} />}
              </div>}
              {root ? (
                <>
                  {section === "forecasts" && !reviewing && expert && analysisFocusControl}
                  <div hidden={!["overview", "ask"].includes(section)} className={section === "ask" ? "dedicatedConversation" : "overviewConversation"}>
                    <div className="analysisViewControls" hidden={reviewing}>
                      {section === "ask" ? <div><strong>Your conversation</strong></div> : !limitedUpload && !reviewOpen && guidedFor !== profileUpload ? (
                        <div className="reviewEntryActions">
                          <button type="button" disabled={busy} onClick={openBrief}>Check what Syntelio understood</button>
                          <details><summary>Other review options</summary><button type="button" disabled={busy} onClick={() => { setBriefFor(""); setGuidedFor(profileUpload); }}>Review this upload step by step</button></details>
                        </div>
                      ) : <span />}
                      <fieldset className="analysisViewChoice" data-mode={expert ? "expert" : "simple"}>
                        <legend className="srOnly">Analysis view</legend>
                        <span className="analysisViewIndicator" aria-hidden="true" />
                        <label>
                          <input
                            type="radio"
                            name="analysis-view"
                            checked={!expert}
                            onChange={() => setExpert(false)}
                          />
                          Simple
                        </label>
                        <label>
                          <input
                            type="radio"
                            name="analysis-view"
                            checked={expert}
                            onChange={() => setExpert(true)}
                          />
                          Expert
                        </label>
                      </fieldset>
                    </div>
                    {section === "overview" && !reviewing && expert && analysisFocusControl}
                    {root && user && !limitedUpload && guidedFor === profileUpload && briefFor !== profileUpload && !reviewOpen && (
                      <GuidedReview
                        key={`guided-${user.id}-${root}-${revisionTick}`}
                        root={root}
                        request={request}
                        onClose={changed => {
                          setGuidedFor("");
                          if (changed) setRevisionTick(value => value + 1);
                        }}
                        onReview={() => {
                          setGuidedFor("");
                          setRevisionTick(value => value + 1);
                          reviewUnderstanding();
                        }}
                      />
                    )}
                    <div className="exploreLayout discoveryLayout">
                  {briefActive && user && (
                    <div hidden={section !== "overview"}><DataBriefReview
                      key={`brief-${user.id}-${root}`}
                      root={root}
                      request={request}
                      manual={briefManual}
                      onClose={closeBrief}
                      onUnavailable={(reason) => {
                        setBriefFor("");
                        setBriefManual(false);
                        setGuidedFor("");
                        if (reason || briefManual)
                          setMessage(`${reason || "The data reading is unavailable right now."} You can review data meaning from the overview.`);
                      }}
                    /></div>
                  )}
                      <section className="workspaceSurface overviewFindings" aria-label="First findings from your file" hidden={section !== "overview" || reviewing}>
                        <header className="workspaceSurfaceHeader">
                          <Icon name="overview" />
                          <div>
                            <h2>First findings from your file</h2>
                            <p>Calculated ranges, groups and data checks</p>
                          </div>
                        </header>
                        <div className="insightCanvas">
                        <DiscoveryPanel
                          enabled={!busy && section === "overview" && !reviewing}
                          key={`discovery-${root}-${revisionTick}`}
                          root={root}
                          request={request}
                          onQuestion={askFromHome}
                          onReady={setStarterQuestions}
                          onAnalysis={(tool, metric) => {
                            if (tool === "patterns") askFromHome(metric ? `Find patterns related to ${metric}` : "Find patterns in my data");
                            else { setToolSelection({ root, tool: "anomalies", ...(metric ? { metric } : {}) }); setSection("decisions"); }
                          }}
                          onPrepare={() => setSection("prepare")}
                          onScenario={(metric, aggregation) => {
                            setToolSelection({ root, tool: "scenarios", metric, aggregation });
                            setSection("decisions");
                          }}
                          onReview={reviewUnderstanding}
                          onChat={() => { setSection("ask"); window.requestAnimationFrame(() => chat.current?.focus()); }}
                          expert={expert}
                        />
                      </div>
                      </section>

                      <div className="conversationWorkspace" hidden={section !== "ask" || reviewing}>
                      <AskPanel
                        ref={chat}
                        key={`chat-${root}-${revisionTick}`}
                        root={root}
                        request={request}
                        downloadPdf={downloadPdf}
                        filename={selectedUpload?.filename ?? "Selected upload"}
                        starterQuestions={starterQuestions}
                        onTool={action => {
                          setToolSelection({root, ...action});
                          if (action.tool === "forecasts") setSection("forecasts");
                          else if (["anomalies", "allocations", "scenarios"].includes(action.tool)) setSection("decisions");
                          else if (action.tool === "prepare") openBrief();
                          else if (action.tool === "overview") setSection("overview");
                          else if (action.tool === "patterns") askFromHome(action.metric ? `Find patterns related to ${action.metric}` : "Find patterns in my data");
                        }}
                        expert={expert}
                      />
                      </div>
                    </div>
                  {section === "overview" && !reviewing && <AnalyticsHome
                    key={`home-${root}-${revisionTick}`}
                    root={root}
                    filename={selectedUpload?.filename ?? "Selected upload"}
                    request={request}
                    onAsk={askFromHome}
                    onSaved={(id) => { setSavedSelection({ root, id }); setSection("saved"); }}
                    onNavigate={navigate}
                    onReview={reviewUnderstanding}
                  />}
                    {section === "overview" && !reviewing && !briefActive && (
                      <section className="workspaceSurface" aria-label="Charts & dashboard controls">
                        <header className="workspaceSurfaceHeader">
                          <Icon name="overview" />
                          <div>
                            <h2>Charts & dashboard controls</h2>
                            <p>Explore trends, filters, saved cards and next steps</p>
                          </div>
                        </header>
                        <div className="expandedWorkspaceTools">
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
                      </section>
                    )}
                    {expert && !reviewing && (
                      <SourceDetails
                        key={`source-${root}-${revisionTick}`}
                        root={root}
                        request={request}
                      />
                    )}
                    {analysisIntent === "all" && !reviewing && (
                      <section
                        className="panel forecastTeaser"
                        aria-label="Explore forecasting"
                      >
                        <div>
                          <h2>Ready to look ahead?</h2>
                          <p>
                            Check whether your file supports a basic time-series
                            forecast. Review past error and uncertainty before
                            using an estimate.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setAnalysisIntent("predictive");
                            setSection("forecasts");
                          }}
                        >
                          Explore basic forecasts
                        </button>
                      </section>
                    )}
                    <details
                      ref={reviewDisclosure}
                      hidden={section === "ask" || guidedActive}
                      className={`workspaceDisclosure ${reviewOpen ? "focusedMeaningReview" : ""}`}
                      open={reviewOpen}
                      onToggle={(event) =>
                        setReviewOpen(event.currentTarget.open)
                      }
                    >
                      <summary>
                        <Icon name="prepare" /> Review & refine data
                        understanding
                        <span>
                          Column meanings, business rules and the source map
                        </span>
                      </summary>
                      {reviewOpen && (
                        <div className="expandedWorkspaceTools">
                          <button className="reviewDone" type="button" onClick={() => setReviewOpen(false)}>Back to overview</button>
                          <UnderstandingPanel
                            key={`understanding-${root}`}
                            root={root}
                            request={request}
                            onReviewMissing={openBrief}
                            onChange={() =>
                              setRevisionTick((value) => value + 1)
                            }
                          />
                          <details className="sourceMapDisclosure"><summary>Explore the column map</summary><DatasetMap
                            key={`map-${root}-${revisionTick}`}
                            root={root}
                            filename={
                              selectedUpload?.filename ?? "Selected upload"
                            }
                            request={request}
                            onQuestion={askFromHome}
                          /></details>
                        </div>
                      )}
                    </details>
                  </div>
                  {section === "prepare" && (
                    <ProfilePanel
                      onRevisionChange={() =>
                        setRevisionTick((value) => value + 1)
                      }
                      key={root}
                      root={root}
                      request={request}
                      onUnderstand={openBrief}
                    />
                  )}
                  {section === "documents" && (
                    <KnowledgePanel key={root} root={root} request={request} />
                  )}
                  {section === "saved" && (
                    <SavedPanel key={root} root={root} request={request} initialItemId={savedSelection?.root === root ? savedSelection.id : undefined} />
                  )}
                  {section === "refresh" && (
                    <RefreshPanel
                      key={`refresh-${root}-${revisionTick}`}
                      root={root}
                      request={request}
                      onReview={reviewUnderstanding}
                      onActivated={async (id) => {
                        const available = await request<Upload[]>(
                          `${root.split("/uploads/")[0]}/uploads`,
                        );
                        setUploads(available);
                        setProfileUpload(id);
                        setStarterQuestions([]);
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
                      onReview={reviewUnderstanding}
                    />
                  )}
                  {section === "forecasts" && (
                    <ForecastPanel
                      key={`forecasts-${root}-${revisionTick}-${toolSelection?.metric}`}
                      root={root}
                      filename={selectedUpload?.filename ?? "Selected upload"}
                      request={request}
                      onReview={reviewUnderstanding}
                      initialMetric={toolSelection?.root === root ? toolSelection.metric : ""}
                      onExplore={() => setSection("overview")}
                      onPatterns={() => askFromHome(toolSelection?.root === root && toolSelection.metric ? `Find patterns related to ${toolSelection.metric}` : "Find patterns in my data")}
                      onScenario={() => { setToolSelection({ root, tool: "scenarios", scenario_mode: "daily_change", metric: toolSelection?.root === root ? toolSelection.metric : undefined }); setSection("decisions"); }}
                      onRefresh={() => setSection("refresh")}
                    />
                  )}
                  {section === "decisions" && (
                    <DecisionPanel
                      key={`decisions-${root}-${revisionTick}-${analysisIntent}-${toolSelection?.tool}-${toolSelection?.metric}-${toolSelection?.aggregation}-${toolSelection?.scenario_mode}`}
                      root={root}
                      request={request}
                      initialMethod={toolSelection?.root === root && ["anomalies", "allocations", "scenarios"].includes(toolSelection.tool) ? toolSelection.tool as "anomalies" | "allocations" | "scenarios" : analysisIntent === "prescriptive" ? "allocations" : "anomalies"}
                      initialMetric={toolSelection?.root === root ? toolSelection.metric : ""}
                      initialOperation={toolSelection?.root === root ? toolSelection.scenario_mode : undefined}
                      initialAggregation={toolSelection?.root === root ? toolSelection.aggregation : undefined}
                      onReview={reviewUnderstanding}
                    />
                  )}
                </>
              ) : (
                ![
                  "team",
                  "data",
                  "audit",
                  "support",
                  "admin",
                  "usage",
                  ...(workspace ? ["search"] : []),
                ].includes(section) && (
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
                    <button type="button" onClick={() => setSection("data")}>
                      Upload your first file
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
            <span>Syntelio · Synthesized Enterprise Intelligence</span>
            <Link href="/">About this demo</Link>
          </footer>
        </div>
      </div>
    </main></ExportDownloadContext.Provider>
  );
}
