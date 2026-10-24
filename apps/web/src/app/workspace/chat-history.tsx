/* Use case: Lists the signed-in person's private chats in this workspace.
What it does: Searches, opens, renames and removes (hides) chats; others' chats are never listed by the server. */

import { useEffect, useState } from "react";
import type { ApiRequest } from "./profile-panel";
import { activityLabel } from "./chat-history-values";
import type { ChatSummary } from "./chat-history-values";
import styles from "./chat-history.module.css";

export function ChatHistory({
  workspaceRoot,
  request,
  activeThread,
  refreshKey,
  busy,
  onOpen,
  onRemoved,
}: {
  workspaceRoot: string;
  request: ApiRequest;
  activeThread: string;
  refreshKey: string;
  busy: boolean;
  onOpen: (chat: ChatSummary) => void;
  onRemoved: (id: string) => void;
}) {
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [renaming, setRenaming] = useState("");
  const [name, setName] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      request<ChatSummary[]>(`${workspaceRoot}/threads?q=${encodeURIComponent(search.trim())}`, { signal: controller.signal })
        .then((items) => { setChats(items); setError(""); })
        .catch((cause) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Your chats could not be loaded."); });
    }, search ? 250 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [workspaceRoot, request, search, refreshKey, reload]);

  async function rename(chat: ChatSummary) {
    try {
      await request(`${workspaceRoot}/threads/${chat.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: name }),
      });
      setRenaming("");
      setReload((value) => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The chat could not be renamed.");
    }
  }

  async function remove(chat: ChatSummary) {
    if (!window.confirm(`Remove “${chat.title}” from your chats? Its audit record is kept.`)) return;
    try {
      await request(`${workspaceRoot}/threads/${chat.id}`, { method: "DELETE" });
      onRemoved(chat.id);
      setReload((value) => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The chat could not be removed.");
    }
  }

  return (
    <div className={styles.history}>
      <label className={styles.search}>
        <span className="srOnly">Search your chats</span>
        <input type="search" value={search} placeholder="Search your chats" onChange={(event) => setSearch(event.target.value)} maxLength={100} />
      </label>
      {error && <p role="alert" className="errorNotice">{error}</p>}
      {chats && !chats.length && <p className={styles.empty}>{search ? "No chats match your search." : "Your chats will appear here after your first question."}</p>}
      <ul className={styles.list} aria-label="Your chats">
        {chats?.map((chat) => (
          <li key={chat.id} className={styles.item} data-active={chat.id === activeThread || undefined}>
            {renaming === chat.id ? (
              <form className={styles.rename} onSubmit={(event) => { event.preventDefault(); void rename(chat); }}>
                <label>
                  <span className="srOnly">Chat name</span>
                  <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required autoFocus />
                </label>
                <button type="submit" disabled={!name.trim()}>Save</button>
                <button type="button" className="quietButton" onClick={() => setRenaming("")}>Cancel</button>
              </form>
            ) : (
              <>
                <button type="button" className={styles.open} disabled={busy} aria-current={chat.id === activeThread ? "true" : undefined} onClick={() => onOpen(chat)}>
                  <span className={styles.title}>{chat.title}</span>
                  <span className={styles.meta}>{chat.filename} · {chat.dataset_name} · {activityLabel(chat.last_activity)}</span>
                </button>
                <div className={styles.actions}>
                  <button type="button" className="quietButton" aria-label={`Rename ${chat.title}`} onClick={() => { setRenaming(chat.id); setName(chat.title); }}>Rename</button>
                  <button type="button" className="quietButton" aria-label={`Remove ${chat.title}`} disabled={busy && chat.id === activeThread} onClick={() => void remove(chat)}>Remove</button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
