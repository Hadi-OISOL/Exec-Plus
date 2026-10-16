> **File use case:** Records observed customer API, webhook and private embedding checks.
> **What it does:** Separates local implementation evidence, retained failures and remaining release acceptance.

# Integration and embedding verification

Status: working-tree implementation on additive **0022**, after metering **0021**.
No deployment, public endpoint or external receiver is claimed. The complete
contract and configuration are in [integration-access-plan.md](integration-access-plan.md).

## Passing checks

| Check | Observed result |
| --- | --- |
| Initial combined backend/architecture slice | 62 passes, 42.688 seconds |
| Key/embed cancellation and transport recheck | 18 passes, including one new cancellation case |
| Final transport slice | Six passes, including one new operator-origin normalization case |
| Distinct backend/architecture coverage | **64**; overlapping rechecks are not added again |
| Repaired RefreshService compatibility | Real refresh webhook activation/delivery case passes |
| Frontend unit tests | **55 passes** |
| Static checks | Types, lint, Ruff and scoped mypy (seven new core files) pass |
| Final Chromium integration journey | **One pass**, 14.9 seconds / 21.9 seconds including startup |
| Responsive captures | Six layouts: key management and embedded dashboard at 1440/390/320 |
| Browser errors | Zero page errors and zero duplicate React key warnings |

The browser uses a fictional workspace and exact large, negative, missing and zero
values. It creates a real scoped key, verifies exact authorized rows, rejects its
use as an ordinary login, and revokes it. It creates a shared saved dashboard and
one-use private view through the real owner UI. A real local HTTPS host exchanges
the bootstrap through origin/source-checked messages. The wrong host is blocked
by the actual browser `frame-ancestors` policy. The view loads the real ECharts
renderer, keeps exact tables and raw `__value` receipt identities, and displays
the saved measure/unit as its friendly chart label. No credential enters browser
storage. Revoking the view clears its displayed results on the next access check.

Backend cases cover current membership and policy boundaries, policy/revocation
changes during work, private/shared board controls, one-use exchange, expiry,
membership removal/re-addition, atomic rate limiting and migration preservation.
Real loopback receivers validate exact HMAC bytes, metadata-only bodies, retry
identity, rotation, stale leases, six-attempt exhaustion, redirect refusal,
pinned-address checks, bounded socket timeouts and cancellation drain. Source and
network work occur outside workspace locks; final authorization remains locked.

## Issuing-account authority repair

Independent cross-feature review found that the optional member `user_id` allowed
an owner to mint a key with another member's broader rights. Two real regression
cases reproduced the defect: a policy-denied owner and a restricted owner both
received 201 instead of 403. Initial failure logs are retained as
`integration-issuer-regression-before.{log,xml}`; no secret was printed.

Keys now bind only the signed-in issuing account. A different `user_id` is refused;
a supplied matching ID is accepted. Issuance checks the issuer's current dataset
access, and every read retains the existing final policy/membership/revocation
checks. The UI explicitly says a key cannot act as another member.

The focused key/embed/migration suite passes **46 cases** in 26.814 seconds. Four
strengthened controls pass in 5.607 seconds, covering denied own issuance, restricted
exact rows, membership deletion/re-addition and a policy change during query work.
These overlap the 46 and are not added again. Together with the earlier unaffected
webhook/architecture cases, the slice has **66 distinct passing cases** across runs.
The real TLS browser journey passes in 16.3 seconds (23.6 including startup), verifies
the saved key belongs to the signed-in issuer, and retains all six responsive,
origin, exact-value, secret-storage and revocation checks. Types/lint, Ruff and
scoped service mypy pass after this repair. No deployment is claimed.

## Retained failures and corrections

- Four first-run test callbacks called synchronous TestClient from its event
  loop. Worker-thread callbacks fixed the fixture; the full slice then passed.
- An aggregate test command used a nonexistent architecture directory and
  collected no tests. The corrected explicit file path supplies the recorded
  architecture passes.
- The first browser fixture intercepted a synthetic public HTTPS page and hit
  Chromium's local-network protection when embedding loopback HTTP. The replacement
  uses a real loopback TLS server and a temporary fixture certificate, with
  certificate bypass limited to that browser context. Application origin and CSP
  restrictions were retained.
- That first attempt also exposed duplicate sibling React keys. Integration
  controls now have a distinct key and mount only inside Team, clearing one-time
  secrets when the owner leaves that view.
- A frontend lint finding was repaired by separating asynchronous reads from
  state updates. Post-save reload failure now reports a completed write honestly.
- Visual review found default typography and a technical measure alias in the
  embedded view. Local styles and saved metadata labels repair presentation;
  exact raw calculation evidence remains unchanged and is asserted separately.
- Final capture-only rerun resets iframe scroll after receipt inspection. No
  product behavior changed in that rerun.

Ignored evidence is under `data/verification/2026-10-16/remaining-work/`:
`integration-all-recheck.xml`, `integration-cancellation-recheck.xml`,
`webhook-transport-final.log`, `webhook-refresh-final.xml`,
`integration-{units,types,lint,ruff,mypy}-final.log`,
`integration-browser-captures.log` and `integrations-browser/`. Initial attempts
remain alongside the passing logs.

## Remaining acceptance

The parent release process must still run its combined compatibility/build gates,
preserve existing data across migration, deploy and verify the private demo.
These focused local checks are not representative security, cross-browser or
sustained-load acceptance. Real customer TLS/origin, host authentication and any
approved external receiver require actual operator/customer inputs. Webhook
delivery remains disabled unless both protected operator settings are supplied.
