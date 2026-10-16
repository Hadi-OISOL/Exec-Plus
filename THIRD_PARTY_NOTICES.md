> **File use case:** Attributes reused third-party code and analysis guidance.
> **What it does:** Records source versions, modifications and the licenses shipped with ExecPlus.

# Third-party notices

The owner confirmed on October 16, 2026 that this project will remain
**noncommercial**. Lieflat-derived code retains its PolyForm Noncommercial
terms. These notices do not change the independent licenses of other components.

| Component | Source/version | Use and modifications | License |
| --- | --- | --- | --- |
| Lieflat Charts by 躺在废墟里 | [ed436ba](https://github.com/larashero3-dotcom/lieflat-charts/tree/ed436ba56b3cbeee20b9b9966b38a9a9689e239c) | Adapted G10 signed-bar renderer; ExecPlus theme, authorized values, React lifecycle, exact-value inspection and bounded zoom replace demo wiring | [PolyForm Noncommercial](apps/web/public/third-party/lieflat-LICENSE.txt) |
| Apache ECharts | [6.1.0](https://github.com/apache/echarts/tree/6.1.0) | Unmodified pinned npm runtime, selected SVG chart modules; application-specific options | [Apache 2.0](apps/web/public/third-party/echarts-LICENSE.txt), [NOTICE](apps/web/public/third-party/echarts-NOTICE.txt), [d3 notices](apps/web/public/third-party/echarts-d3-LICENSE.txt) |
| ZRender | [6.1.0](https://github.com/ecomfe/zrender) | ECharts rendering dependency | [BSD 3-Clause](apps/web/public/third-party/zrender-LICENSE.txt) |
| tslib | 2.3.0, Microsoft Corporation | ECharts/ZRender runtime helpers | [License](apps/web/public/third-party/echarts-tslib-LICENSE.txt), [copyright](apps/web/public/third-party/echarts-tslib-CopyrightNotice.txt) |
| documd-visuals | [2672b69](https://github.com/markdown-viewer/skills/tree/2672b6920f6c055caf72a916b414ede62ecbfc2e) | Adapted time-series chart preset; real returned observations, exact inspection, ExecPlus theme and null-gap preservation replace demonstration values | [CC-BY-4.0](apps/web/public/third-party/documd-LICENSE.md) |
| Exploratory data analysis guidance, AIpoch | [686e09d](https://github.com/aipoch/medical-research-skills/tree/686e09dfdb45d9fa1a08664f06bb93769b3c9d91) | Curated reading recipe adapted from the CSV EDA checklist and report template; filtered to supported tools and eligible fields; no bundled analyzer execution | [MIT](apps/web/public/third-party/eda-LICENSE.txt), ©2026 AIpoch |
| SQL Data Analytics Project, Baraa Khatib Salkini | [b99f16a](https://github.com/DataWithBaraa/sql-data-analytics-project/tree/b99f16a26197ff0d36131867af319238aec23dd8) | Reading progression adapted from date-range, measures and magnitude exploration; no upstream dataset or unrestricted SQL execution | [MIT](apps/web/public/third-party/sql-analytics-LICENSE.txt), ©2025 Baraa Khatib Salkini |

| ReportLab | [5.0.1](https://pypi.org/project/reportlab/5.0.1/) | Pinned unmodified PDF runtime; ExecPlus supplies protected saved-answer content and a bounded renderer | [BSD](apps/web/public/third-party/reportlab-LICENSE.txt) |
| Pillow | 12.3.0, pinned directly | Trusted server chart drawing and ReportLab image support; no user images, arbitrary image paths or remote loading are exposed | [MIT-CMU and bundled notices](apps/web/public/third-party/pillow-LICENSE.txt) |
| charset-normalizer | 3.5.2 in the verified PDF build | ReportLab dependency | [MIT](apps/web/public/third-party/charset-normalizer-LICENSE.txt) |
| Manrope by Mikhail Sharanda and Mirko Velimirović | Existing ExecPlus font; SHA-256 `3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6` | Unmodified duplicate packaged for offline PDF embedding with checked glyph coverage | [SIL OFL](apps/api/src/execplus/infrastructure/exports/assets/OFL.txt) |

Exact reused source paths and implementation boundaries are recorded in
[the repository integration map](docs/repository-integration.md). The documd CLI
and GPL rendering/export programs are not included. Project-only development
skills retain their own notices in the ignored local installations.

The web distribution includes these license texts under `/third-party/`; the API
image carries this notice and the same texts. No upstream example values are used
as user data. Licensors do not endorse ExecPlus.

The PDF adapter contains original project code, not Anthropic PDF skill or AIpoch
HTML-to-PDF script code. See [its dependency and content boundary](docs/pdf-export.md).
The pinned development-only pypdf 6.20.1 (BSD 3-Clause) is used to verify output,
not included in the application runtime.

The optional larger allocation method uses **OR-Tools9.15.6755** (Apache2.0) and pinned
**pandas2.3.3**. Its unmodified wheel bundles additional libraries with independent licenses,
including COIN-OR (EPL2.0), Eigen (MPL2.0), SCIP/SoPlex (Apache2.0), HiGHS (MIT),
Abseil, Protobuf, RE2, Boost, zlib and bzip2. [The complete retained notices and source
locations](apps/web/public/third-party/ortools/NOTICE.txt) accompany the distribution.
Only CP-SAT is invoked, in a bounded process; no arbitrary solver script or external action
is exposed. See [the allocation method and dependency review](docs/large-allocation-method.md).

The workspace choice control uses unmodified **@radix-ui/react-select 2.3.8**
(MIT, WorkOS), with ExecPlus's controlled wrapper, accessible labels and teal/navy
styling. Its 38 newly resolved packages are MIT; the existing tslib 2.8.1 helper
is BSD-0-Clause. The [full dependency inventory](apps/web/public/third-party/radix-select/inventory.json)
and [retained license texts](apps/web/public/third-party/radix-select/NOTICE.txt)
include exact versions, integrity values and the official-source notice for
react-remove-scroll-bar, whose npm archive omits its license file. No additional
icon package or third-party example content is bundled.
