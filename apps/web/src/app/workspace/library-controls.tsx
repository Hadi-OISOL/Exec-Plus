/* Use case: Helps users find authorized saved work without running its analysis.
What it does: Supplies scoped search, visibility filters and accessible grid/list presentation controls. */

import styles from "./library.module.css";

export type LibraryLayout = "grid" | "list";
export type LibraryVisibility = "all" | "private" | "shared";

export function LibraryControls({
  name,
  search,
  onSearch,
  visibility,
  onVisibility,
  layout,
  onLayout,
  count,
}: {
  name: string;
  search: string;
  onSearch: (value: string) => void;
  visibility: LibraryVisibility;
  onVisibility: (value: LibraryVisibility) => void;
  layout: LibraryLayout;
  onLayout: (value: LibraryLayout) => void;
  count: number;
}) {
  return (
    <div className={styles.toolbar}>
      <label className={styles.search}>
        <span>Search {name}</span>
        <input
          type="search"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder={`Search ${name} by name`}
        />
      </label>
      <label className={styles.visibility}>
        Visibility for {name}
        <select
          value={visibility}
          onChange={(event) =>
            onVisibility(event.target.value as LibraryVisibility)
          }
        >
          <option value="all">All visible to me</option>
          <option value="private">Private</option>
          <option value="shared">Workspace shared</option>
        </select>
      </label>
      <div className={styles.viewSwitch} role="group" aria-label={`${name} layout`}>
        {(["grid", "list"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            aria-label={`${name} ${mode} view`}
            aria-pressed={layout === mode}
            onClick={() => onLayout(mode)}
          >
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path
                d={mode === "grid" ? "M2 2h6v6H2z M12 2h6v6h-6z M2 12h6v6H2z M12 12h6v6h-6z" : "M2 3h3v3H2z M8 4h10 M2 9h3v3H2z M8 10h10 M2 15h3v3H2z M8 16h10"}
              />
            </svg>
          </button>
        ))}
      </div>
      <span className={styles.count} aria-live="polite">{count} shown</span>
    </div>
  );
}

export function visibleLibraryItem(
  item: { name: string; shared: boolean },
  search: string,
  visibility: LibraryVisibility,
): boolean {
  return item.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()) &&
    (visibility === "all" || item.shared === (visibility === "shared"));
}
