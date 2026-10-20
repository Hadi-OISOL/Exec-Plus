> **File use case:** Shared visual-design reference for the October 19 ExecPlus web redesign (agents E ui-foundation and F ui-visuals).
> **What it does:** Fixes concrete tokens (color, type, spacing, radius, elevation, motion, chart palettes) and screen layouts, and marks which parts are observed from public ThoughtSpot material versus ExecPlus's own design choices.

# ExecPlus UI design reference (October 19, 2026)

Status: **stage 2 (complete)**. Legend: **[TS-obs]** observed on public ThoughtSpot pages or
public docs screenshots (no login, no tenant, nothing copied into the product);
**[ours]** ExecPlus choice; **[ref]** idea from a named open-source project.
Evidence locations are in §11. Never ship ThoughtSpot logos, images, copy or code.

## 1. Fonts

- `apps/web/src/app/fonts/InterVariable.woff2` — Inter 4.1, official rsms/inter release
  `Inter-4.1.zip` (zip sha256 `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e`).
  File sha256 `693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3`, 352,240 bytes, `wOF2` magic verified.
- `InterVariable-Italic.woff2` sha256 `e564f652916db6c139570fefb9524a77c4d48f30c92928de9db19b6b5c7a262a`, 387,976 bytes (optional; load only if italics are used).
- License: `apps/web/src/app/fonts/Inter-LICENSE.txt` (SIL OFL 1.1, verbatim); recorded in the
  fonts `README.md` and `THIRD_PARTY_NOTICES.md`.
- `next/font/local`, `weight: "100 900"`, `display: "swap"`, CSS variable `--font-sans`;
  fallback `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Mono: system
  `ui-monospace, "SF Mono", "Cascadia Mono", Menlo, monospace` (column names in chips/code).
- Numbers **[ours]**: KPIs, table cells, axis labels, deltas, tooltips use
  `font-variant-numeric: tabular-nums` (`"tnum"`). Body: `font-feature-settings: "cv11"`.
  Use `"zero"` (slashed zero) only for IDs/hashes.
- [TS-obs] Marketing site preloads Geist / Geist Mono. Product screenshots show a neutral
  grotesk whose name is not public (embed docs only expose `--ts-var-root-font-family`). Inter is our choice.

## 2. Color tokens

Define on `:root` (light) in `theme.css`; redefine for dark under
`@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }` **and**
`:root[data-theme="dark"] {…}`. Ratios are WCAG 2.x, computed for this doc.

| Token | Light | Dark | Use / contrast |
|---|---|---|---|
| `--color-bg` | `#F6F8FA` | `#0E131B` | Canvas behind tiles; sidebar [TS-obs `#F6F8FA`] |
| `--color-surface` | `#FFFFFF` | `#161C26` | Tiles, panels, chat column |
| `--color-surface-raised` | `#FFFFFF` | `#1D2430` | Menus, popovers, dialogs (+shadow) |
| `--color-surface-sunken` | `#F0F2F5` | `#11161F` | Inputs on cards, table header, user bubble |
| `--color-surface-hover` | `#EEF1F5` | `#222A37` | Row / list / nav hover |
| `--color-border` | `#E3E6EB` | `#2A3240` | Tile border, dividers [TS-obs tile edge ≈`#E9EBEE`] |
| `--color-border-strong` | `#C9CFD8` | `#3A4353` | Inputs, ask bar, table rules |
| `--color-text` | `#1B2330` | `#E8ECF2` | Primary text, 15.8 / 15.7 [TS-obs `#1B2330`] |
| `--color-text-secondary` | `#4A5361` | `#B4BCC8` | Labels, descriptions, 7.2 / 8.9 |
| `--color-text-muted` | `#677080` | `#8B94A3` | Captions, axis, coverage line, ≥4.7 / ≥5.6 |
| `--color-text-disabled` | `#8A93A0` | `#5F6878` | Disabled only |
| `--color-primary` | `#2563EB` | `#6B9BFF` | Primary buttons, active tab, send button |
| `--color-primary-hover` | `#1D4FD8` | `#86AEFF` | |
| `--color-primary-pressed` | `#1A43B8` | `#A3C1FF` | |
| `--color-on-primary` | `#FFFFFF` | `#0B1220` | 5.2 / 6.9 |
| `--color-primary-subtle` | `#EBF1FE` | `#1B2A4A` | Selected nav row, info banner, focus halo |
| `--color-primary-text` | `#1D4FD8` | `#86AEFF` | Links, selected nav text, metric names, 5.9 / 6.4 on subtle |
| `--color-focus-ring` | `#2563EB` | `#86AEFF` | 2px outline, 2px offset |
| `--color-success` / `-subtle` | `#0A7543` / `#E7F6EE` | `#3FCB83` / `#13301F` | 5.2 / 6.9 |
| `--color-warning` / `-subtle` | `#A35404` / `#FDF1E3` | `#F0A33C` / `#35260F` | 4.9 / 7.0 |
| `--color-danger` / `-subtle` | `#C42B32` / `#FDECEC` | `#FF7B7F` / `#3A1A1C` | 4.9 / 6.2 |
| `--color-chip-measure` | `#E0F8EF` | `#17332A` | Measure chips [TS-obs `#E0F8EF`] |
| `--color-chip-dimension` | `#DEE8FA` | `#1B2A4A` | Attribute/category chips [TS-obs `#DEE8FA`] |
| `--color-chip-filter` | `#EAEDF2` | `#262E3B` | Filter chips with funnel icon [TS-obs `#EAEDF2`] |
| `--color-overlay` | `rgba(15,20,30,.45)` | `rgba(0,0,0,.6)` | Dialog scrim |

Chip text is always `--color-text` (≥11.5:1 on every chip bg). Positive/negative deltas use
success/danger **plus** an arrow icon; status always pairs icon + label. "Exact / Verified"
badge = success-subtle + success; "Estimate / Assumption" = warning-subtle + warning;
model prose ("AI reading — review") gets a neutral chip, never a verified badge.

[TS-obs] Product (docs screenshots): primary blue `#2770EF` (selected nav text, Go/Done,
send button), canvas `#F6F8FA`, text `#1B2330`/`#1C232F`, chip/secondary-button gray
`#EBEDF1`, selected nav bg `#E7EEF9`, info banner `#DEE8FA`, dark top bar `#1C232F`.
`#2770EF` on `#E7EEF9` is only 3.9:1, so we use the slightly deeper `#2563EB`/`#1D4FD8`.
Marketing site (CSS): `#0A6CF9`, `#4E55FD`, cyan `#00D2FF`, navy `#1B1B61`/`#08072C` — not used.

## 3. Typography scale [ours]

| Token | Size / line | Weight | Tracking | Use |
|---|---|---|---|---|
| `--text-display` | 32 / 40 | 650 | -0.02em | Home greeting only |
| `--text-h1` | 24 / 32 | 650 | -0.015em | Page / Liveboard title [TS-obs ≈24px] |
| `--text-h2` | 18 / 26 | 600 | -0.01em | Section title, answer headings |
| `--text-h3` | 15 / 22 | 600 | -0.005em | Tile title [TS-obs ≈17px regular-weight] |
| `--text-body` | 14 / 20 | 400 | 0 | Default UI |
| `--text-body-lg` | 16 / 26 | 400 | 0 | Chat answer prose, ask bar input |
| `--text-small` | 13 / 18 | 400/500 | 0 | Table cells, chips, secondary |
| `--text-caption` | 12 / 16 | 500 | 0.01em | Axis labels, badges, coverage line |
| `--text-overline` | 11 / 16 | 600 | 0.06em upper | Nav group titles [TS-obs "LAST 7 DAYS"] |
| `--text-kpi` | 32 / 38 | 650 | -0.02em tnum | KPI value (28/34 under 640px) [TS-obs ≈40px bold] |

Only weights 400/500/600/650. Prose max width 72ch.

## 4. Spacing, radius, elevation, z-index [ours]

- Spacing (4px base): `--space-1` 4, `-2` 8, `-3` 12, `-4` 16, `-5` 20, `-6` 24, `-8` 32,
  `-10` 40, `-12` 48, `-16` 64. Tile padding 16 (<640px) / 20. Tile gap 16. Page gutter
  16 / 24 (≥640) / 32 (≥1280). Section gap 32.
- Radius: `--radius-xs` 4 (badges, bar ends), `--radius-sm` 6 (inputs, small buttons),
  `--radius-md` 8 (menus, chips' container), `--radius-lg` 12 (tiles, panels, composer),
  `--radius-xl` 16 (Home ask bar, dialogs), `--radius-full` (pills: chips, primary/secondary
  buttons, icon buttons). [TS-obs] Product buttons are pills (Edit, Explore, Go, Done,
  New chat); tiles ≈8px radius; embed default `--ts-var-button-border-radius: 5px`.
- Elevation (light): `--shadow-1` `0 1px 2px rgba(16,24,40,.05), 0 1px 3px rgba(16,24,40,.06)`
  (tiles at rest, with 1px border — [TS-obs] very soft); `--shadow-2`
  `0 4px 12px -2px rgba(16,24,40,.10), 0 2px 4px -2px rgba(16,24,40,.06)` (hovered tile, menus);
  `--shadow-3` `0 16px 32px -8px rgba(16,24,40,.18), 0 4px 8px -4px rgba(16,24,40,.08)` (dialogs).
  Dark: `rgba(0,0,0,.35/.45/.6)`, always keep the 1px border.
- Z: sticky header 10, sidebar 20, popover 40, drawer 50, dialog 60, toast 70.

## 5. Motion [ours]

| Token | Value | Use |
|---|---|---|
| `--ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | Default |
| `--ease-emphasized` | `cubic-bezier(0.3, 0, 0, 1)` | Drawers, panels in |
| `--ease-exit` | `cubic-bezier(0.4, 0, 1, 1)` | Leaving |
| `--dur-fast` | 120ms | Hover, color, focus |
| `--dur-base` | 200ms | Menus, chips, disclosures |
| `--dur-slow` | 320ms | Drawers, section reveal |
| ECharts enter | `animationDuration: 600`, `animationEasing: 'cubicOut'` | First render |
| ECharts update | `animationDurationUpdate: 300`, `'cubicInOut'` | Filter / theme / data change |

- Tile reveal: opacity 0→1, translateY 8→0, `--dur-slow`, stagger 40ms, cap 6 items (rest instant).
- Hover tile: shadow-1 → shadow-2 and actions fade in (`--dur-fast`); no scale.
- Skeleton: 1.4s linear shimmer. Activity shows only real server stages.
- `prefers-reduced-motion: reduce`: no translate/scale, durations 0.01ms, static skeleton tint,
  ECharts `animation: false`. Content is never hidden behind animation.
- [TS-obs] marketing CSS uses `transition: .3s/.5s` (mostly `all`/opacity); product timing unknown.
- No animation library needed. If one is ever justified: `motion@13.5.1` (MIT, published
  2026-10-02, React ^18||^19 peer). Not installed; do not add for this redesign.

## 6. App shell

[TS-obs] Product: dark top bar with library search, notifications, help, avatar; a light
left panel (`#F6F8FA`) with title + collapse icon, pill "New chat" button, overline groups
("LAST 7 DAYS") and selected row (`#E7EEF9` bg, blue text); content on white. Liveboards:
white header band (title, star, description, owner, pill Edit, share, more) over the gray canvas.

[ours]
- **Sidebar** 248px / 64px rail; `--color-bg` with right border. Top 56px: product mark +
  workspace switcher. Then full-width pill **New question** (primary). Groups (overline):
  *Analyze* — Home, Ask, Data overview; *Library* — Saved answers, Boards, Studies;
  *Data* — Sources, Prepare; *Admin* (if permitted). Row 36px, radius 8, icon 18 + 14/500 label;
  hover surface-hover; selected primary-subtle + primary-text (no left bar needed).
  Footer: memory, theme toggle, account. Collapse button persists per viewer (localStorage, try/catch).
- **Top bar** 56px sticky, `--color-surface`, bottom border: page title/breadcrumb left;
  compact ask trigger (max 520px, `Ctrl/⌘ K`) center — hidden on Home; actions right.
- **Content** max 1440px centered; canvas `--color-bg` for boards, `--color-surface` for chat.
- `<1024px`: sidebar = drawer with scrim. `<640px`: single column, top bar = menu + title + ask
  icon, no horizontal page scroll; wide tables scroll inside their tile only.
- Focus: `:focus-visible { outline: 2px solid var(--color-focus-ring); outline-offset: 2px }`.
  Targets ≥40px (≥44px under 640px).

## 7. Chart palettes and chrome (ECharts 6.1)

**Categorical** [ref: dataviz validated default] — fixed order, never cycled; color follows the
entity, not its rank. Validated with `validate_palette.js` on our surfaces `#FFFFFF` / `#161C26`.

| Slot | Light | Dark |
|---|---|---|
| 1 blue | `#2A78D6` | `#3987E5` |
| 2 orange | `#EB6834` | `#D95926` |
| 3 aqua | `#1BAF7A` | `#199E70` |
| 4 yellow | `#EDA100` | `#C98500` |
| 5 magenta | `#E87BA4` | `#D55181` |
| 6 green | `#008300` | `#008300` |
| 7 violet | `#6250D6` | `#9085E9` |
| 8 red | `#E34948` | `#E66767` |

Light: all gates pass (worst adjacent CVD ΔE 9.1, normal ΔE 19.6); slots 3/4/5 are <3:1 on
white → every chart keeps direct labels or a table view. Dark: all gates incl. ≥3:1 pass.
>8 categories → top 7 + **Other** (`#8A93A0` light / `#5F6878` dark). Donut, scatter and
any all-pairs view: ≤3 hues ideal, ≤6 slices + Other. Enable `aria: { enabled: true, decal:
{ show: false } }` and offer decal patterns via a "Patterns" toggle for print/CVD.
[TS-obs] ThoughtSpot defaults seen: `#2F74F0`, `#47D1E0`, `#02BF7F`, `#FCC839`, `#70A1F4`,
line `#8B61F5`; single-measure bars cyan `#47D1E0`. Not reused.

- **Sequential** (heatmap magnitude, light→dark): `#CDE2FB #9EC5F4 #6DA7EC #3987E5 #2A78D6 #1C5CAB #104281 #0D366B`.
  Dark theme: run dark→bright (`#184F95` … `#CDE2FB`) so "more" = brighter.
- **Diverging** (correlation −1…+1, change vs baseline): `#B42A2A #E34948 #F19A99` → neutral
  `#F0EFEC` (dark `#2F3644`, a cool slate so the arms do not turn brown) → `#86B6EF #2A78D6 #1C5CAB`. Equal arms, gray midpoint.
- **Chrome**: grid lines `--color-border` 1px, dashed `[3,3]`, value axis only; axis labels
  12px muted tnum; category axis line `--color-border-strong`; no value-axis line. Tooltip:
  surface-raised, shadow-2, radius 8, padding 10/12, 13px, series dot indicator, value
  right-aligned tnum, exact server string shown. Legend top-right ≤6 items, else bottom, 12px.
- **Marks**: bars max 32px, `borderRadius: [4,4,0,0]` (horizontal `[0,4,4,0]`), 2px gap between
  stacked segments; lines 2px, `symbol` hidden until hover (8px, 2px surface ring); area
  opacity .16; KPI sparkline area .16 + last-point dot 6px [TS-obs], dotted final segment
  when the last period is incomplete [TS-obs]. Mean/median `markLine` dashed muted.
- **Themes**: `echarts.registerTheme('execplus-light'|'execplus-dark', …)` from these tokens
  and switch with `chart.setTheme()` (ECharts 6 dynamic switching, no dispose/re-init).

## 8. Key screens [ours unless marked]

**8.1 Home with ask bar.** Centered column max 760px, top padding 72px (32 on mobile).
Greeting `--text-display` + one muted line ("Ask about *Dataset name* or upload a file").
**Ask bar** [TS-obs Spotter composer: textarea, dataset selector chip, mode icons, settings,
round blue send, "responses should be reviewed" note]: surface, 1px border-strong,
radius-xl, shadow-1, min-height 112px; textarea 16/26 placeholder "Ask a question about your
data…"; bottom row: dataset chip (pill, chip-filter bg, chevron), "@ mention a column" hint
(caption, muted), right a 36px round primary send button (arrow-up icon, disabled until text).
Focus: border primary + `0 0 0 4px var(--color-primary-subtle)`. Enter sends, Shift+Enter newline.
Below (16px): 3–6 **suggested questions** from the server for the active dataset — pill chips,
surface border, 13px, icon left; click fills and sends. Then sections (32px gap):
*Start from your data* (data overview card for the active dataset with 3 mini KPIs + "Open
overview"), *Recent* (3/2/1-column grid of answer/board cards: type icon, title, dataset,
relative time), *Sources* strip with **Upload file** drop zone (dashed border-strong,
radius-lg, 120px, icon + "Drop a CSV or Excel file, or browse").

**8.2 Data overview Liveboard (after upload).** Header band on surface (bottom border): title
`--text-h1`, meta line muted (`100 rows · 14 columns · uploaded 2 min ago`), meaning status
badge (Confirmed / Needs review); right: primary pill **Ask about this data**, secondary pill
**Review meaning**, icon button More. Underline tabs [TS-obs]: Overview · Columns · Quality ·
Relationships (2px primary underline, 14/500, 40px tall). Body on canvas: 12-column grid,
gap 16. Spans: ≥1280 KPI 3 / small 4 / medium 6 / wide 12; 640–1279 KPI 6 / small 6 /
medium 12; <640 all 12. Order:
1. **Findings strip** (wide): up to 3 insight cards side by side (stack on mobile), "See all" link.
2. **KPI row**: rows analysed, completeness %, and 2 headline measures (sum/mean from executed queries).
3. **Composition**: donut (small/medium) + top-categories bar (medium).
4. **Distributions**: histogram small multiples (small each, max 4, "Show more").
5. **Relationships**: correlation heatmap (medium) + structural map (medium).
6. **Quality**: column table (wide): name (mono), role chip, type, missing %, distinct, sample note.

**Tile anatomy** [TS-obs]: surface, 1px border, radius-lg, shadow-1, padding 20. Header: title
h3 (1 line, ellipsis, full in `title`), optional subtitle muted 13. Hover/focus-within actions
top-right: 28px round icon buttons (chip-filter bg) — Explore, table/chart switch, expand,
more. Body heights: small 240, medium 280, wide 320 (mobile 240). Footer 12px muted:
coverage ("Showing 30 of 30 rows" [TS-obs]) + Exact badge + "View table".
**KPI tile** [TS-obs]: title; value `--text-kpi`; context line muted ("of 100 rows" /
period); delta line: arrow icon + `8.3%` + `(3.21M)` absolute + muted comparison label
(e.g. "vs previous month") in success/danger; optional 48px sparkline. min-height 132.
**Donut**: `radius: ['62%','85%']`, `startAngle: 90`, sorted desc, `itemStyle.borderColor`
surface, `borderWidth: 2`, `borderRadius: 4`; center = total (kpi style, 24px) + label; legend
right (tile ≥480px) else below, legend rows show name + value + %; outside labels only ≤5 slices;
emphasis `scaleSize: 4`. Never for >6 parts or for non-additive measures (use bar).
**Bar**: horizontal when >6 categories or labels >8 chars; sorted desc; ≤12 bars + Other;
value labels at bar end (tnum); labels truncated at 18ch, full in tooltip.
**Histogram**: 12–30 bins (server-computed), 1px gap, slot 1, dashed median markLine with
label; caption below "Median 42.1 · IQR 30.0–55.0" from deterministic stats.
**Correlation heatmap**: lower triangle only, ≤12×12 (else top pairs list), square cells, 2px
surface gap, diverging `visualMap` min −1 max 1 horizontal below, cell labels 2 decimals tnum,
label color white when |r| ≥ 0.6 else `--color-text`; click a cell → scatter of the pair
(use `jitter` when dense). Caption: "Association, not cause." [ours, matches product rules].
**Structural map**: column-membership diagram (existing contract), nodes = rounded rects
radius 8 colored by role chip colors, edges `--color-border-strong`.

**Insight card** [TS-obs AI Highlights: metric name in primary-blue, bold value right, red/green
delta badge with arrow, muted period label, one-sentence explanation, selected card 2px blue
border, "Is this useful?" ✓/✗; Spotter correlation answers list "Key Findings"]: surface,
border, radius-lg, padding 16. Row 1: kind chip (icon + "Notable" / "Watch" / "Info") and
Exact badge right. Row 2: title h3. Row 3: one sentence, numbers bolded (server strings).
Row 4: evidence chips (measure/dimension/filter tokens) [TS-obs]. Optional 96px mini chart.
**Proposed actions**: 1–3 small secondary pill buttons ("Compare by region", "Check
outliers", "Forecast next 3 periods"), each running a governed tool. Footer disclosure
"Why this?" (method, rows, limits). Selected/focused card: 2px primary border.

**8.3 Chat answer.** Column max 760px, 24px between turns [TS-obs Spotter]. User turn:
right-aligned bubble, surface-sunken, radius 12 (4 on the top-right), 15px, max 80%.
Assistant turn (no bubble, 24px mark left): (1) **activity** line "Ran 2 queries · 1.4s" with
chevron; expanded = step list + tool cards [TS-obs "Answer generation — Show Details" with
Input/Output]; collapsed by default once done. (2) **Headline** 16/26, key number bold.
(3) Query chips row (measure/dimension/filter). (4) **Answer tile** (same tile component):
chart/table switch + expand top-right; footer actions [TS-obs Pin, Save, Download, Edit]:
Save, Pin to board, Download, Open table. (5) Findings as h2 sections + bullets.
(6) Follow-up chips. (7) Feedback "Is this useful?" thumbs-up / thumbs-down icon buttons (no emoji
text). Composer sticky bottom (ask bar compact: radius-lg, min-height 56) with footnote
"Answers show their calculations; AI readings should be reviewed." [TS-obs similar note].
Stale-data banner [TS-obs]: full-width primary-subtle bar, info icon, close.

## 9. Empty, loading and error states [ours]

- **Loading**: skeleton tiles with final dimensions (no layout shift), header text real when
  known; answer activity shows real stage names + elapsed seconds; ask bar stays usable.
- **Empty**: 40px icon in primary-subtle circle, h3 title, one sentence, one primary action.
  No data → "Upload a CSV or Excel file"; no strong pattern → say so and list weak comparisons.
- **Not enough data**: inside the tile, centered muted text + reason ("Needs ≥ 3 complete periods").
- **Error**: inline danger-subtle banner, icon, plain cause, Retry; never an empty tile.
- **Clarification**: question card with option chips; chosen option disables the rest.

## 10. Open-source references and ECharts 6.1 mapping [ref]

- **ECharts 6** (bundled 6.1.0, Apache-2.0): token-based default theme; dynamic `setTheme`
  and dark-mode switching; default axis-label layout avoids overflow/overlap; scatter
  `jitter` + `jitterOverlap` (jitter / beeswarm) for dense distributions; broken axis for
  outliers (verify option name in the 6.1 option docs before use); matrix coordinate system
  (correlation matrices, small multiples in one instance); chord series (only with computed
  weights); `aria` + `decal` for accessibility. Violin/contour live in the separate
  `echarts-custom-series` npm project — not bundled, do not add now.
- **Tremor** (Apache-2.0, Tailwind + Recharts): KPI card = title, metric, delta badge,
  optional progress; "show the data, hide the chrome". Ideas only — do not install.
- **shadcn/ui charts** (MIT, Recharts): charts themed purely by CSS variables with a second
  set under dark; tooltip indicator variants (dot / line / dashed) and totals; legend below
  plot with click-to-toggle. Reproduce in ECharts `tooltip.formatter` + `legend`.
- **Grafana Saga / Metabase**: dense panels with hover-revealed header menus; dashboard =
  resizable cards on a grid, "number" card for KPIs. Saga tokens were not verified.

## 11. Evidence and limits

- REA 6.4.0 (`data/agent-tools/bin/rea`), headless Chrome, separate profile
  `data/agent-tools/browser-profiles/thoughtspot-design-20261019`. Captures (ignored) in
  `data/agent-tools/rea-captures/thoughtspot-20261019/<page>/` (page.json, verified PNG,
  manifest): home `ev_697ebc8c…`, product `ev_6c5e43aa…`, spotter `ev_7bd0c27e…`, spotterviz
  `ev_8080486e…`, visualize `ev_9556802c…`, analytics `ev_d05187dc…`, analyst-studio `ev_e2488cb1…`.
- `raw/`: homepage HTML/CSS (fonts, colors, radii, transitions) and docs pages;
  `docs-images/`: 18 public docs.thoughtspot.com screenshots (Liveboard, KPI tabs, AI
  Highlights, Search data, Spotter answers) used for pixel sampling. Public pages only.
- Not verified: product font name, the full default chart palette order, product motion
  timings, dark-mode product tokens (only a scaled marketing image: tile ≈`#1A1B29`, primary
  ≈`#6893EB`), Grafana/Tremor exact tokens. Sampled hexes from anti-aliased PNGs are ±2 per channel.
