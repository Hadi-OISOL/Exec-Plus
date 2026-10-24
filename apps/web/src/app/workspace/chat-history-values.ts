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

export const CHAT_PAGE = 50;

export function chatsPath(workspaceRoot: string, search: string, after?: Pick<ChatSummary, "id" | "last_activity">): string {
  const params = new URLSearchParams({ q: search.trim(), limit: String(CHAT_PAGE) });
  if (after) params.set("after", `${after.last_activity}|${after.id}`);
  return `${workspaceRoot}/threads?${params}`;
}

export function groupChats<T extends Pick<ChatSummary, "last_activity">>(chats: T[], now: Date = new Date()) {
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 24 * 60 * 60 * 1000;
  const groups: { label: string; chats: T[] }[] = [];
  for (const chat of chats) {
    const time = new Date(chat.last_activity).getTime();
    const label = time >= midnight ? "Today" : time >= midnight - day ? "Yesterday" : time >= midnight - 7 * day ? "Previous 7 days" : "Older";
    if (groups.at(-1)?.label === label) groups.at(-1)!.chats.push(chat);
    else groups.push({ label, chats: [chat] });
  }
  return groups;
}

export function belongsToSource(chat: Pick<ChatSummary, "dataset_id" | "upload_id">, root: string): boolean {
  return root.endsWith(`/datasets/${chat.dataset_id}/uploads/${chat.upload_id}`);
}
