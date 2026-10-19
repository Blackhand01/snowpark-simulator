# Resource-bounded 4D Gaussian Splatting: audit and design

Date: 18 October 2026. **DESIGN FOR HUMAN REVIEW — NO EXECUTION AUTHORIZED.**

This dossier designs a reproducible reconstruction and playback pipeline for the snowpark, moving athlete and equipment. The objective is the lowest **demonstrated total cost that satisfies agreed quality gates**, using the declared M1 / 8 GB Mac and only free Colab for remote computation. It does not establish that any proposed pipeline already meets those gates.

Terminology: a Gaussian is an oriented translucent 3D primitive; splatting projects/composites these primitives into images. A canonical model is the reference shape before time-dependent deformation. SH means spherical harmonics, coefficients for view-dependent color; a bounding-box ROI is a rectangular region of interest. GPU means graphics processing unit; CUDA is NVIDIA's GPU programming platform; RSS is process resident memory. SMPL is a learned parametric human-body model; skinning attaches surface points to articulated bones. Densification adds/splits primitives; pruning removes them. The experiment plan defines PSNR/SSIM image metrics and their limits.

## Sequential optimization decision

Before selecting each factor, compare use-case-relevant alternatives in the [stage-by-stage literature review](07-use-case-literature-review.md) and [stage-review template](templates/stage-review.md). DSD-GS is now a focused decomposition/reuse candidate, with rail-occlusion and code-readiness constraints; it is not a selected backend.

Evaluate **every resource-relevant stage, one aspect at a time**. Each candidate Ck starts from the last human-accepted configuration A(k-1) and reports both **Ck versus original pilot B0** and **Ck versus A(k-1)**. Keep B0 immutable. Accepting a candidate appends a new reference; rejection or inconclusive evidence leaves the parent unchanged. The [sequential protocol](06-sequential-optimization.md) and [experiment card](templates/experiment-card.md) govern all assignments.

A1 (static background fitted once plus a localized dynamic foreground, jointly depth-composited) remains a promising architecture candidate. HUST provides the existing control and a low-integration-cost first option; another SOTA backend may replace it if separately tested quality and total cost justify the change. Sparse controls (A2) and articulation (A3) remain alternatives. Diagnose the entire pipeline first, then use an ordinary longer-training control before attributing gains to a more complex reconstruction method.

Why: the current CUDA path already completed training and export; its small foreground, uniform loss, random initialization and missing seen-view diagnostics provide actionable uncertainties. The evidence does **not** establish that 8 GB Mac memory or T4 capacity caused the failed reconstruction. Backend replacement must include integration, preprocessing, weights and maintenance costs; this is a comparison requirement, not a prohibition on replacement.

## Reading order and deliverables

1. [Verified baseline and evidence limits](01-baseline-audit.md): actual scene → capture → training → evaluation → later export; facts versus hypotheses.
2. [Literature, implementations and Benini/PULP principles](02-literature-and-codesign.md): source-linked candidate cards, resource and license limits, independent evidence.
3. [Local PDF inventory](local-paper-inventory.md) and [machine-readable inventory](local-paper-inventory.json): physical files, extraction coverage and version differences.
4. [Architecture, diagrams and module contracts](03-architecture-and-contracts.md): admitted inputs, coordinates, data ownership, execution placement and recovery.
5. [Budgets, intervention matrix and experiments](04-budgets-and-experiments.md): proposed thresholds, cost accounting, ablations and stopping rules.
6. [Sequential optimization protocol](06-sequential-optimization.md) and [blank experiment/result card](templates/experiment-card.md): all-stage coverage, single-factor treatments, dual references, scope changes and human promotion.
7. [Agent assignment guide](05-agent-prompts.md): nine independently assignable prompts, ordering, ownership and explicit validation gates.
8. [Audit preservation report](preservation-review.md), [initial inventory](preservation-before.json) and [final comparison](preservation-review.json).
9. [Document validation](design-validation.json): link, JSON, prompt-field and diagram-source checks; no application or training tests.

## What is established

- Current repository verified for this revision: `/Users/stefanoroybisignano/Desktop/GaussianSplatting/synthetic-scene-simulator`. The former `Idea-Validation/` path no longer exists. Original baseline HEAD `b2358624690762381e69194d552c5cc68d5fa574`.
- Existing pilot: 496 observations, 640×480, 16 calibrated cameras, 31 instants; 300 fitting observations. Dynamic training took about 183 s in the historical T4 run and ended with 17,507 Gaussians. Athlete-region novel-view quality failed the historical criteria.
- The visible athlete/equipment mask covered about 1.31% of training pixels. This measures exposure, **not gradient contribution or causality**.
- A later export produced 31 PLY frames, with six exact backend reload comparisons. SuperSplat import/timeline was observed historically. A concurrent player task subsequently produced SOG frames and frame-advancement logs with stalls; sustained frame rate, fidelity and isolated Mac memory acceptance remain unresolved. See the timestamped addendum in the audit.
- Historical test outputs have been examined. They are development evidence, not an untouched final test.

## Evidence vocabulary

**CURRENT-READ**: source or artifact content read in this audit. **HISTORICAL-MEASURED**: measurement recorded by a previous run, not re-executed. **CALCULATED**: arithmetic with an explicit formula. **PROPOSED**: design or acceptance budget. **UNVERIFIED**: unavailable measurement, unread content or unresolved compatibility. Author-reported literature measurements are labelled separately; none are forecasts for a T4.

Some local files are FileProvider `dataless` placeholders. Metadata existence and a stored historical SHA-256 are not a fresh byte-integrity check. Eight of 42 local PDF files extracted successfully in bounded reads; primary online versions filled selected gaps. Unread works are not evidence for technical claims.

## Decisions needed before assigning any prompt

| Decision | Recommended starting choice | Consequence |
| --- | --- | --- |
| Quality target | Approve or revise Q1–Q6 in the experiment plan | No resource minimization before quality is defined |
| Scientific protocol | I1 with individually declared pretrained priors is a recommended option pending approval; retain I0 as prior-free control | Original Blender masks/depth/rig require separate assisted protocols; no weights/downloads implicitly authorized |
| Architecture | A1 is a candidate; select one factor/backend treatment after whole-pipeline diagnosis | No fixed backend; A2/A3 or a package replacement require their own costed comparison |
| Next phase | P01 preparation of B0, A0, stage ledger and one exact comparison card | No improved configuration is assumed accepted; approval of the dossier does not launch any prompt |
| Compute ceiling | Proposed 20 min GPU training/run and 120 min first screening campaign | Availability of any free GPU remains unknown |
| Coverage | Decide short-clip diagnosis versus separately budgeted full 0–5.02-s action | Current README records full-action intent; pilot only covers 0.9–1.9 s. Compare common scope or label unavailable |
| Final independence | Approve a future sealed capture plan if a final claim is required | No new capture or dataset is produced now |
| License scope | Keep research evaluation; resolve component terms before external/commercial distribution | Root repository licenses do not clear renderer, body models or weights |

Critical gaps: seen-training-view regional metrics; actual gradient/visibility distribution; equipment-specific labels; full process/device memory; initialization coverage; robust image-derived segmentation; current free Colab environment; complete runtime defaults file hydration; human-body prior compatibility; independent viewer parity and playback.

The repository's existing `.gitignore` excludes chronological design subdirectories. These deliverables are local and not staged or committed; that policy was not changed. Open this entry file directly rather than expecting a Git diff to list the dossier.

## Revision record

The [sequential revision record](revisions/2026-10-18-sequential/README.md) preserves the previous dossier in an archive and records documentation-only checks. Historical measurements are not overwritten by new results.

## Scope and stop

This work read source, existing reports and selected existing images; extracted readable PDFs; consulted primary external sources; and wrote this design directory. No agents were activated, implementation changed, dependencies installed, models trained, captures generated or viewers newly benchmarked. `Thesis` and `OmniStance` were used only for reading. Concurrent work outside this directory is preserved and identified in the preservation report. **Stop here for human validation.**
