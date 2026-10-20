"use client";

/* Use case: Remembers the reader's appearance preference on this browser.
What it does: Follows system appearance by default, keeps tabs synchronized and
allows the control to work when browser storage is unavailable. */
import { useEffect, useState, useSyncExternalStore } from "react";

type Theme = "system" | "light" | "dark";
const key = "execplus-appearance";
function valid(value: string | null): Theme { return value === "light" || value === "dark" ? value : "system"; }
function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  window.dispatchEvent(new Event("execplus-theme"));
}
export function ThemeControl() {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    function restore() {
      let next: Theme = "system";
      try { next = valid(localStorage.getItem(key)); } catch { /* Storage is optional. */ }
      setTheme(next); apply(next);
    }
    restore();
    window.addEventListener("storage", restore);
    return () => window.removeEventListener("storage", restore);
  }, []);
  return <label className="themeControl"><span className="srOnly">Appearance</span><select aria-label="Appearance" value={theme} onChange={event => {
    const next = valid(event.target.value); setTheme(next); apply(next);
    try { localStorage.setItem(key, next); } catch { /* Keep the active preference for this page. */ }
  }}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>;
}
function subscribe(callback: () => void) {
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  system.addEventListener("change", callback);
  window.addEventListener("execplus-theme", callback);
  return () => { system.removeEventListener("change", callback); window.removeEventListener("execplus-theme", callback); };
}
function snapshot() {
  const theme = document.documentElement.dataset.theme;
  return theme === "dark" || (theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
}
export function useDarkTheme() { return useSyncExternalStore(subscribe, snapshot, () => false); }
