/* Use case: Warns workspace owners and admins when an allowance is close to or at its limit.
What it does: Shows the server's exact near/reached notices on every view, and nothing when usage is fine or unavailable. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./dataset-access-panel.module.css";

type Notice = { kind: string; state: "near" | "reached"; message: string };

export function UsageNotice({ workspaceId, view, request }: { workspaceId: string; view: string; request: ApiRequest }) {
  const [notices, setNotices] = useState<{ workspaceId: string; items: Notice[] } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    request<{ notices: Notice[] }>(`/workspaces/${workspaceId}/plan-usage`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setNotices({ workspaceId, items: value.notices }); })
      .catch(() => { if (!controller.signal.aborted) setNotices(null); });
    return () => controller.abort();
  }, [workspaceId, view, request]);
  if (notices?.workspaceId !== workspaceId || !notices.items.length) return null;
  const reached = notices.items.some(item => item.state === "reached");
  return <aside className={styles.notice} aria-label="Workspace allowance notice"><div role={reached ? "alert" : "status"}>
    <strong>{reached ? "An allowance has been reached" : "An allowance is close to its limit"}</strong>
    {notices.items.map(item => <p key={item.kind}>{item.message}</p>)}
    <p>Open Usage &amp; retention → Workspace allowances for details.</p>
  </div></aside>;
}
