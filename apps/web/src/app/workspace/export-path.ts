/* Use case: Keeps authenticated downloads on explicit application export routes.
What it does: Rejects arbitrary hosts, paths and malformed identifiers before attaching session authorization. */

const id = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const file = "export\\.(?:pdf|xlsx|csv|png)";
const workspace = new RegExp(`^/workspaces/${id}/(?:threads/${id}/turns/${id}/${file}|datasets/${id}/(?:forecasts|analyses)/${id}(?:/comparisons/${id})?/${file}|(?:study-versions|study-boards)/${id}/${file}|exports/dashboard)$`);
const consolidation = new RegExp(`^/organizations/${id}/consolidations/${id}/${file}$`);

export function allowedExportPath(path: string): boolean {
  const [route] = path.split("?");
  return workspace.test(route) || consolidation.test(route);
}
