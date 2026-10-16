> **File use case:** Records the project-local skills and reference repositories requested for ExecPlus.
> **What it does:** Preserves source pins, license boundaries, static-scan evidence and practical limits before future use.

# Project skill adoption

Reviewed October 16, 2026. The selected skills help the coding agent design,
inspect and document this project. They are not executable tools available to
ExecPlus's product agent. No application dependency, model provider, production
gate or supported upload format changes because a skill is installed.

## Exact sources and locations

All repositories are downloaded beneath the ignored
`data/agent-tools/references/` directory. The six-source index is
`data/agent-tools/references/oct16-manifest.json`; Lieflat has a separate
`lieflat-charts-installation.json` receipt for the earlier reference copy and
`lieflat-charts-project-installation.json` for the subsequent coding-skill install.

| Source | Pinned commit | License | Project use |
| --- | --- | --- | --- |
| [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/56ea9cf174ed86786187daa9de0e6247cb0747e4) | `56ea9cf174ed86786187daa9de0e6247cb0747e4` | MIT | Selected skill at `.agents/skills/ui-ux-pro-max/` |
| [documd visuals](https://github.com/markdown-viewer/skills/tree/2672b6920f6c055caf72a916b414ede62ecbfc2e) | `2672b6920f6c055caf72a916b414ede62ecbfc2e` | CC-BY-4.0 for this skill package | Selected skill at `.agents/skills/documd-visuals/` |
| [Medical Research Skills](https://github.com/aipoch/medical-research-skills/tree/686e09dfdb45d9fa1a08664f06bb93769b3c9d91) | `686e09dfdb45d9fa1a08664f06bb93769b3c9d91` | MIT | Only general `exploratory-data-analysis` installed at `.agents/skills/exploratory-data-analysis/` |
| [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector/tree/8ccf9201c57ae89afcb84737d8c9d58f7fccf952) | `8ccf9201c57ae89afcb84737d8c9d58f7fccf952` | Apache-2.0 | Inspector instructions at `.agents/skills/skill-inspector/`; scanner in `data/agent-tools/skillspector-env/` |
| [Lieflat Charts](https://github.com/larashero3-dotcom/lieflat-charts/tree/ed436ba56b3cbeee20b9b9966b38a9a9689e239c) | `ed436ba56b3cbeee20b9b9966b38a9a9689e239c` | PolyForm Noncommercial 1.0.0; additional third-party notices | Coding skill at `.agents/skills/lieflat-charts/`; chart guidance for original components, without template/code copying into the product |
| [oneDAL](https://github.com/uxlfoundation/oneDAL/tree/eeb645077424fe8534060d74a044a120384db325) | `eeb645077424fe8534060d74a044a120384db325` | Apache-2.0 | Source reference only; no application install |
| [SQL Data Analytics Project](https://github.com/DataWithBaraa/sql-data-analytics-project/tree/b99f16a26197ff0d36131867af319238aec23dd8) | `b99f16a26197ff0d36131867af319238aec23dd8` | MIT | Analysis progression/examples; no upstream datasets or SQL imported into the product |

The installed copies retain their source license files. Their folders, scanner
environment, reference clones and reports remain project-local and ignored. No
global skill directory, shell profile or company repository setting was changed.
The complete medical collection is downloaded for reference; its clinical skills
are not enabled. REA remains at its previously pinned project-local location.
All seven clone HEADs match the listed pins. The four previously installed skill
copies match their upstream files byte-for-byte, with only the upstream root
license added where the selected subfolder did not include one. The fifth,
Lieflat, was installed unmodified through the official skill-installer helper with
explicit `--ref`, `--name lieflat-charts` and this project's `.agents/skills`
destination. All 146 files match the clone and previously scanned copy, with no
extra or missing files. Its directory is excluded through `.git/info/exclude`;
license/notices and a per-file SHA-256 receipt remain intact. Client discovery on
a subsequent turn makes it available as a coding skill.

The [chart reference audit](chart-experience-reference-audit.md) connects every
repository to a concrete application improvement or a clearly bounded development
role. Actual presentation work is described in [chart experience](chart-experience.md).
Downloading oneDAL or installing an EDA skill does not make the product agent run
their numerical code, and these documents do not claim that it does.

## Review method and retained evidence

The review follows the installed `.agents/skills/skill-inspector/SKILL.md`, whose
[pinned upstream instructions](https://github.com/NVIDIA/SkillSpector/blob/8ccf9201c57ae89afcb84737d8c9d58f7fccf952/skills/skill-inspector/SKILL.md)
require static evidence followed by source-aware review. SkillSpector **2.12.0** was built from
the pinned local source in a separate virtual environment. The resolved dependency
versions are retained in `scanner-dependencies.txt`; the application environment
was not modified.

The scanner command is `skillspector scan <local-folder> --no-llm --format json
--output <report>`. Each scan runs without inherited credentials, with tracing
disabled, no transitive downloads and no author-supplied suppression baseline.
No target scripts, HTML templates or scientific parsers are executed by this
review. No LLM scanning provider is selected or called. The static scanner can
query OSV for package/version advisories; this is distinct from LLM analysis and
does not establish the safety of external assets.

Private evidence lives at
`data/verification/2026-10-16/personal-studio/skill-scans/`: per-target JSON reports
and logs, `scan-status.json`, a complete source-file SHA-256 manifest, and the
scanner dependency freeze. Results below apply only to those captured files and
this review scope. A score is a risk signal, not proof of safety.

## Scan outcomes and source review

All five CLI runs produced valid reports with `execution_successful=true`.
UI, documd and Lieflat exited 1 with findings; EDA and Inspector exited 0.
No scan was interrupted or timed out. The table retains the scanner's raw result;
the last column is the separate source-review verdict for the stated use.

| Target | Raw score / severity / recommendation | Static coverage | Combined verdict and posture |
| --- | --- | --- | --- |
| UI/UX Pro Max | 100 / CRITICAL / DO_NOT_INSTALL; 65 findings | 62/74 files fully inspected, 83.8%; **partial** | **CAUTION**: local design guidance; no blind execution of catalog snippets/install commands |
| documd visuals | 100 / CRITICAL / DO_NOT_INSTALL; 18 findings | 355/361 files fully inspected, 98.3%; **partial** | **CAUTION**: authoring guidance only; optional exporter not installed or executed |
| Exploratory data analysis | 27 / MEDIUM / CAUTION; 2 findings | 12/12 files inspected, 100%; **partial** because sample-path references are unresolved | **CAUTION**: general development guidance; analyzer not a product tool |
| Lieflat Charts | 96 / CRITICAL / DO_NOT_INSTALL; 40 findings | 31/82 analyzed text components fully inspected, 37.8%; **partial** | **CAUTION** for explicitly requested local coding guidance; no automatic template execution or product copying |
| Skill Inspector | 0 / LOW / SAFE; no findings | 2/2 files inspected, 100%; **complete** within the requested static configuration | **APPROVE** as the scoped review procedure; not a certification of the scanner or other skills |

These are not clean-scan or certified-safe claims. No findings were suppressed,
upstream instructions edited, or scores lowered. Source review accounts for the
specific signals as follows; per-finding judgments remain in the private evidence.
The newly installed Lieflat files are identical to the scanned files, so the
existing result is reused without another scan. Installation does not upgrade
the verdict or close its incomplete coverage.

- **UI:** HIGH `PE3` matches password-manager keywords and instructions to keep
  `.env.local` out of Git; `P1` matches system gestures in an anti-pattern column;
  `P6` matches ordinary Python `return rule` / `return rules`; `MP3` matches error
  context and a no-overwrite test comment. `E2` is a test that copies its environment
  and removes `GOOGLE_FONTS_API_KEY` before invoking a fixture. The tests were not
  run. `OH1` includes an unsafe-HTML anti-pattern and a real inline-script hydration
  example: do not copy it without the application's escaping/CSP requirements.
  MEDIUM flags cover documented optional writes/test subprocesses, unpinned setup
  commands, ordinary Flutter documentation links, and advice in “don't” columns.
  The four obfuscation-coverage cases were traced to the parser: food `takeout`,
  XAML `Delete` labels, and a React-effect cleanup query. Parser span limits remain
  unresolved scanner coverage, not evidence of a complete audit.
- **documd:** HIGH `P2` flags five source-attribution HTML comments; they contain no
  override instruction. HIGH `PE3` is visible example policy prose about rotating
  credentials, not code reading them. HIGH `AE1` records parser limits in engine
  references; the referenced ECharts, infographic and HTML/CSS guidance and the
  affected coverage ledgers were read manually. MEDIUM `RP1` correctly identifies
  unpinned optional exporter commands. They remain unused.
- **EDA:** HIGH `AR2` matches the evaluation text “No direct medical advice without
  disclaimer,” which says the opposite of suppressing a disclaimer. MEDIUM `LP3`
  accurately identifies local file-read/write capability without permission
  metadata. The explicit source/output boundary below remains necessary; adding
  permission declarations would not itself provide isolation.
- **Lieflat:** an independent reviewer inspected all 15 unique ranges behind 26
  HIGH `P2` findings: ordinary closed section comments followed by visible demo
  labels, with no hidden instruction found. Ten HIGH `AE1` findings concern seven
  existing renderer/helper artifacts whose inline JavaScript exceeded scanner
  parsing limits. That coverage gap remains open. MEDIUM `RP1` is an unpinned
  installer example; `MP2` is a visible decorative divider. Its `big-threads.html`
  uses `innerHTML` with fixed demo labels, which must not be replaced blindly with
  untrusted data. These source findings remain applicable to the identical installed
  copy; the allowed use is bounded coding guidance, not template execution.

## Use boundaries

UI/UX Pro Max searches its local CSV catalog. Its normal search has no network
client or process execution. Optional `--persist` writes design guidance under an
explicit output directory; names are reduced to safe path segments and existing
files are preserved unless `--force` is supplied. The only environment lookup in
the main implementation is terminal colour capability. Use its project-local
script path rather than the upstream example's Claude plugin environment variable.
Keep output in an intended project folder and review before any forced overwrite.

documd visuals contains Markdown/JSON/TSV guidance and examples, not a bundled
renderer. Its optional unpinned `npx @markdown-viewer/documd` examples would fetch
and execute a separate package; that command was not run. The skill package's
CC-BY-4.0 license does not cover the separate GPL-3.0-only export/rendering tools.
Keep upstream attribution when sharing copied package examples. Plain Markdown
viewers do not necessarily render its custom fences, and ExecPlus does not gain a
document-export feature from these files.

The EDA skill is development guidance only. Its analyzer reads a requested local
file and writes a report, with no network or subprocess implementation. The output
path can overwrite a file and reports contain source metadata and data summaries;
use an explicit ignored output location if the analyzer is separately authorized.
Scientific readers are not a sandbox for untrusted uploads. Its CSV code reads the
first 10,000 rows, uses ordinary floating-point summaries and does not implement
every format named in its catalog. In particular, its generic reader has no XLSX
branch. No bundled analyzer or extra scientific dependency was run or installed.
See [the data-tool adoption review](data-tool-adoption-review.md) for supported
ExecPlus methods and the conditions for a future evaluated ML adapter.

Lieflat is now an installed project coding skill, following the user's explicit
request. Use its inspected data-shape, honest-encoding and readability guidance
to design original ExecPlus components. Its PolyForm Noncommercial terms are not
treated as permission to copy its templates, token library or layout code into a
potentially commercial ExecPlus product. The unmodified installation has its
license and third-party notices. No Lieflat template is opened as executable HTML
or shipped in the app; no product chart is represented as a copied implementation.
The project boundary takes precedence over `SKILL.md:33–65`, which directs template
reuse; `README.en.md:308` calls for separate commercial permission. Installing the
skill does not waive those terms. Its general design ideas can inform original
work without copying the licensed assets.
The templates use major-version CDN URLs and Google Fonts; map examples fetch
fixed public GeoJSON. Its smoke-test script runs `npm root -g`, dynamically imports
Playwright and launches Chromium; its validator evaluates the local palette in a
Node VM. These are documented development functions, not a safe boundary for
executing an untrusted template. They were read but not run. No hidden credential
read, data-upload request or startup persistence was observed in that review.

Skill Inspector is a review procedure, not a runtime hook. Keep its `--no-llm`
default for this project; starting separate model/agent scans requires a separate
user request. Static scanning and this manual review do not certify future
versions, transitive packages, external CDNs or all possible skill behavior.
