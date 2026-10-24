/* Use case: Separates team activity, owner-only AI usage and owner/admin allowances.
What it does: Loads one focused usage view at a time through existing authenticated requests. */

import { useState } from "react";
import dynamic from "next/dynamic";
import type { ApiRequest } from "./profile-panel";
import { WorkspaceLoading } from "./workspace-loading";
import styles from "./model-usage-panel.module.css";

const ProductUsagePanel = dynamic(() => import("./product-usage").then(module => module.ProductUsagePanel), { loading: () => <WorkspaceLoading /> });
const ModelUsagePanel = dynamic(() => import("./model-usage-panel").then(module => module.ModelUsagePanel), { loading: () => <WorkspaceLoading /> });
const PlanEntitlementsPanel = dynamic(() => import("./plan-entitlements-panel").then(module => module.PlanEntitlementsPanel), { loading: () => <WorkspaceLoading /> });

export function UsagePanel({ workspaceId, owner, request }: { workspaceId: string; owner: boolean; request: ApiRequest }) {
  const [view, setView] = useState("activity");
  const model = owner && view === "model";
  const allowances = view === "allowances";
  return <div>
    <div className={styles.switch} role="group" aria-label="Usage view">
      <button type="button" aria-pressed={!model && !allowances} onClick={() => setView("activity")}>Team activity</button>
      {owner && <button type="button" aria-pressed={model} onClick={() => setView("model")}>AI usage</button>}
      <button type="button" aria-pressed={allowances} onClick={() => setView("allowances")}>Workspace allowances</button>
    </div>
    {allowances ? <PlanEntitlementsPanel workspaceId={workspaceId} request={request} /> : model ? <ModelUsagePanel workspaceId={workspaceId} request={request} /> : <ProductUsagePanel path={`/workspaces/${workspaceId}/product-usage`} request={request} />}
  </div>;
}
