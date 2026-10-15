/* Use case: Gives pending data work a calm, accessible visual state.
What it does: Animates a decorative chart for a finite time without inventing progress or results. */

export function WorkspaceLoading({ title = "Opening this view", detail = "Getting the information you need…" }: { title?: string; detail?: string }) {
  return <div className="workspaceLoading" role="status">
    <div className="loadingChart" aria-hidden="true">
      {[22, 40, 31, 54, 44, 66].map((height, index) => <span key={index} style={{ height, animationDelay: `${index * 90}ms` }} />)}
    </div>
    <div><strong>{title}</strong><p>{detail}</p></div>
  </div>;
}
