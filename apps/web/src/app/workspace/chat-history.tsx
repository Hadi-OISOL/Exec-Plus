/* Use case: Shows the signed-in person's private chats in a collapsible sidebar beside Ask Syntelio.
What it does: Starts, searches, groups by recency, pages, opens, renames and removes (hides) chats; on phones it is a drawer that traps focus. */

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import type { ApiRequest } from "./profile-panel";
import { CHAT_PAGE, chatsPath, groupChats } from "./chat-history-values";
import type { ChatSummary } from "./chat-history-values";
import { Icon } from "./explore-components";
import styles from "./chat-history.module.css";

const STORAGE_KEY = "syntelio.chat-sidebar";
const PHONE = "(max-width: 768px)";

function subscribePhone(onChange: () => void) {
  const query = window.matchMedia(PHONE);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function storedOpen() {
  try {
    return typeof window === "undefined" || window.localStorage.getItem(STORAGE_KEY) !== "closed";
  } catch {
    return true;
  }
}

export function useChatSidebar() {
  const phone = useSyncExternalStore(subscribePhone, () => window.matchMedia(PHONE).matches, () => false);
  const [desktopOpen, setDesktopOpen] = useState(storedOpen);
  const [drawerOpen, setDrawerOpen] = useState(false);

  function setOpen(next: boolean) {
    if (phone) return setDrawerOpen(next);
    setDesktopOpen(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "open" : "closed");
    } catch {}
  }

  const open = phone ? drawerOpen : desktopOpen;
  return { open, phone, setOpen, toggle: () => setOpen(!open) };
}

const FOCUSABLE = "button:not(:disabled), input:not(:disabled), [href], [tabindex]:not([tabindex='-1'])";

export function ChatSidebar({
  workspaceRoot,
  request,
  activeThread,
  refreshKey,
  busy,
  phone,
  onOpen,
  onRemoved,
  onNewChat,
  onClose,
}: {
  workspaceRoot: string;
  request: ApiRequest;
  activeThread: string;
  refreshKey: string;
  busy: boolean;
  phone: boolean;
  onOpen: (chat: ChatSummary) => void;
  onRemoved: (id: string) => void;
  onNewChat: () => void;
  onClose: () => void;
}) {
  const [chats, setChats] = useState<ChatSummary[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [renaming, setRenaming] = useState("");
  const [menu, setMenu] = useState("");
  const [name, setName] = useState("");
  const [reload, setReload] = useState(0);
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      request<ChatSummary[]>(chatsPath(workspaceRoot, search), { signal: controller.signal })
        .then((items) => { setChats(items); setHasMore(items.length === CHAT_PAGE); setError(""); })
        .catch((cause) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Your chats could not be loaded."); });
    }, search ? 250 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [workspaceRoot, request, search, refreshKey, reload]);

  useEffect(() => {
    if (phone) panel.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
  }, [phone]);

  async function loadMore() {
    const last = chats?.at(-1);
    if (!last) return;
    setLoadingMore(true);
    try {
      const items = await request<ChatSummary[]>(chatsPath(workspaceRoot, search, last));
      setChats((current) => {
        const seen = new Set(current?.map((chat) => chat.id));
        return [...(current ?? []), ...items.filter((chat) => !seen.has(chat.id))];
      });
      setHasMore(items.length === CHAT_PAGE);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "More chats could not be loaded.");
    } finally {
      setLoadingMore(false);
    }
  }

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
    setMenu("");
    if (!window.confirm(`Remove “${chat.title}” from your chats? Its audit record is kept.`)) return;
    try {
      await request(`${workspaceRoot}/threads/${chat.id}`, { method: "DELETE" });
      onRemoved(chat.id);
      setReload((value) => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The chat could not be removed.");
    }
  }

  function keyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      if (menu) {
        panel.current?.querySelector<HTMLElement>(`[aria-controls="chat-menu-${menu}"]`)?.focus();
        setMenu("");
      } else if (phone) onClose();
      return;
    }
    if (!phone || event.key !== "Tab" || !panel.current) return;
    const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    const edge = event.shiftKey ? items[0] : items.at(-1);
    if (document.activeElement === edge) {
      event.preventDefault();
      (event.shiftKey ? items.at(-1) : items[0])?.focus();
    }
  }

  const sidebar = (
    <aside
      ref={panel}
      id="chat-sidebar"
      className={styles.sidebar}
      data-phone={phone || undefined}
      aria-label="Chat history"
      role={phone ? "dialog" : undefined}
      aria-modal={phone || undefined}
      onKeyDown={keyDown}
    >
      <div className={styles.top}>
        <button type="button" className={styles.newChat} disabled={busy} onClick={() => { onNewChat(); if (phone) onClose(); }}>
          <Icon name="plus" size={16} /> New chat
        </button>
        {phone && (
          <button type="button" className={styles.iconButton} aria-label="Close chat history" onClick={onClose}>
            <Icon name="close" size={18} />
          </button>
        )}
      </div>
      <label className={styles.search}>
        <span className="srOnly">Search your chats</span>
        <input type="search" value={search} placeholder="Search your chats" onChange={(event) => setSearch(event.target.value)} maxLength={100} />
      </label>
      <div className={styles.scroll}>
        {error && <p role="alert" className="errorNotice">{error}</p>}
        {!chats && !error && <p className={styles.empty} role="status">Loading your chats…</p>}
        {chats && !chats.length &&<p className={styles.empty}>{search ? "No chats match your search." : "Your chats will appear here after your first question."}</p>}
        <ul className={styles.list} aria-label="Your chats">
          {groupChats(chats ?? []).map((group) => [
            <li key={group.label} role="presentation" className={styles.group}>{group.label}</li>,
            ...group.chats.map((chat) => (
              <li
                key={chat.id}
                className={styles.item}
                data-active={chat.id === activeThread || undefined}
                onBlur={(event) => { if (menu === chat.id && !event.currentTarget.contains(event.relatedTarget)) setMenu(""); }}
              >
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
                    <button
                      type="button"
                      className={styles.open}
                      disabled={busy}
                      aria-current={chat.id === activeThread ? "true" : undefined}
                      title={chat.title}
                      onClick={() => { onOpen(chat); if (phone) onClose(); }}
                    >
                      <span className={styles.title}>{chat.title}</span>
                      <span className={styles.meta}>{chat.filename}</span>
                    </button>
                    <button
                      type="button"
                      className={styles.iconButton}
                      aria-label={`Chat options for ${chat.title}`}
                      aria-expanded={menu === chat.id}
                      aria-controls={`chat-menu-${chat.id}`}
                      onClick={() => setMenu(menu === chat.id ? "" : chat.id)}
                    >
                      <Icon name="more" size={16} />
                    </button>
                    {menu === chat.id && (
                      <div id={`chat-menu-${chat.id}`} className={styles.menu} role="group" aria-label={`Options for ${chat.title}`}>
                        <button type="button" onClick={() => { setMenu(""); setRenaming(chat.id); setName(chat.title); }}>Rename</button>
                        <button type="button" disabled={busy && chat.id === activeThread} onClick={() => void remove(chat)}>Remove</button>
                      </div>
                    )}
                  </>
                )}
              </li>
            )),
          ])}
        </ul>
        {hasMore && (
          <button type="button" className={styles.more} disabled={loadingMore} onClick={() => void loadMore()}>
            {loadingMore ? "Loading…" : "Load more chats"}
          </button>
        )}
      </div>
      <p className={styles.note}>Only you can see these chats.</p>
    </aside>
  );

  if (!phone) return sidebar;
  return createPortal(
    <>
      <div className={styles.backdrop} aria-hidden="true" onClick={onClose} />
      {sidebar}
    </>,
    document.querySelector(".workbench") ?? document.body,
  );
}
