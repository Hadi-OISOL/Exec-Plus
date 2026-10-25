/* Use case: Runs resumable chunked file uploads in the background of the workspace.
What it does: Queues files, hashes and sends each chunk with retries, supports pause/resume/cancel, and remembers in-progress sessions (never file contents) so an upload can resume after a reload. */

export const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;
export const RESUME_KEY = "execplus.uploads.v1";
export const UPLOAD_ACCEPT = ".csv,.tsv,.tab,.txt,.xlsx,.xlsm,.xls,.xlsb,.ods,.json,.jsonl,.ndjson,.parquet,.sqlite,.sqlite3,.db,.sav,.zsav,.dta,.sas7bdat,.xpt,.xml,.zip,.gz,.bz2,.xz";

export function uploadContentType(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".csv")) return "text/csv";
  if (lower.endsWith(".xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  return "application/octet-stream";
}

export type UploadPhase = "queued" | "uploading" | "paused" | "processing" | "done" | "failed" | "needs-file";
export type UploadedFile = { id: string; workspace_id: string; dataset_id: string; filename: string; status: string; [key: string]: unknown };
export type UploadItem = {
  key: string;
  filename: string;
  size: number;
  workspaceId: string;
  datasetId?: string;
  sessionId?: string;
  sentBytes: number;
  speed: number;
  phase: UploadPhase;
  error?: string;
  errorCode?: string;
  legacy?: boolean;
  result?: UploadedFile;
};
export type ResumeRecord = { sessionId: string; workspaceId: string; userId: string; filename: string; size: number; lastModified: number };
export type Transport = (path: string, init?: RequestInit) => Promise<Response>;
type Session = { id: string; chunk_size: number; received_bytes: number; next_chunk: number; total_chunks: number; status: string; filename?: string; size_bytes?: number };
type Failure = Error & { status?: number; code?: string };
type Running = { file?: Blob & { lastModified?: number }; contentType: string; controller?: AbortController; session?: Session };
type Store = Pick<Storage, "getItem" | "setItem">;
export type ManagerOptions = {
  transport: Transport;
  userId: string;
  concurrency?: number;
  retries?: number;
  backoffMs?: number;
  pollMs?: number;
  storage?: Store | null;
  onFinish?: (item: UploadItem) => void;
};

export function chunkBounds(index: number, chunkSize: number, size: number): [number, number] {
  return [index * chunkSize, Math.min(size, (index + 1) * chunkSize)];
}

export async function sha256Hex(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

function retryable(cause: unknown): boolean {
  const failure = cause as Failure;
  if (failure?.name === "AbortError") return false;
  if (failure?.status === undefined) return true;
  return failure.status >= 500 || failure.status === 408 || failure.status === 429;
}

function pause(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => { clearTimeout(timer); reject(Object.assign(new Error("Aborted"), { name: "AbortError" })); }, { once: true });
  });
}

export async function withRetry<T>(action: () => Promise<T>, retries: number, backoffMs: number, signal?: AbortSignal): Promise<T> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await action();
    } catch (cause) {
      if (attempt >= retries || !retryable(cause) || signal?.aborted) throw cause;
      await pause(backoffMs * 2 ** attempt, signal);
    }
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value >= 100 || Number.isInteger(value) ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "";
  if (seconds < 60) return `${Math.ceil(seconds)} s left`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)} min left`;
  return `${Math.floor(seconds / 3600)} h ${Math.ceil((seconds % 3600) / 60)} min left`;
}

export function uploadErrorMessage(code: string | undefined, message: string, size: number): string {
  if (code === "quota_exceeded") return `Not enough storage space for this ${formatBytes(size)} file. Delete files you no longer need or ask an administrator for more space.`;
  if (code === "file_too_large") return `This file is too large. Files can be up to ${formatBytes(MAX_UPLOAD_BYTES)}.`;
  if (code === "unsupported_format") return "This file type is not supported yet. Choose CSV, TSV, Excel, ODS, JSON, Parquet, SQLite, SPSS, Stata, SAS, XML or a ZIP/GZ archive of one.";
  if (code === "unsafe_filename") return "This file name cannot be used. Rename the file and try again.";
  return message || "The upload failed. Check your connection and try again.";
}

export function readRecords(storage: Store | null | undefined): ResumeRecord[] {
  try {
    const value = JSON.parse(storage?.getItem(RESUME_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter(item => item && typeof item.sessionId === "string") : [];
  } catch {
    return [];
  }
}

function writeRecords(storage: Store | null | undefined, records: ResumeRecord[]) {
  try { storage?.setItem(RESUME_KEY, JSON.stringify(records)); } catch { /* Storage can be full or disabled; resume is then unavailable. */ }
}

async function body<T>(response: Promise<Response>): Promise<T> {
  const value = await response;
  return value.status === 204 ? (undefined as T) : value.json();
}

export class UploadManager {
  private items: UploadItem[] = [];
  private running = new Map<string, Running>();
  private listeners = new Set<() => void>();
  private counter = 0;
  readonly options: Required<Omit<ManagerOptions, "storage" | "onFinish">> & Pick<ManagerOptions, "storage" | "onFinish">;

  constructor(options: ManagerOptions) {
    this.options = { concurrency: 1, retries: 3, backoffMs: 500, pollMs: 3000, ...options };
  }

  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  snapshot = () => this.items;
  active = () => this.items.some(item => item.phase === "queued" || item.phase === "uploading");

  enqueue(file: Blob & { name: string; lastModified?: number }, workspaceId: string, datasetId: string, contentType: string): string {
    if (file.size > MAX_UPLOAD_BYTES) throw new Error(uploadErrorMessage("file_too_large", "", file.size));
    const key = `upload-${Date.now()}-${(this.counter += 1)}`;
    this.running.set(key, { file, contentType });
    this.items = [...this.items, { key, filename: file.name, size: file.size, workspaceId, datasetId, sentBytes: 0, speed: 0, phase: "queued" }];
    this.emit();
    this.pump();
    return key;
  }

  async restore(): Promise<void> {
    const records = readRecords(this.options.storage).filter(record => record.userId === this.options.userId);
    for (const workspaceId of new Set(records.map(record => record.workspaceId))) {
      let open: Session[];
      try {
        open = await body<Session[]>(this.options.transport(`/workspaces/${workspaceId}/upload-sessions?status=open`));
      } catch {
        continue;
      }
      const live = new Map(open.map(session => [session.id, session]));
      for (const record of records.filter(item => item.workspaceId === workspaceId)) {
        const session = live.get(record.sessionId);
        if (!session) { this.forget(record.sessionId); continue; }
        if (this.items.some(item => item.sessionId === record.sessionId)) continue;
        const key = `upload-${Date.now()}-${(this.counter += 1)}`;
        this.running.set(key, { contentType: "", session });
        this.items = [...this.items, { key, filename: record.filename, size: record.size, workspaceId, sessionId: record.sessionId, sentBytes: session.received_bytes, speed: 0, phase: "needs-file" }];
      }
    }
    this.emit();
  }

  attach(key: string, file: Blob & { name: string; lastModified?: number }): boolean {
    const item = this.find(key);
    if (!item || item.phase !== "needs-file") return false;
    if (file.name !== item.filename || file.size !== item.size) {
      this.patch(key, { error: `Choose the same file: ${item.filename} (${formatBytes(item.size)}).` });
      return false;
    }
    const state = this.running.get(key)!;
    state.file = file;
    state.contentType = file.type;
    this.patch(key, { phase: "queued", error: undefined });
    this.pump();
    return true;
  }

  pause(key: string) {
    const item = this.find(key);
    if (!item || (item.phase !== "uploading" && item.phase !== "queued")) return;
    this.patch(key, { phase: "paused", speed: 0 });
    this.running.get(key)?.controller?.abort();
    this.pump();
  }

  resume(key: string) {
    const item = this.find(key);
    if (!item || (item.phase !== "paused" && item.phase !== "failed")) return;
    if (!this.running.get(key)?.file) { this.patch(key, { phase: "needs-file", error: undefined }); return; }
    this.patch(key, { phase: "queued", error: undefined, errorCode: undefined });
    this.pump();
  }

  async cancel(key: string) {
    const item = this.find(key);
    if (!item) return;
    this.running.get(key)?.controller?.abort();
    this.running.delete(key);
    this.items = this.items.filter(value => value.key !== key);
    this.emit();
    this.pump();
    if (item.sessionId && item.phase !== "done") {
      this.forget(item.sessionId);
      await this.options.transport(`/workspaces/${item.workspaceId}/upload-sessions/${item.sessionId}`, { method: "DELETE" }).catch(() => undefined);
    }
  }

  dismiss(key: string) {
    this.running.delete(key);
    this.items = this.items.filter(item => item.key !== key);
    this.emit();
  }

  stopAll() {
    for (const item of this.items) if (item.phase === "uploading" || item.phase === "queued") this.pause(item.key);
  }

  reset() {
    for (const state of this.running.values()) state.controller?.abort();
    this.running.clear();
    this.items = [];
    this.emit();
  }

  private find(key: string) { return this.items.find(item => item.key === key); }

  private patch(key: string, change: Partial<UploadItem>) {
    this.items = this.items.map(item => (item.key === key ? { ...item, ...change } : item));
    this.emit();
  }

  private emit() { for (const listener of this.listeners) listener(); }

  private forget(sessionId: string) {
    writeRecords(this.options.storage, readRecords(this.options.storage).filter(record => record.sessionId !== sessionId));
  }

  private pump() {
    const busy = this.items.filter(item => item.phase === "uploading").length;
    const next = this.items.filter(item => item.phase === "queued").slice(0, Math.max(0, this.options.concurrency - busy));
    for (const item of next) {
      this.patch(item.key, { phase: "uploading" });
      void this.run(item.key);
    }
  }

  private async run(key: string) {
    const state = this.running.get(key);
    const item = this.find(key);
    if (!state?.file || !item) return;
    const controller = new AbortController();
    state.controller = controller;
    const { transport, retries, backoffMs } = this.options;
    const call = <T,>(path: string, init: RequestInit = {}) => withRetry(() => body<T>(transport(path, { ...init, signal: controller.signal })), retries, backoffMs, controller.signal);
    try {
      let result: UploadedFile;
      if (item.legacy) {
        result = await this.legacy(item, state, controller.signal);
      } else {
        const root = `/workspaces/${item.workspaceId}/upload-sessions`;
        if (!item.sessionId) {
          let session: Session;
          try {
            session = await call<Session>(root, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filename: item.filename, size_bytes: item.size, content_type: state.contentType || "application/octet-stream", purpose: "upload", ...(item.datasetId ? { dataset_id: item.datasetId } : {}) }) });
          } catch (cause) {
            const failure = cause as Failure;
            if (!item.datasetId || !((failure.status === 404 && !failure.code) || failure.status === 405)) throw cause;
            this.patch(key, { legacy: true });
            result = await this.legacy(item, state, controller.signal);
            return this.finish(key, result);
          }
          state.session = session;
          this.patch(key, { sessionId: session.id, sentBytes: session.received_bytes });
          writeRecords(this.options.storage, [...readRecords(this.options.storage), { sessionId: session.id, workspaceId: item.workspaceId, userId: this.options.userId, filename: item.filename, size: item.size, lastModified: state.file.lastModified ?? 0 }]);
        } else {
          state.session = { ...state.session!, ...(await call<Session>(`${root}/${item.sessionId}`)) };
        }
        const session = state.session!;
        const path = `${root}/${session.id}`;
        while (session.next_chunk < session.total_chunks && session.status === "open") {
          const [start, end] = chunkBounds(session.next_chunk, session.chunk_size, item.size);
          const chunk = state.file.slice(start, end);
          const hash = await sha256Hex(chunk);
          const began = performance.now();
          const progress = await withRetry(async () => {
            try {
              return await body<Session>(transport(`${path}/chunks/${session.next_chunk}`, { method: "PUT", body: chunk, headers: { "Content-Type": "application/octet-stream", "X-Chunk-SHA256": hash }, signal: controller.signal }));
            } catch (cause) {
              const failure = cause as Failure;
              if (failure.status !== 409 || failure.code === "quota_exceeded") throw cause;
              const latest = await body<Session>(transport(path, { signal: controller.signal }));
              if (latest.next_chunk === session.next_chunk) throw cause;
              return latest;
            }
          }, retries, backoffMs, controller.signal);
          const seconds = Math.max((performance.now() - began) / 1000, 0.001);
          const instant = (progress.received_bytes - session.received_bytes) / seconds;
          Object.assign(session, progress);
          const previous = this.find(key)?.speed ?? 0;
          this.patch(key, { sentBytes: session.received_bytes, speed: previous && instant > 0 ? previous * 0.7 + instant * 0.3 : Math.max(instant, previous) });
        }
        result = (await call<{ upload: UploadedFile }>(`${path}/complete`, { method: "POST" })).upload;
        this.forget(session.id);
      }
      await this.finish(key, result, controller.signal);
    } catch (cause) {
      const current = this.find(key);
      if (!current || (current.phase !== "uploading" && current.phase !== "processing")) return;
      const failure = cause as Failure;
      this.patch(key, { phase: "failed", speed: 0, errorCode: failure.code, error: uploadErrorMessage(failure.code, failure.message, item.size) });
      this.options.onFinish?.(this.find(key)!);
    } finally {
      if (state.controller === controller) state.controller = undefined;
      this.pump();
    }
  }

  private async legacy(item: UploadItem, state: Running, signal: AbortSignal): Promise<UploadedFile> {
    return body<UploadedFile>(this.options.transport(`/workspaces/${item.workspaceId}/datasets/${item.datasetId}/uploads?filename=${encodeURIComponent(item.filename)}`, { method: "POST", headers: { "Content-Type": state.contentType }, body: state.file, signal }));
  }

  private async finish(key: string, result: UploadedFile, signal?: AbortSignal) {
    let upload = result;
    if (upload.status === "processing") {
      this.patch(key, { phase: "processing", sentBytes: this.find(key)!.size, speed: 0 });
      this.pump();
      while (upload.status === "processing") {
        await pause(this.options.pollMs, signal);
        upload = await withRetry(() => body<UploadedFile>(this.options.transport(`/workspaces/${upload.workspace_id}/datasets/${upload.dataset_id}/uploads/${upload.id}`, { signal })), this.options.retries, this.options.backoffMs, signal);
      }
      if (upload.status === "failed") throw Object.assign(new Error("We could not read this file. Check its format and try again."), { code: "processing_failed" });
    }
    this.patch(key, { phase: "done", sentBytes: this.find(key)!.size, speed: 0, result: upload });
    this.options.onFinish?.(this.find(key)!);
  }
}
