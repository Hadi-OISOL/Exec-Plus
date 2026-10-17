> **File use case:** Demonstrates the two development phases on a separate local installation.
> **What it does:** Gives concrete fictional inputs, UI steps, expected results and access checks without external accounts or services.

# Try the two phases locally

Use [Start ExecPlus, section B](start-project.md#b-run-on-your-own-computer).
This walkthrough targets local schema **0029** on `http://localhost:3000` and
`http://localhost:8000`. The existing private VPS is a separate **0020** deployment
until its release is explicitly completed. These commands neither deploy nor
connect to it. Use only fictional files in this demonstration.

The API and worker run with models, vectors, email and outbound webhooks disabled.
Guided analysis uses local verified tools; arbitrary model conversation is not
part of this offline demonstration. Keep external source connectors unconfigured.
The phase [implementation matrix](codex-two-phase-implementation.md),
[Phase 1 evidence](verification-codex-phase1.md) and
[Phase 2 evidence](verification-codex-phase2.md) record actual acceptance status.

## 1. Create an account and resume setup

1. Choose **New account**. Enter a fictional account email, your display name,
   workspace name and a private password of 15–128 characters, twice.
2. Submit **Create local account**, then **Sign in with password**. A new account
   receives an owned workspace and a price-free local Demo allowance. The email
   identifies this local account; it has not been verified through a mailbox.
3. In **Your setup guide**, choose a **Setup step** and **Open step**. Pause the
   guide, leave the screen, then **Resume**. Reloading the browser requires a new
   login, but the guide's saved state remains.
4. Return after doing each activity and **Refresh recorded progress**. Use **Skip**
   only deliberately. **Finish** requires each step to have recorded activity or
   an explicit skip. Finishing does not confirm meanings or approve decisions.

Private goals, notes and guide progress stay with that person in that workspace.
For password change, logout or account disable, use the existing account controls.
Changes revoke the documented sessions and dependent credentials. There is no
email reset; authorized interactive recovery and account-bound invitation approval
are explained in [local accounts](local-accounts-onboarding.md).

## 2. Prepare the existing fictional kits

From the checkout root, with the normal environment installed:

```bash
PYTHONPATH=apps/api/src .venv/bin/python scripts/create_demo_kit.py
.venv/bin/python scripts/create_synthetic_workflow_kit.py --output data/synthetic-workflow-v1
```

The first writes the existing retail/action examples to ignored `data/demo-kit/`.
The second writes finance, sales, inventory, HR, company and deliberately dirty
examples plus their meaning/checksum manifest. Neither command imports data or
changes an existing workspace. They refuse to overwrite edited files; use another
output directory if necessary.

Start with **Data library → Explore retail demo**, or upload
`data/demo-kit/execplus-retail-daily-v1.csv`. Review the
[retail definition table](demo-data-guide.md#what-to-tell-execplus): one row is one
complete day in one fictional region, not one order. Confirm the date, categories,
identifier, metric units and default calculations explicitly. The eight numeric
fields include averages as well as sums; delivery hours and discount percentages
must not become summed totals.

For a cleaning demonstration, upload `dirty-review.csv` to a **separate dataset**.
Inspect its whitespace, duplicate, missing cells and invalid text. Preview trimming
`category`, inspect the proposed change, then apply it. Reopen history and compare
the original and prepared versions. Trimming does not repair invalid dates or
numbers. Keep those issues visible instead of guessing replacement values or
silently dropping records. Use the clean retail file for subsequent steps.

## 3. Check a calculation, save a dashboard and export

Use **Search data** and its guided measure/category controls to calculate:

| Retail calculation, all rows and no filters | Expected exact value |
| --- | ---: |
| Sum of `Revenue_USD` | 8,235,156.60 USD |
| Sum of `Orders` | 141,464 orders |
| Sum of `Ad_Spend_USD` | 901,678.00 USD |
| Sum of `Visits` | 2,546,220 visits |

Compare revenue by `Region` and by `Date`; inspect the exact table and evidence
behind the chart. In **Studies & dashboards**, create an eligible study, then
**Create study dashboard** and **Pin to dashboard**. A dashboard accepts up to six
saved versions. Reopening preserves the version instead of silently rerunning it.

Use **Download result** or **Download saved dashboard** for PDF and Excel. Compare
totals, units, selected population and source/version references with the saved
result. Excel's exact numbers may be text where necessary to retain precision;
do not mistake a rounded spreadsheet display for the authoritative value. PNG is
available only where an eligible numerical chart exists. An unavailable result
must remain unavailable, never a fabricated zero-valued chart.

Other synthetic checks are in [the workflow kit](local-workflow-verification.md):
finance revenue 12,714 USD, sales revenue 2,340 USD, inventory 329 items **on its
final date**, and HR salary 30,900 USD/month. Inventory snapshots are not additive
across dates. The intentionally unsafe formula CSV should be rejected.

## 4. Inspect allowances and internal operations

As the workspace owner, open **Usage & retention → Workspace allowances**, then
**Refresh allowances**. Observe actual retained resources and admitted operations.
An upload, a governed query and a new bounded model computation have separate
processing admissions; one action can require more than one. A capacity comparison
can admit its query plus up to six solves. Reopening saved evidence performs
authorization/replay without a new model admission. Downloads count separately.

Demo, Starter, Growth and Enterprise are internal presets, not purchases. A local
platform administrator can select a workspace in **Admin console** and **Assign
a local allowance**, with an explicit period. Ordinary owners cannot grant
themselves that staff role. On a disposable account whose identity you control,
the authorized operator procedure is:

```bash
python3 -m execplus.manage grant-staff --email learner@example.test \
  --role admin --account-id <confirmed-account-uuid> --identity-checked
```

Use the actual UUID shown in that person's **Account security** panel and check
the account independently first. The flag records that check; it does not do it.
After the demonstration, revoke the temporary grant:

```bash
python3 -m execplus.manage revoke-staff --email learner@example.test
```

The local administrator can also open **Internal alerts** to inspect collected
request counts, fixed failure categories, collection gaps and alert thresholds.
Do not create failures by corrupting a database. An empty incident list does not
prove every service is healthy. Alert acknowledgement changes review state, not
the failed job. No external email or monitoring vendor is involved. Exact quota
denial/concurrency tests and limited cost estimates are documented in
[local allowances](local-plan-entitlements.md).

## 5. Explain an observed change

Return to retail. In **Studies & dashboards → Explain a change**, choose **Two
date ranges**, `Date`, sum of `Revenue_USD`, and segment `Region`. Compare
2025-01-01–2025-01-31 with 2025-02-01–2025-02-28. These are observed totals across
different numbers of days; the comparison does not normalize them into daily rates.

Inspect both totals, the exact difference, ranked contributors, record coverage
and formulas. Where offered, add `Orders` for the explicit volume/mix/unit-revenue
decomposition. Unit revenue is an observed ratio, not a known catalog price or
proof of a cause. A zero net difference has no percentage contribution.

Save, reopen, export and pin this study. **Two file snapshots** additionally supports
explicit fields from two permitted datasets in the same workspace. Both sources
remain required for reopening, sharing, API access and embedding. See
[contribution studies](contribution-studies.md).

## 6. Forecast when the file supports it

In **Forecasts**, select `Date`, `Orders`, **Sum**, **Daily**, seven forecast days,
and complete coverage 2025-01-01–2025-12-31. Confirm the coverage only because the
fictional kit supplies all 365 days. Set **Forecast approach** to **Advanced —
compare smoothing and trends**, then select **Compare all eligible methods**.
Declare the optional seven-day cycle to include eligible seasonal candidates.
Compare the selected result with its simple benchmark; selecting Advanced does
not force a more complex model to win.

Read the chronological holdout errors and interval method before saving. The
forecast starts after this file ends, on January 1, 2026. Its bands are not a
guarantee. Reopen the saved vintage unchanged; later actuals must be explicitly
supplied before comparing outcomes. A no-date file cannot acquire a time forecast
from row order; a separately declared what-if remains hypothetical.

### Reproduce a later-actual comparison without inventing observations

This is a **historical holdback exercise** using the existing fictional retail
rows. It is not a prediction tested on genuinely new future observations. Create
a separate training file that stops on December 24; the original kit stays intact:

```bash
.venv/bin/python - <<'PY'
import csv
import hashlib
from pathlib import Path
source = Path("data/demo-kit/execplus-retail-daily-v1.csv")
original = source.read_bytes()
with source.open(newline="", encoding="utf-8") as input_file:
    reader = csv.DictReader(input_file)
    fields = reader.fieldnames
    rows = list(reader)
training = [row for row in rows if row["Date"] <= "2025-12-24"]
assert len(rows) == 1095 and len(training) == 1074
target = source.with_name("retail-holdback-training.csv")
with target.open("x", newline="", encoding="utf-8") as output:
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(training)
assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(original).digest()
print("Created a separate 1,074-row training file; original retail bytes unchanged.")
PY
```

The command refuses an existing output. Upload `retail-holdback-training.csv` into
a new dataset, then confirm the retail field meanings and units. Use a stable
description such as “Fictional daily retail operations; one complete day per
region; revenue and advertising use USD.” Describe coverage in the forecast form,
not by changing the dataset's business meaning between snapshots.

1. Create and save an **Advanced** daily `Orders` sum forecast, horizon seven,
   coverage **2025-01-01–2025-12-24**. Its estimates cover December 25–31.
2. With that **same dataset selected**, upload the unchanged original
   `execplus-retail-daily-v1.csv` as a second upload. Confirm exactly the same
   description, domain, row meaning, field meanings, units and metric definitions.
   A changed business definition should be refused, not silently accepted.
3. Select the full-file upload and reopen the saved holdback forecast from its
   dataset history. In **Compare with actual results**, enter **Actual coverage
   start** `2025-12-25` and **Actual coverage end** `2025-12-31`, confirm complete
   actual periods, then choose **Compare actual data**.
4. Check seven observed periods and zero pending periods. Each actual is the sum
   of the three original `Orders` rows on that date. Inspect errors and source
   receipts, then download **Download actual-data comparison** as Excel or PDF.
5. Reopen the original forecast and the saved comparison separately. The forecast's
   estimates must stay unchanged; the comparison retains its own later-source
   evidence. This does not retrain the forecast or replace either upload.

## 7. Compare several declared changes and limits

Use the small fictional CSV and per-unit mapping in the
[scenario contract](scenario-constraints-capacity-comparisons.md#demonstrate-with-fictional-local-data).
It contains two rows: quantities 2 and 3; prices 10 and 20 USD; variable costs 6
and 8 USD per item; fixed allocated costs 3 and 4 USD. Confirm quantity in items
and the three money fields in USD. Each row contributes once.

Open **Anomalies & decisions → What-if · scenario comparison**, then choose the
scenario approach **Price, quantity and costs · source model**. Choose **Price and
variable cost per unit**, map all four inputs, and declare two alternatives:

- Conservative: price −10%, all other changes zero. Remaining amount: **29 USD**.
- Optimistic: price +10%, quantity +10%, other changes zero. Remaining amount:
  **50.2 USD** (`80 × 1.1 × 1.1 − 36 × 1.1 − 7`).

The unchanged baseline is **37 USD**. **Add outcome limit**: remaining amount
**At least 35 USD**. Baseline and Optimistic pass; Conservative violates it.
Optionally add a single-driver price sensitivity range of `-10,0,10`; its other
drivers stay zero, so those amounts are 29, 37 and 45 USD.

Inspect the exact checks, save and reopen. A successor retains its earlier saved
version and requires a fresh review. Margin limits with zero or negative revenue
are unavailable. These are assumptions under a fixed-mix calculation; naming an
alternative Optimistic gives it no probability or causal support.

## 8. Review unusual records and periods

Choose **Expert** if the advanced method chooser is hidden. Under **Anomalies &
decisions**, begin with **Unusual values · snapshot distribution**: retail
`Support_Tickets` by `Region`, threshold 3.5, materiality 0, minimum group size 8.
The kit deliberately contains large values at March 15/North, July 1/Central and
October 14/South. Inspect exact records; a flag means review, not confirmed error.

Then select **Unusual periods · trailing window**. Use daily summed support
tickets, full 2025 coverage, first evaluated date 2025-01-21, 20 earlier
observations and **Every earlier period**. Inspect the start/end/count of each
strictly earlier reference. Seasonal comparisons need more history; do not claim
complete weekday/month comparisons when it is absent. Save a private review and
reopen the original evidence. Sustained changes can enter the rolling reference
and become harder to detect.

**Unusual combinations · reference group** needs a confirmed unique identifier,
two to four fixed-unit measures, distinct explicit groups, 30–500 complete
reference rows and at most 1,000 selected rows. The retail kit should not be
relabeled or silently sampled to force eligibility. To reproduce the existing
[browser fixture](../apps/web/e2e/advanced-anomalies.spec.ts) explicitly as a small
fictional upload, run:

```bash
.venv/bin/python - <<'PY'
import csv
from pathlib import Path
target = Path("data/demo-kit/combination-review.csv")
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("x", newline="", encoding="utf-8") as output:
    writer = csv.writer(output)
    writer.writerow(["id", "cohort", "a", "b"])
    for i in range(70):
        writer.writerow([f"r{i}", "reference" if i < 60 else "comparison",
                         (i * 3 + i * i) % 41,
                         (i * 11 + i * i * 2) % 41 if i < 65 else 10000])
PY
```

It refuses to replace an existing file. Upload it as a new dataset; confirm `id`
as identifier, `cohort` as category, `a` and `b` as metrics in `units`. Select both
measures, reference group `reference`, comparison group `comparison`, threshold 9
and explicitly confirm your reference choice. Inspect the distances, exact table,
reference evidence and saved review. The [anomaly contract](advanced-anomaly-review.md)
explains singular-reference refusal and limitations. Distances and thresholds
are not probabilities or proof of fraud.

## 9. Compare constrained choices and approve deliberately

Choose **Try decision demo**, confirm the four fields using the
[action definition table](demo-data-guide.md#try-the-separate-decision-demo), then
select **Recommendation · budget allocation**. Budget 1,000 USD, quantity maximum
1, budget increment 1, and staff capacity 10 hours. Declare the two kit rules:
Email campaign requires Tracking setup; Search ads excludes Social ads.

The exact small-model choice is Tracking setup + Email campaign + Search ads:
1,000 USD cost, nine hours and **160 USD assumed benefit**. Approval records your
review; it does not run a campaign or establish real uplift.

For the larger solver and capacity alternatives, use the two-action example in
the [scenario/allocation contract](scenario-constraints-capacity-comparisons.md#demonstrate-with-fictional-local-data).
Choose **Recommendation · larger resource allocation**, maximum quantity 2,
budget 0.11 USD and capacity 0.5 hours. The original usable optimum has benefit
**0.25 USD**. Enable **Include capacity comparison** for the budget and enter
`0.03,0.08,0.11,0.13,0.16`. Exact benefits are 0.07, 0.18, 0.25, 0.29 and 0.29 USD.

Read each actual solver status, resource use and independent checks. Infeasible
or timed-out alternatives must not become zero-benefit solutions. Approving this
record approves only its original capacity model; an alternative needs a new
saved model and review. Source changes invalidate effective approval without
erasing the old review. Saved reopening checks retained outcomes without solving.

## 10. Consolidate two explicitly authorized companies

Create two new workspaces through **Team & settings**, then create one organization
and use **Group current workspace** for each. Remain the organization owner and a
permitted member of both company workspaces. Organization grouping alone grants
no data access.

Upload `company-a.csv` and `company-b.csv` from `data/synthetic-workflow-v1/` into
their respective workspaces. Confirm account categories, signed `amount`, one
company/account/period balance, and fixed USD for A / EUR for B. In **Company
consolidation**, choose both prepared files, `account` and `amount`, reporting
currency USD and January 2025. The worksheet includes every prepared row; its
declared period does not filter the ledger automatically.

Review every account mapping. Explicitly enter the kit's fictional rates: A = 1,
B = 1.25 USD per EUR, with the declared date/reference. Do not fetch or guess FX.
With unchanged account names and no adjustments, expected combined USD balances
are Cash 200, Equity −200, Intercompany 0 and Internal offset 0; total 0. The zero
net intercompany balance is not an elimination journal.

Save, reopen and export the private worksheet. To demonstrate a balanced
elimination, use the reciprocal-counterparty example in the
[tested consolidation journey](../apps/web/e2e/consolidation.spec.ts), which includes
explicit counterparties and −20/+20 USD approved entries. The starter company kit
does not declare those counterparties, so no elimination should be inferred.
See [company consolidation](company-consolidation.md) for source revocation rules.

## 11. Use a scoped read API and a local embedded view

In **Team & settings → Read-only API**, choose the dataset, only the operations
needed, and an expiry. The one-time key is separate from your account session.
For a comparison/dashboard, include every source dataset. Keep the key private.
Use local OpenAPI at `http://localhost:8000/docs`, select the
**ScopedIntegrationKey** security scheme, and try the appropriate saved result:

```text
GET /integration/v1/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}/profile
GET /integration/v1/workspaces/{workspace_id}/studies/{version_id}
GET /integration/v1/workspaces/{workspace_id}/datasets/{dataset_id}/analyses/{analysis_id}
```

Use IDs from your own saved results. Confirm the response matches their evidence,
then revoke the key and check that another read fails. A profile-only key must
not read analyses. Keys cannot use ordinary account routes or approve decisions.
Full route/scope mapping: [customer results API](customer-results-api.md).

For a local frame, explicitly share a dashboard and every pinned study. Restart
only the isolated local API command with the additional environment assignment
`EXECPLUS_INTEGRATION_ALLOW_LOOPBACK=true`. Keep its other offline settings.
Serve the existing host example:

```bash
python3 -m http.server 3100 --bind 127.0.0.1 --directory examples/local-embed-host
```

Open `http://127.0.0.1:3100`. In **Embed a dashboard**, enter that exact host origin.
Copy its local frame address and only the one-use `epb_` secret into the host form
within five minutes. Never paste a broad account session or API key. The view
lasts at most fifteen minutes. Revoke the grant and select **Refresh access &
results** inside the frame; access must stop. A new opening requires a new
bootstrap. Follow the [host instructions](../examples/local-embed-host/README.md).
Return the local loopback setting to its default when this exercise ends.

Leave **Notifications** outbound delivery unconfigured. Signed payload/outbox
tests are local implementation evidence, not evidence of real webhook delivery.

## 12. Check privacy and finish the guide

Create a second fictional account in a separate browser session. An invitation
requires manager approval of that exact native account UUID after an independent
identity check; an email name alone is insufficient. Explicitly add that member
to the intended workspace only.

Using a disposable dataset, the owner can apply a dataset policy granting that
member selected columns and a typed row filter. Recheck the member's profile,
guided queries and exports: only their allowed source scope should be available.
Dataset-owner or staff status is not a data-policy bypass. Do not use a policy
exercise on real records, and do not assume a shared card grants source access.

Keep an owner-private analysis private: the teammate should not reopen it. For a
shared result, revoke a required source grant, then refresh the saved view and
attempt an export/API/embed read. New reads must fail rather than display cached
restricted values. Already downloaded copies cannot be remotely withdrawn.
Details and conservative restrictions are in [dataset policies](dataset-access-policies.md).

Return to **Your setup guide**, refresh recorded activity and finish or explicitly
skip unfinished optional steps. Skipped steps remain visible as skipped.

For a separate recovery demonstration, use the existing
[disposable synthetic rehearsal](local-workflow-verification.md#synthetic-recovery-rehearsal).
It verifies backup checksums, current schema and representative restored evidence
in fresh temporary containers; never restore over this running local workspace
or the VPS. Public HTTPS, production embedding/delivery, independent security
review, backup custody and representative customer/model acceptance remain
separate gates. A completed walkthrough does not clear them.
