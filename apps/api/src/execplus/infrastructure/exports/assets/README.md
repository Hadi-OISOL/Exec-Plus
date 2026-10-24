> **File use case:** Bundles the existing Syntelio font for offline PDF output.
> **What it does:** Records the unchanged font source, license, checksum and tested text boundary.

# PDF font

`Manrope-Variable.ttf` is copied unchanged from the web application's existing
font asset. Source and original download information are in
`apps/web/src/app/fonts/README.md`; it comes from Google Fonts' Manrope project.
The accompanying SIL Open Font License is retained as `OFL.txt`.

SHA-256: `3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6`.

ReportLab embeds the used glyphs. The adapter validates coverage before rendering;
unsupported characters produce an explicit export error rather than missing
glyphs or silent replacements. This is not universal writing-system support.
No font or other resource is fetched over the network at generation time.
