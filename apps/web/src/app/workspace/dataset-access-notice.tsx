/* Use case: Explains when the selected source is limited by a person's access rules.
What it does: Loads current authorized scope without displaying another source's stale notice. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import styles from "./dataset-access-panel.module.css";

export function DatasetAccessNotice({ root, view, request }: { root: string; view: string; request: ApiRequest }) {
  const [scope, setScope] = useState<{ root: string; restricted: boolean; notice: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    request<{ restricted: boolean; notice: string }>(`${root}/access-scope`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) setScope({ root, ...value }); })
      .catch(() => { if (!controller.signal.aborted) setScope(null); });
    return () => controller.abort();
  }, [root, view, request]);
  if (scope?.root !== root || !scope.restricted) return null;
  return <aside className={styles.notice} aria-label="Your dataset access"><strong>Your view of this data</strong><p>{scope.notice}</p></aside>;
}
