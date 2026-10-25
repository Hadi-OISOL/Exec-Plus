/* Use case: Shows background uploads and personal storage use anywhere in the workspace.
What it does: Renders a collapsible floating tray with per-file and overall progress, pause/resume/cancel/retry controls, reselect-to-resume after reload, and the storage quota bar. */

"use client";

import { useState } from "react";
import { Icon } from "./explore-components";
import { formatBytes, formatDuration } from "./upload-manager";
import type { UploadItem, UploadManager } from "./upload-manager";
import styles from "./upload-tray.module.css";

export type StorageUse = { used_bytes: number; quota_bytes: number; open_upload_bytes: number };

const phaseLabels: Record<UploadItem["phase"], string> = {
  queued: "Queued",
  uploading: "Uploading",
  paused: "Paused",
  processing: "Processing",
  done: "Done",
  failed: "Failed",
  "needs-file": "Waiting for the file",
};
const permanent = new Set(["quota_exceeded", "file_too_large", "unsupported_format", "unsafe_filename", "processing_failed"]);

function percent(sent: number, size: number) {
  return size ? Math.min(100, Math.floor((sent * 100) / size)) : 100;
}

export function StorageBar({ storage }: { storage: StorageUse }) {
  const used = storage.used_bytes + storage.open_upload_bytes;
  const share = storage.quota_bytes ? Math.min(100, Math.round((used * 100) / storage.quota_bytes)) : 100;
  const level = share >= 100 ? "full" : share >= 80 ? "warning" : "ok";
  return (
    <div className={styles.storage} data-level={level}>
      <div className={styles.storageText}>
        <span>{formatBytes(used)} of {formatBytes(storage.quota_bytes)} used</span>
        <span>{share}%</span>
      </div>
      <div className={styles.track} role="progressbar" aria-label="Storage used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={share} aria-valuetext={`${formatBytes(used)} of ${formatBytes(storage.quota_bytes)} used`}>
        <span style={{ width: `${share}%` }} />
      </div>
      {level !== "ok" && (
        <p className={styles.storageWarning}>
          {level === "full" ? "Your storage is full. Delete files you no longer need before uploading more." : "Your storage is almost full."}
        </p>
      )}
    </div>
  );
}

function UploadRow({ item, manager, onOpen }: { item: UploadItem; manager: UploadManager; onOpen: (item: UploadItem) => void }) {
  const value = percent(item.sentBytes, item.size);
  const indeterminate = item.legacy && item.phase === "uploading";
  const remaining = item.speed > 0 ? formatDuration((item.size - item.sentBytes) / item.speed) : "";
  return (
    <li className={styles.item} data-phase={item.phase}>
      <div className={styles.itemHead}>
        <strong title={item.filename}>{item.filename}</strong>
        <span className={styles.phase}>{phaseLabels[item.phase]}</span>
      </div>
      <div
        className={styles.track}
        role="progressbar"
        aria-label={`${item.filename} upload progress`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={indeterminate ? undefined : value}
        data-indeterminate={indeterminate || item.phase === "processing" || undefined}
      >
        <span style={{ width: `${indeterminate ? 100 : value}%` }} />
      </div>
      <p className={styles.detail}>
        {indeterminate ? `Sending ${formatBytes(item.size)}` : `${value}% · ${formatBytes(item.sentBytes)} of ${formatBytes(item.size)}`}
        {item.phase === "uploading" && item.speed > 0 && ` · ${formatBytes(Math.round(item.speed))}/s`}
        {item.phase === "uploading" && remaining && ` · ${remaining}`}
        {item.phase === "processing" && " · Syntelio is reading your file"}
      </p>
      {item.error && <p className={styles.error} role="alert">{item.error}</p>}
      <div className={styles.actions}>
        {(item.phase === "uploading" || item.phase === "queued") && <button type="button" onClick={() => manager.pause(item.key)}>Pause</button>}
        {item.phase === "paused" && <button type="button" onClick={() => manager.resume(item.key)}>Resume</button>}
        {item.phase === "failed" && !permanent.has(item.errorCode ?? "") && <button type="button" onClick={() => manager.resume(item.key)}>Retry</button>}
        {item.phase === "needs-file" && (
          <label className={styles.pick}>
            Resume upload — reselect the file
            <input type="file" accept=".csv,.xlsx" onChange={event => { const file = event.target.files?.[0]; if (file) manager.attach(item.key, file); event.target.value = ""; }} />
          </label>
        )}
        {item.phase === "done" && <button type="button" onClick={() => onOpen(item)}>Open</button>}
        {item.phase === "done" || (item.phase === "failed" && !item.sessionId)
          ? <button type="button" onClick={() => manager.dismiss(item.key)} aria-label={`Dismiss ${item.filename}`}>Dismiss</button>
          : item.phase !== "processing" && <button type="button" onClick={() => void manager.cancel(item.key)} aria-label={`Cancel ${item.filename}`}>Cancel</button>}
      </div>
    </li>
  );
}

export function UploadTray({ manager, items, storage, onOpen }: { manager: UploadManager; items: UploadItem[]; storage: StorageUse | null; onOpen: (item: UploadItem) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!items.length) return null;
  const moving = items.filter(item => item.phase !== "done" && item.phase !== "failed");
  const total = moving.reduce((sum, item) => sum + item.size, 0);
  const sent = moving.reduce((sum, item) => sum + item.sentBytes, 0);
  const overall = percent(sent, total);
  const title = moving.length ? `Uploading ${moving.length} ${moving.length === 1 ? "file" : "files"} · ${overall}%` : "Uploads finished";
  const announcement = items.map(item => `${item.filename}: ${phaseLabels[item.phase]}${item.error ? `. ${item.error}` : ""}`).join(". ");
  return (
    <section className={styles.tray} aria-label="Uploads" data-collapsed={collapsed || undefined}>
      <button type="button" className={styles.header} aria-expanded={!collapsed} aria-controls="upload-tray-body" onClick={() => setCollapsed(value => !value)}>
        <Icon name="upload" size={16} />
        <span>{title}</span>
        <span className={styles.chevron} aria-hidden="true">{collapsed ? "▴" : "▾"}</span>
      </button>
      {moving.length > 0 && (
        <div className={`${styles.track} ${styles.overall}`} role="progressbar" aria-label="Overall upload progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={overall}>
          <span style={{ width: `${overall}%` }} />
        </div>
      )}
      <p className={styles.srOnly} role="status" aria-live="polite">{announcement}</p>
      <div id="upload-tray-body" hidden={collapsed}>
        <ul className={styles.list}>
          {items.map(item => <UploadRow key={item.key} item={item} manager={manager} onOpen={onOpen} />)}
        </ul>
        {storage && <StorageBar storage={storage} />}
      </div>
    </section>
  );
}
