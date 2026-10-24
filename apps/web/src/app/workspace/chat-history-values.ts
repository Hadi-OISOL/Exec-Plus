/* Use case: Formats the private "Your chats" list without touching the network.
What it does: Gives short relative activity times and tells whether a chat belongs to the open file. */

export type ChatSummary = {
  id: string;
  dataset_id: string;
  upload_id: string;
  title: string;
  named: boolean;
  dataset_name: string;
  filename: string;
  last_activity: string;
  turn_count: number;
};

export function activityLabel(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const minutes = Math.floor((now.getTime() - then.getTime()) / 60000);
  if (!Number.isFinite(minutes)) return "";
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} h ago`;
  if (minutes < 7 * 24 * 60) return `${Math.floor(minutes / (24 * 60))} d ago`;
  return then.toLocaleDateString();
}

export function belongsToSource(chat: Pick<ChatSummary, "dataset_id" | "upload_id">, root: string): boolean {
  return root.endsWith(`/datasets/${chat.dataset_id}/uploads/${chat.upload_id}`);
}
