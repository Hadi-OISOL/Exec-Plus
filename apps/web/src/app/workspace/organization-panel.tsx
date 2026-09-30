/* Use case: Organizes separate department workspaces without widening access.
What it does: Creates organization groups and exposes only workspaces the signed-in user can enter. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { studyJson } from "./studies-panel";

type Organization = {
  id: string;
  name: string;
  owner_id: string;
  departments: { workspace_id: string; name: string }[];
};

export function OrganizationPanel({
  workspaceId,
  actorId,
  owner,
  request,
  onSelect,
}: {
  workspaceId: string;
  actorId: string;
  owner: boolean;
  request: ApiRequest;
  onSelect: (id: string) => void;
}) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selected, setSelected] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    request<Organization[]>("/organizations")
      .then((value) => {
        if (active) setOrganizations(value);
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message);
      });
    return () => {
      active = false;
    };
  }, [request, workspaceId]);
  async function action(task: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await task();
      setOrganizations(await request("/organizations"));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not organize workspaces.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel" aria-label="Organization departments">
      <h2>Organization & departments</h2>
      <p>
        Each department uses a separate workspace. Membership and invitations
        control access; organization grouping grants no additional data access.
      </p>
      {organizations.map((item) => (
        <article key={item.id}>
          <h3>{item.name}</h3>
          <div className="studyActions">
            {item.departments.map((department) => (
              <button
                key={department.workspace_id}
                disabled={busy || department.workspace_id === workspaceId}
                onClick={() => onSelect(department.workspace_id)}
              >
                Open {department.name}
              </button>
            ))}
          </div>
        </article>
      ))}
      {owner && (
        <>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const name = String(new FormData(form).get("name") ?? "");
              void action(async () => {
                const value = await request<Organization>(
                  "/organizations",
                  studyJson("POST", { name }),
                );
                setSelected(value.id);
                form.reset();
                setMessage(
                  "Organization created. Attach your department workspace below.",
                );
              });
            }}
          >
            <label>
              Organization name
              <input name="name" required maxLength={100} />
            </label>
            <button disabled={busy}>Create organization</button>
          </form>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const name = String(
                new FormData(event.currentTarget).get("name") ?? "",
              );
              void action(async () => {
                await request(
                  `/workspaces/${workspaceId}/department`,
                  studyJson("POST", { organization_id: selected, name }),
                );
                setMessage(
                  "Current workspace grouped as a department. Access is unchanged.",
                );
              });
            }}
          >
            <label>
              Organization
              <select
                required
                value={selected}
                onChange={(event) => setSelected(event.target.value)}
              >
                <option value="">Choose your organization</option>
                {organizations
                  .filter((item) => item.owner_id === actorId)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Department name
              <input required name="name" maxLength={100} />
            </label>
            <button disabled={busy || !selected}>
              Group current workspace
            </button>
          </form>
        </>
      )}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
