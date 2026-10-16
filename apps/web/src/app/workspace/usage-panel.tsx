/* Use case: Separates team activity from owner-only AI usage.
What it does: Loads one focused usage view at a time through existing authenticated requests. */

import { useState } from "react";
import dynamic from "next/dynamic";
import type { ApiRequest } from "./profile-panel";
import { WorkspaceLoading } from "./workspace-loading";
import styles from "./model-usage-panel.module.css";

const ProductUsagePanel = dynamic(() => import("./product-usage").then(module => module.ProductUsagePanel), { loading: () => <WorkspaceLoading /> });
const ModelUsagePanel = dynamic(() => import("./model-usage-panel").then(module => module.ModelUsagePanel), { loading: () => <WorkspaceLoading /> });

export function UsagePanel({ workspaceId, owner, request }: { workspaceId: string; owner: boolean; request: ApiRequest }) {
  const [view, setView] = useState("activity");
  const model = owner && view === "model";
  return <div>
    {owner && <div className={styles.switch} role="group" aria-label="Usage view">
      <button type="button" aria-pressed={!model} onClick={() => setView("activity")}>Team activity</button>
      <button type="button" aria-pressed={model} onClick={() => setView("model")}>AI usage</button>
    </div>}
    {model ? <ModelUsagePanel workspaceId={workspaceId} request={request} /> : <ProductUsagePanel path={`/workspaces/${workspaceId}/product-usage`} request={request} />}
  </div>;
}
