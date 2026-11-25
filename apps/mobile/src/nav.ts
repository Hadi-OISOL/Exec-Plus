/* Use case: Describes where the Osalytix phone app can go and how screens move between places.
What it does: Defines the pushed routes, the main screen's focus (file, chat or analytics, thread) and the navigator shared through React context. */

import { createContext, useContext } from "react";
import type { Source } from "./api";
import type { FileTab } from "./screens/File";

export type Route =
  | { name: "main" }
  | { name: "files" }
  | { name: "memory" }
  | { name: "audit" }
  | { name: "account" }
  | { name: "profile" }
  | { name: "team" }
  | { name: "support" }
  | { name: "scenarios"; source: Source }
  | { name: "recommendations"; source: Source };

export type Focus = {
  source?: Source;
  fresh?: boolean;
  mode: "chat" | "analytics";
  tab: FileTab;
  threadId?: string;
  question?: string;
  chatKey: number;
};

export type Nav = {
  push: (route: Route) => void;
  back: () => void;
  open: (focus: Partial<Focus>) => void;
  workspaceId: string;
  signOut: () => void;
};

export const NavContext = createContext<Nav | null>(null);

export function useNav() {
  const value = useContext(NavContext);
  if (!value) throw new Error("Navigator missing");
  return value;
}
