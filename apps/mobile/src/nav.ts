/* Use case: Describes where the Osalytix phone app can go and how screens move between places.
What it does: Defines the route shapes and the small push/back navigator shared through React context. */

import { createContext, useContext } from "react";
import type { Source } from "./api";

export type Route =
  | { name: "home" }
  | { name: "files" }
  | { name: "chats" }
  | { name: "account" }
  | { name: "profile" }
  | { name: "file"; source: Source; fresh?: boolean }
  | { name: "chat"; workspaceId: string; source?: Source; threadId?: string; question?: string };

export type Nav = {
  push: (route: Route) => void;
  back: () => void;
  tab: (route: Route) => void;
  workspaceId: string;
  signOut: () => void;
};

export const NavContext = createContext<Nav | null>(null);

export function useNav() {
  const value = useContext(NavContext);
  if (!value) throw new Error("Navigator missing");
  return value;
}
