> **File use case:** Records the source and license of the bundled product typefaces.
> **What it does:** Enables offline self-hosted typography without external browser font requests.

# Inter (product typeface)

Inter 4.1 variable fonts from the official rsms/inter release `Inter-4.1.zip`,
added October 19, 2026; distributed under the accompanying `Inter-LICENSE.txt` (SIL OFL 1.1).

- `InterVariable.woff2` SHA256: 693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3
- `InterVariable-Italic.woff2` SHA256: e564f652916db6c139570fefb9524a77c4d48f30c92928de9db19b6b5c7a262a

`next/font/local` loads them at build time as `--font-sans`; no customer data or requests go to third parties.

# Manrope (retained, unused)

Variable font from https://github.com/google/fonts/tree/main/ofl/manrope,
downloaded October 13, 2026; distributed under the accompanying OFL.txt.
Font SHA256: 3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6.
It is no longer loaded by the application and can be deleted with its license.

# Fraunces and IBM Plex Mono (public site only)

Added November 1, 2026 for the public landing/auth/onboarding pages; loaded by
`src/app/site/site-tokens.css` via `@font-face`, never by the workspace.

- `FrauncesVariable.woff2` (Undercase Type release 1.000, axes SOFT/WONK/opsz/wght)
  SHA256: 25e420d8c154303e08322ea77f08997c4aade75653ef18425772ada5abacd0ce — `Fraunces-LICENSE.txt` (SIL OFL 1.1)
- `IBMPlexMono-Regular.woff2` (IBM `@ibm/plex-mono` 1.1.0)
  SHA256: 49ce58b41a0e1cb921c0f58d9a5b8b96a2cc21437c7066f3ba4f24873076d131 — `IBMPlexMono-LICENSE.txt` (SIL OFL 1.1)
