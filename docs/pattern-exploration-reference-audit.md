> **File use case:** Reference and library evidence for the requested pattern-finding enhancement.
> **What it does:** Separates public ThoughtSpot observations, documented capabilities, numerical trials and ExecPlus design decisions.

# Pattern exploration reference audit — October 14, 2026

The user requested measured patterns, understandable conditional questions,
helpful alternatives when dates are absent, better presentation and open-source
exploration tools. This extends the existing analysis experience. It does not
establish universal intelligence, causal identification, competitor parity or
permission to bypass source, privacy or production gates.

## Findings from the public reference

| Question | Finding | Evidence and boundary |
| --- | --- | --- |
| How does a user start exploring? | The analysis illustration places an analysis action beside chart controls. Its next illustration presents three choices with a brief explanation and a small visual: unusual points, trends and relationships between measures. Column selection and advanced settings are later steps. | REA P1/P2 and the [SpotIQ analysis guide](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotiq-custom). These are documentation illustrations, not a workflow executed in an authenticated tenant. |
| How are findings made understandable? | Change-analysis examples put a short finding above a chart, retain comparison context at the top, and offer attribute navigation beside the result. A secondary section lists further findings below the main chart. | REA P3/P4 and the [change-analysis guide](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotiq-comparative). Observed layout; the calculations and statistical labels in those examples were not independently verified. |
| What can automated exploration examine? | The product documentation describes automatic trends, outliers and correlations, with configurable minimum observations and result limits. Its best-practice guide recommends a focused measure and useful modeling metadata. | [SpotIQ overview](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotiq), [analysis settings](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotiq-custom), [best practices](https://docs.thoughtspot.com/cloud/26.9.0.cl/spotiq-best). Documented behavior, not tested accuracy or completeness. |
| How is a forecast distinguished? | The example separates an observed solid line from a projected dotted line and a shaded range. Its source/query context remains visible. The guide requires a time-series KPI, a time keyword and at least 15 time points; it also describes source and interaction limits. | REA P5 and the [forecasting guide](https://docs.thoughtspot.com/cloud/26.9.0.cl/spotiq-forecasting). This does not support a time forecast from an undated snapshot. ExecPlus retains its own eligibility and validation rules. |
| Does a more capable agent imply unrestricted execution? | A newer guide describes Python-generated tables becoming charts, with semantic column types guiding presentation. | [Agentic chart data sources](https://docs.thoughtspot.com/cloud/26.10.0.cl/charts-agentic-supported-sources). Vendor documentation only. ExecPlus can reuse structured numerical results without adopting arbitrary model-written code or inferring the vendor's private runtime controls. |

No ThoughtSpot account was created, no customer tenant was accessed and no
ExecPlus data was uploaded. Private prompts, training, ranking, internal APIs,
security controls and backend architecture remain unknown. No branding, code or
illustration is copied into the product.

## REA evidence ledger

Used installed project CLI `rea@6.4.0`, with `data/agent-tools/browser.py` and its
separate Chrome profile. `list-browser-targets` preceded capture. Playwright
performed navigation and scrolling; REA passively observed each resulting page.
The helper verified PNG signatures and SHA-256 digests. The inspection browser
was stopped afterward; the application browser and VPS tunnel were untouched.

| ID | Target / visible content | Page evidence | Screenshot evidence |
| --- | --- | --- | --- |
| P1 | `26.10.0.cl/spotiq-custom`, chart action | `ev_4d35da1b3b0654fb4f523a427798838ac255932de8ede3aa91ad91720f1a1bfd` | `ev_2304934fce9007f978a78e693e3cbf5dbbe59505f4c20bae8a8f36c8b4c3d2dd` |
| P2 | Same page, analysis choice illustration | `ev_ef2f3e6dee3f78d0b4043a8a133b3a2bf06e0b85cb89c2fcc530b1f90c306402` | `ev_486bfdb5310f80dba224a70daaf23cb2ac339d55d0c2a1f74ee6f881f4d9b16b` |
| P3 | `26.10.0.cl/spotiq-comparative`, explanation and attribute chart | `ev_cb985963f35cd67dbba9b8ad82b75658ee1f71c056877ef9ab88211f8ee2f1b3` | `ev_11e369eaea332db5fbcb456a8519e55958e70f70b7f7bf337f963a895a19ecc6` |
| P4 | Same page, secondary insights | `ev_77c0e2bbac8ed14fe02f71cd75044e7578d0f87d6338f75bc72bf34266b58af4` | `ev_594ff659a1c55a86afc9dcfdd521f6fed9378d31063fac3139e0d60e066686c0` |
| P5 | `26.9.0.cl/spotiq-forecasting`, observed/projected chart | `ev_538bd8bedd384ff788c0bb0765799249e6aaeadf190b8fcaf23a4271bd0a5673` | `ev_7c9d08e8829b9a73e7fc2a89d37a04464c7cd3d0bdf927b3c2a00f53af045ab2` |

All targets use `https://docs.thoughtspot.com/cloud/`. Full captures remain ignored
under `data/agent-evidence/20261014T123358010952Z`,
`20261014T123447759242Z`, `20261014T123515740566Z`,
`20261014T123557372131Z` and `20261014T123614625620Z`.
The intermediate workflow-heading view is retained at
`20261014T123416624489Z`. Accessibility capture
`ev_e4707c54a2b8c4a1b8a23146ed36ac85c77ec438db521249383e8ba47f0f5a28`
and discovery evidence
`ev_269d964823bf55428c7fda64d226c92ece0fe0c62a376d8a14b209a8110b88a5`
remain under `data/agent-tools/browser/`.

Coverage is limited to the selected public origins, capture windows and visible
documentation. An attempted `spotiq-results` URL returned 404; no finding relies
on it. The first Playwright helper used an incorrect package path and failed
before navigation; using the installed root workspace package resolved it.

## Adaptation to existing ExecPlus components

These are design decisions informed by the reference, not reproduced internals.

| Existing surface | Enhancement direction | Evidence and correctness requirement |
| --- | --- | --- |
| Ask ExecPlus | Recognize requests for patterns and calculate eligible relationships from authorized rows. Follow with a short ordinary-language statement and relevant next action. | Keep interpretation distinct from computed evidence. Never invent a relationship from column names or a model's domain associations. |
| Pattern results | Lead with a small ranked set of readable cards. Show involved fields, direction or group comparison, row coverage and a compact chart; expose method/source details separately. | Preserve exact source values and identify statistical coefficients as approximate. Display coverage and exclusions; a ranking score is not a probability. |
| Knowledge and missing information | Reuse saved meanings and private goals to select relevant questions. Ask only for material missing details, such as what one row represents or the outcome the user wants to estimate. | Never silently convert an identifier into a measure, infer elapsed time from row order, or overwrite a confirmed unit. |
| Forecast empty state | Explain the absent timeline in one sentence, then offer measured relationships, comparisons and the existing explicit-assumption scenario path. | A snapshot can show which values occur together. It cannot establish what happens later or prove that one condition caused another. |
| Conditional questions | Explain observed subsets as “In rows where …, the average … was …”. If a user supplies a hypothetical daily rate and duration, show that assumption next to the arithmetic result. | “After X days” needs a declared rate or validated dynamic model. Do not multiply soil moisture or temperature by a duration and call it a prediction. Existing scenarios must retain their own explicit inputs. |
| Visuals | Use a clear headline, consistent cards, charts beside explanations, readable source controls and responsive stacking. | Keep keyboard access, labels, empty states, reduced motion and small-screen overflow checks. Avoid visual significance labels unsupported by the selected method. |

## Open-source library decision

Local inspection found DuckDB 1.5.6 already installed. SciPy, NumPy, scikit-learn,
pandas and the legacy ydata-profiling package were absent before this trial.
The approved implementation direction is a registered SciPy infrastructure
adapter behind an application port, with governed DuckDB extraction and exact
Decimal summaries. The domain remains free of numerical-library imports.

| Library | Fit and decision | Primary source / limitation |
| --- | --- | --- |
| DuckDB 1.5.6 | Retain existing authorized extraction, filters, typed receipts and exact aggregates. Its open-source engine also exposes descriptive statistics. | [Aggregate documentation](https://www.duckdb.org/docs/current/sql/functions/aggregates), [MIT license](https://github.com/duckdb/duckdb/blob/main/LICENSE). Existing query restrictions and versioned evidence remain authoritative; arbitrary statistical SQL is not automatically permitted. |
| SciPy **1.15.3** + NumPy **2.2.6** | Exact candidate pins preserve the project's Python >=3.10 declaration and supply CPython 3.12 Linux wheels. Use Pearson/Spearman coefficients and nominal association as descriptive measures, never model arithmetic. | [SciPy release](https://pypi.org/project/scipy/1.15.3/), [NumPy release](https://pypi.org/project/numpy/2.2.6/), [Spearman contract](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.spearmanr.html), [association contract](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.stats.contingency.association.html). Versions are deliberately compatible pins, not a claim to be the newest release. |
| scikit-learn | Useful for a later explicitly selected prediction target and representative evaluation. Not needed merely to expose measured snapshot patterns. | [Common pitfalls](https://scikit-learn.org/stable/common_pitfalls). Split data before learning preprocessing, prevent target leakage and preserve held-out evaluation. Automatically choosing a plausible-sounding farm outcome is not validated prediction. |
| fg-data-profiling | Potential isolated offline profiling comparison; not the runtime interface for this slice. It produces broad HTML/JSON reports rather than ExecPlus's existing private evidence contract. | The [maintainer repository](https://github.com/Data-Centric-AI-Community/fg-data-profiling) says `ydata-profiling` has been renamed and the old package will no longer receive fixes. No old-name package was installed. Do not embed a full report without resource, privacy and rendering review. |

SciPy's ordinary Spearman p-value is documented as reliable only at large sample
sizes, with permutation methods suggested for smaller samples. This slice does
not expose p-values or claim statistical significance. Constant inputs have no
coefficient; undefined results must be excluded rather than displayed as zero.
Scanning many pairs also creates selection effects. Coefficients describe the
selected snapshot and do not establish causality or out-of-sample accuracy.

### Dependency and runtime evidence

Official PyPI metadata on October 14 reports both pinned releases unyanked,
Python >=3.10 support and available CPython 3.12 manylinux2014 x86_64 wheels.
SciPy declares NumPy >=1.23.5 and <2.5. The vulnerability fields were empty;
this is registry metadata, not a complete security audit. Wheel identifiers:

- SciPy: 37,309,455 bytes; SHA-256
  `271e3713e645149ea5ea3e97b57fdab61ce61333f97cfae392c28ba786f9bb49`.
- NumPy: 16,527,618 bytes; SHA-256
  `fd83c01228a688733f1ded5201c678f0c53ecc1006ffbc404db9f7a899ac6249`.

The [SciPy license](https://github.com/scipy/scipy/blob/v1.15.3/LICENSE.txt) and
[NumPy license](https://github.com/numpy/numpy/blob/v2.2.6/LICENSE.txt) are
BSD-style licenses. Their wheel `LICENSE.txt` files
also describe bundled OpenBLAS/LAPACK, GCC runtime libraries and libquadmath;
retain those notices in the image. The library trees plus bundled shared objects
occupy approximately 203 MiB, excluding metadata. This is a real image cost.
Use bounded native thread counts in API/jobs to avoid multiplying BLAS threads
across concurrent workers. The Python 3.12 slim image remains the target; a fresh
non-root image check is still required after integration.

An ignored isolated Python 3.12.14 environment at
`data/research/pattern-libraries/venv` installed both exact wheels successfully;
`pip check` reports no broken requirements. Independent trial evidence in
`result.json` records **20 passing checks**: known positive/negative coefficients,
independent tied ranks, known categorical association, constant inputs, zero
marginals and high-offset decimal conversion. A 2,000-row, 12-column trial
computed Pearson and Spearman for 66 pairs in 0.101 seconds; import took
0.830 seconds and peak process RSS was approximately 97.4 MiB with native thread
counts set to one. This is one local functional trial, not a deployed capacity
or sustained-load benchmark.

The high-offset fixture initially rounded its own Decimal construction under the
default precision and failed; constructing exact source strings corrected the
fixture. The retained probe demonstrates an application concern: converting
nearby values around 10^30 directly to floats erases differences. Preserve exact
ranks for rank correlation; center/scale with adequate Decimal precision or
reject loss of precision before Pearson conversion. Symmetric nonlinear data
also produced zero Pearson and Spearman despite dependence. A zero coefficient
must not become “there is no relationship of any kind.”

## Completion boundary

Public reference inspection, compatible dependency selection and isolated
library trials are complete. Application integration, source/privacy and replay
tests, exact/approximate presentation, mobile checks, runtime image validation
and release evidence belong in the implementation verification ledger. This
audit alone does not complete a product feature or clear a production gate.
