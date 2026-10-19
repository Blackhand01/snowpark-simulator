# Single-factor experiment and result card — blank template

**Status: UNASSIGNED / NOT AUTHORIZED.** Copy into a new decision directory; do not fill unknowns with plausible values. This template is documentation, not an executable configuration. Apply the [sequential protocol](../06-sequential-optimization.md).

## Assignment and identities

Required prerequisite: completed [stage review](stage-review.md), with compared alternatives, primary evidence, case-specific assumptions and human selection. Its ID/hash must accompany this card.

| Field | Required value before execution |
| --- | --- |
| Experiment ID / scope epoch | UNASSIGNED |
| Prompt number / exact phase and mode | UNASSIGNED |
| Human authorization reference / timestamp / scope | UNASSIGNED |
| Pipeline stage / hypothesis / SOTA paper-section-code source | UNASSIGNED |
| B0 mode / original artifact-config-data-evaluator identities | UNRESOLVED; immutable original, not current HEAD |
| Accepted parent ID / human acceptance evidence | A0 initially references the chosen B0 mode; otherwise UNRESOLVED |
| Candidate ID / code-config-dependency hashes | UNASSIGNED |
| One factor / before value / after value | UNASSIGNED |
| Necessary coupled consequences / inseparable package rationale | NONE DECLARED; justify explicitly if present |
| Fixed factors | Dataset/splits; protocol; scope; calibration; metrics/support; seeds; training budget/schedule; model capacity; precision; renderer; export/player, except named treatment |
| Input allowlist / forbidden inputs / weight hashes and licenses | UNRESOLVED |
| Duration / cameras / physical times / evaluation resolution | UNRESOLVED; do not extrapolate B0 silently |
| Required B0 replay / parent replay / ordinary scope-matched control | UNASSIGNED; each needs an authorized run ID or valid reuse evidence |
| Owned paths / excluded paths / independent reviewer | UNASSIGNED |
| Final-data policy | Development only unless separately authorized FINAL_VERIFICATION |

## Preregistered decision and execution plan

- Primary quality/resource outcome and minimum useful improvement: **UNRESOLVED**.
- Non-regression tolerances for athlete, equipment, background, novel views/times, temporal coherence and occlusions: **UNRESOLVED**.
- Metric-spec version, uncertainty/seed plan and visual panel IDs: **UNRESOLVED**.
- Comparison type: equal GPU-active training allowance, total cold cost, warm reuse scenario and common delivered quality/coverage; identify applicable views and limitations.
- Exact authorized candidate/control/replay runs: **NONE**. No run is inferred from this template.
- Total CPU/GPU/wall budget, memory ceilings, disk/transfer limits, remaining campaign budget and allocated retries: **UNRESOLVED**.
- Recovery: isolated new artifacts, verified resumable state, retained failures, cumulative budget across interruption, rollback only owned changes. No automatic resume.
- Stop: forbidden input, unapproved factor, missing identity/required dependency, nonfinite state, corrupted data, budget exhaustion, user cancellation; define stage-specific triggers before execution.
- Human validation point: **UNASSIGNED**. Positive reviewer advice is not promotion.

## All-stage cost and coverage ledger

Every stage must have measured evidence, a missing-measurement plan, or a justified deferral. For each row report B0/parent/candidate IDs, cold/warm time, CPU/GPU time, peak host/device memory, stored/decoded bytes and transfers where relevant. Distinguish measurements, estimates and limits. Missing is N/A, never zero. Avoid double-counting nested checkpoint/IO intervals.

| Stage | Evidence / bottleneck / proposed one-factor treatment | Status / missing check / budget |
| --- | --- | --- |
| Acquisition and labels | UNASSESSED | UNASSIGNED |
| Preparation, decode and caches | UNASSESSED | UNASSIGNED |
| Initialization and priors | UNASSESSED | UNASSIGNED |
| Representation and motion | UNASSESSED | UNASSIGNED |
| Training and sampling | UNASSESSED | UNASSIGNED |
| Rendering and precision | UNASSESSED | UNASSIGNED |
| Evaluation | UNASSESSED | UNASSIGNED |
| Transfers and copies | UNASSESSED | UNASSIGNED |
| Checkpoint, persistence and restart | UNASSESSED | UNASSIGNED |
| Export, compression and decode | UNASSESSED | UNASSIGNED |
| Visualization and interaction | UNASSESSED | UNASSIGNED |
| Environment/setup, failed attempts, development effort | UNASSESSED | UNASSIGNED |

## Results — fill only after an authorized execution

Create one row per metric and stratum; retain per-record data. Quality deltas use the metric's own units, e.g. dB for PSNR; lower is better only for error/cost metrics. Cost percentages use `100*(C-reference)/reference`, with N/A on zero or missing denominator. Each delta includes provenance, matching status and uncertainty.

| Metric / unit / region / stratum | B0 | Accepted parent | Candidate | C−B0 | C−parent | Comparability / uncertainty / evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Body/clothing PSNR/SSIM/shape | N/A | N/A | N/A | N/A | N/A | Not executed |
| Equipment fidelity and missing-part defects | N/A | N/A | N/A | N/A | N/A | Not executed |
| Background/rail/shadow quality | N/A | N/A | N/A | N/A | N/A | Not executed |
| New view / new time / joint quality | N/A | N/A | N/A | N/A | N/A | Not executed |
| Temporal residual and visual occlusion failures | N/A | N/A | N/A | N/A | N/A | Not executed |
| Per-stage and total cold/warm wall time | N/A | N/A | N/A | N/A | N/A | Not executed |
| GPU-active time and host/device peak memory | N/A | N/A | N/A | N/A | N/A | Not executed |
| Stored/encoded/decoded bytes and transfer bytes | N/A | N/A | N/A | N/A | N/A | Not executed |
| First display / unique fps / p95 frame time | N/A | N/A | N/A | N/A | N/A | Not executed |
| Save/restart overhead, failures, development effort | N/A | N/A | N/A | N/A | N/A | Not executed |

Ordinary-backend control results, if required, appear in an additional table with the same boundaries; they never replace B0. For scope changes, report B0 only on valid overlap and name the new scope-matched control. State whether results support a component, package or whole-pipeline claim. Energy is unmeasured unless an actual energy measurement method and units exist.

## Review and human decision

- Checks actually executed / not executed; artifacts and hashes: **NOT EXECUTED**.
- Independent recommendation: **NOT REVIEWED** (accept for development / reject / inconclusive; final gates separately stated).
- Final quality status: **NOT VERIFIED**. An intermediate accepted configuration can still fail final gates.
- Human decision / timestamp: **PENDING**.
- On explicit acceptance: append Ak with full immutable chain and acceptance evidence. On rejection/inconclusive: retain A(k-1). Preserve every candidate and used-budget record.
- Next action: **STOP**. A proposed next factor is not authorization. Interaction tests require separately approved cells and budget.
