# Budgets, priorities and experimental protocol

Everything labelled PROPOSED requires approval before execution. The current assignment has no experimental authorization.

## Normative sequential comparison

Apply [the complete-pipeline sequential protocol](06-sequential-optimization.md) and [experiment card](templates/experiment-card.md) to every intervention below. B0 is the immutable original pilot; A(k-1) is the last explicitly accepted configuration; Ck differs from that parent by exactly one declared factor. Every result reports Ck−B0 and Ck−A(k-1), with matched-comparison limits. A0 initially references the declared B0 mode; no improved stack has been accepted by this document. Whole-pipeline diagnosis determines priority; no resource-heavy stage is omitted from the ledger.

The O labels below are intervention families, not permission to combine their mechanisms. Split/freeze, cache/layout/workers, compression/window/quantization and camera count/placement/resolution must be split into atomic comparisons wherever independently controllable. An inseparable backend package is explicitly a package-level treatment.

## Objective and acceptance before optimization

First satisfy quality and reproducibility, then minimize total cold end-to-end wall time under hard memory/storage limits. Report warm repeat cost separately. GPU time is a scarce free-service resource; developer effort and maintenance also matter. Do not combine time, bytes and quality into an arbitrary single weighted score.

Q1–Q6 are proposed engineering thresholds, not established perceptual truth or already agreed targets. Keep the historical bbox scores for continuity while adding exact region scores to avoid background dominance. The thresholds apply separately to new-view, new-time and joint new-view/new-time strata.

| Gate | Proposed acceptance |
| --- | --- |
| Q1 Foreground fidelity | Macro mean visible-pixel PSNR ≥23 dB separately for body/clothing and equipment; ≥90% of valid frames ≥20 dB. Also report combined historical bbox PSNR and SSIM; bbox SSIM ≥0.85 |
| Q2 Shape/occlusion | Visible-foreground silhouette intersection-over-union ≥0.90; no missing ski/limb, rail ordering reversal or transparent body in the preregistered visual set. Each failure is retained, not filtered from scoring |
| Q3 Static scene and snow | Background PSNR no more than 0.2 dB worse than the matched static reference; stable non-shadow regions must not acquire temporal motion. Report rail and moving-shadow subsets separately where labels exist |
| Q4 Temporal stability | At least 25% reduction of the historical error-image temporal residual against the matched static control, with no worse foreground fidelity; report absolute residual too. Visual real-time and slow playback must show coherent limbs/equipment and no popping at occlusions |
| Q5 Export and playback | Lossless same-renderer round-trip max absolute error ≤1e-6 on declared cameras/times; lossy variant foreground PSNR drop ≤0.2 dB and SSIM drop ≤0.005. Mac target sustained 30 displayed unique fps at 640×480, p95 frame time ≤40 ms, five loops with no growing memory, successful pause/seek/orbit/pan/zoom |
| Q6 Resource/reproducibility | All input/protocol/code identities recorded; no forbidden input; hard limits below respected; local recovery bundle verified; independent evaluator can reproduce score aggregation |

If body/equipment evaluation masks are unavailable, Q1/Q2 are **inconclusive**, not passed by substituting a larger combined bbox. SSIM on regions too small for its window is not valid; report missingness and exact-mask PSNR/MAE instead. An overly demanding gate can be revised only before opening the final test, with an explicit versioned rationale. A slower every-frame player may still be useful, but does not meet the stated 30-fps gate.

## Metrics and aggregation contract

For mask M and RGB values in [0,1], `MSE_M = sum(M*(prediction-reference)^2)/(3*sum(M))`; `PSNR_M = -10*log10(max(MSE_M,1e-12))`. PSNR measures pixel error, in decibels; it can reward blur and is sensitive to alignment. An empty mask returns `not_applicable`, not 120 dB. Record both macro average of frame dB and pooled-pixel MSE/PSNR; never confuse the two. MAE is mean absolute RGB error on the same support.

SSIM (structural similarity) compares local luminance, contrast and structure. Preserve the historical scikit-image settings: Gaussian sigma 1.5, data_range=1, RGB channel axis, population covariance. Report the exact bounding box and window valid support. Do not black out the background and call the resulting score pure foreground SSIM. Freeze whether scoring uses float predictions or uint8 round-trip; historical comparison must use the historical uint8 path, with a separate float diagnostic if useful.

Silhouette IoU is intersection divided by union of visible foreground supports; foreground visibility must account for static rail occlusion. A standalone foreground alpha render without rail depth is not sufficient. Fix the predicted alpha threshold at 0.5 in the preregistration, do not tune it on final masks. Boundary F-score within 2 px is a secondary thin-equipment diagnostic, not a replacement for missing parts.

Historical temporal metric: `e_t = prediction_t-reference_t`; average `abs(e_(t+dt)-e_t)` over the union of the two foreground bboxes. Record physical dt and normalize comparisons to the same dt; this is a residual-change measure, not true scene flow. For future dense clips, add motion-compensated residuals using **evaluation-only** known correspondences/visibility, and report disocclusion separately. Original motion may score a model but cannot be used to train I0/I1. Do not assume Gaussian nearest neighbors are ground-truth material correspondences.

LPIPS (learned perceptual image patch similarity) is optional: specify network/version, weight hash, color normalization and crop policy, account for inference cost and license. It is not initially a hard gate and can be unreliable on a tiny athlete crop. Geometry depth error (meters), normal error (degrees) and equipment endpoint motion error are optional evaluator-only diagnostics; Gaussian expected depth is not automatically a physical surface depth.

Aggregate per camera, time, body, equipment, rail, stable snow and shadow; include means, medians, p10, worst cases and fraction below threshold. Confidence intervals should resample camera/temporal blocks, not pretend adjacent pixels/frames are independent. One scene cannot establish generalization to other people, tricks or real data.

## Historical costs versus design ceilings

MiB/GiB use powers of two; paper GB/MB retain their stated units. These ceilings are safeguards and decision budgets, not performance predictions.

| Component | Historical evidence | Proposed next-stage ceiling / target |
| --- | --- | --- |
| Existing-artifact preparation | Hydration/validation sometimes slow; full current RSS NR | Mac process tree ≤4 GiB; one decoder/worker initially; ≤15 min CPU phase, then report blocker |
| New capture, only if separately approved | 496 images / 82.06 min render time, 640×480×24 samples | No capture now. First future sealed extension ≤220 RGB observations; ≤60 min wall target / 90 min hard stop, preserve partial output |
| I0 segmentation/triangulation | Not measured | ≤10 min CPU or ≤5 GPU min per dataset, ≤2 GiB temporary buffers; otherwise simplify or stop |
| I1 pretrained initialization | EDGS paper ~15 GB A100 peak, not local | No automatic permission. ≤10 GPU min and same device limit only after compatibility audit; stop if infeasible |
| Colab environment/probe | Legacy environment and T4 worked historically | ≤30 min setup attempt; no repeated dependency churn or paid upgrade; record current hardware and license closure first |
| Existing checkpoint diagnosis | Historical final evaluation ~52 s/model | ≤5 GPU min total inference, ≤10 min wall, ≤2 GiB new artifacts; zero optimizer/backward steps |
| Static + foreground training, one candidate | Historical 154.55/183.22 s processes | ≤20 min GPU-active training total across static and dynamic stages/run; hard wall ≤30 min; start stage allocation 5+15 min, not 20+20 |
| First screening campaign | No new run | ≤120 GPU min training across individually approved runs; diagnostic/setup/evaluation separately charged. No automatic sweep |
| Evaluation | ~52 s/model + 3.17 s comparison historically | ≤5 GPU min/run, ≤10 min wall; regional tables before optional videos |
| Checkpoints | Dynamic fine checkpoint logical ~42.1 MB; content dataless here | ≤1 GiB/run for resumable state/logs, ≤4 GiB all new run artifacts, ≤8 GiB active campaign |
| Export | 8.34 s loop; 134.64 MB PLY total; 89.98 MB downloaded archive | ≤5 GPU min; retain source model, reference frames and manifest; total experiment transfer ≤1 GiB target |
| Viewer | Earlier import; concurrent UI snapshots 5–8.6 effective fps with stalls, full acceptance NR | Additional player process-tree footprint ≤1 GiB target; green macOS memory pressure, no growing swap; stop if total work exceeds 4 GiB incremental footprint |
| Local disk | Capture historically stopped below 8 GiB | Require free space ≥8 GiB **after** estimated transient allocation; never delete historical artifacts to make a run fit |

GPU device-memory policy: soft target ≤8 GiB total process use, hard limit ≤min(12 GiB, currently available device memory minus 2 GiB reserve). Also log torch allocated/reserved separately. Colab host-RAM hard limit is min(6 GiB, available host RAM minus 2 GiB); if unavailable, stop before loading a potentially large model. Historical 0.20 GiB torch allocated does not prove total GPU memory was that small. M1 unified memory is shared among OS, CPU and GPU; a separate “8 GB GPU budget” does not exist.

Concurrent SOG conversion records add a provisional 148.16 s successful conversion and 22.18 MB encoded output, plus a terminated 127.51 s attempt. Include failed-attempt cost when assessing that path; the encoded 6.07× ratio is not a free training or decoded-memory reduction. These records are summarized in the baseline addendum and must be refreshed before P08.

## Explicit storage/memory calculations

These are **CALCULATED raw-array lower bounds**, not measured process peaks:

- One RGB frame: `640*480*3 = 921,600` bytes as uint8; `3,686,400` as FP32. All 300 fitting frames decoded FP32 require 1,105,920,000 bytes before metadata, duplicates or GPU copies. Keep PNG on disk and a bounded cache unless measured preload benefits justify it.
- Legacy degree-3 PLY: `248*N + header` bytes. For N=17,507, the actual file is 4,343,266 bytes. Thirty-one frames total 134,641,246 bytes. At the same N, 300 frames would require about 1.30 GB before headers/compression; this is linear storage arithmetic, not a quality forecast.
- A 59-float trainable Gaussian attribute vector is 236 bytes. Parameters + gradients + two Adam moment vectors are at least `944*N` bytes in FP32; N=200k gives 188.8 MB **before** deformation fields, activations, tile lists, visibility buffers and images. The Gaussian-count guard is not a complete memory model.
- Full FP32 RGB cache for 12 cameras: `12*640*480*3*4 = 44,236,800` bytes; alpha/depth and GPU duplication add cost. Such an RGB cache is not valid for arbitrary rail occlusion. Projection-cache footprint must be measured from actual array shapes.
- Static-once representation bytes: `B_static + T*B_foreground + B_motion_metadata`; full bake: `T*(B_static+B_foreground)`. The symbolic saving is `(T-1)*B_static`, but the actual split counts and player support are unknown. Do not claim a measured saving.
- Crop enlargement by 2× in each direction quadruples pixels/work for that crop, not information content. A crop cannot restore an equipment detail absent from the original samples.

Before upload, require space for archive + unpacked input + maximum checkpoint/output + a second temporary atomic-save copy + 8 GiB reserve. Download only after checking archive and expanded sizes; avoid three untracked copies. Hash caches are keyed by source hash/config/tool versions, not “latest” filenames.

## Cost accounting and Pareto comparison

For each model record `T_cold = acquisition + preprocessing + cold environment + transfer + fitting + evaluation + export + first display`, with non-overlapping phase boundaries. Report queue/wait separately from active compute. `T_warm` excludes only genuinely reusable cache work and names the reuse count. Repeated failed installs, retries and interrupted work belong to total cost. Static reuse amortization after k clips is `T_static/k`, but also report the first-clip cost.

The current two historical points illustrate the distinction, not an optimized frontier:

| Historical mode | Training process seconds | Spatial foreground bbox PSNR | Quality feasible? |
| --- | ---: | ---: | --- |
| Static | 154.55 | 12.8792 | No |
| Dynamic | 183.22 | 12.9631 | No |

For future results, retain a table/plot of foreground quality versus cold total time, marking memory/quality violations and showing encoded bytes as a separate axis. A point is dominated only if another is no worse in all agreed costs/quality and strictly better in at least one. Published speedups cannot be multiplied to create predicted points.

## Intervention matrix

Each family must pass the [use-case literature selection gate](07-use-case-literature-review.md) before an atomic experiment is assigned. The matrix lists hypotheses, not already selected optimizations.

Development estimates below are planning ranges in focused engineer-days (one day ≈6 productive hours), not commitments. “High uncertainty” means benefit remains unmeasured on the snowpark.

| ID / bottleneck | Mechanism / expected benefit | Uncertainty and quality risk | Development cost; dependencies/incompatibilities | Minimum approved experiment |
| --- | --- | --- | --- | --- |
| D0 Unknown failure mode and cost distribution | Whole-pipeline ledger plus seen-view regional diagnostics separates fit from generalization | Low execution risk; masks may remain combined | 0.5–1 d; evaluator C9, existing checkpoint | Frozen inference, full train/val regional matrix; no training |
| O0 Possibly short optimization | Ordinary backend with longer schedule; tests whether architecture work is necessary | More time may overfit; cost increases | 0.25–0.5 d; complete resolved defaults; no bundled model change | Same initializer/data, 3/10/20-min learning curve, one approved run with checkpoints |
| O1 Foreground diluted in loss | Class-normalized L1 retaining full image term | Mask errors amplify; background may degrade | 0.5–1 d; C3/C6; incompatible with GT masks in I0 | O0 versus weighted loss, same GPU time and seed |
| O2 Redundant static deformation/interference | Fit background once, freeze, localize deformation | Mask holes, shadow residuals, seam/occlusion errors | 2–4 d; C3–C5; flat RGB compositing disallowed | Accepted parent versus split OR freeze; declare inseparable coupling, charge static cost |
| O3 Poor geometric start | Training-only static/same-time triangulation | Snow texture and small athlete may produce wrong geometry | 1–2 d I0; 2–3 d I1 port; no mixed-time moving-point triangulation | Random versus matched initializer; equal fitting time and separate total-cost comparison |
| O4 Inefficient observation sampling | Mix uniform and foreground/occlusion/residual samples | Overfits hard views, changes objective | 0.5–1 d; training-only residuals; exclude validation/test sampling | Same loss/model, log probabilities and camera balance |
| O5 Insufficient capacity | Restore one plane scale or deformation depth; later density schedule | More parameters may hide bad calibration | 0.5 d; telemetry and ordinary controls | One capacity axis at a time at equal GPU time |
| O6 Equipment deforms implausibly | Rigid per-part transforms or sparse controls | Incorrect part assignment, rigid assumption fails | 2–4 d; image part tracks; original rig only A-R | One ski/equipment subgroup; compare residual and visibility |
| O7 Moving shadows corrupt geometry | Geometry-fixed time-varying appearance residual | Could memorize silhouettes; apparent relief may be lost | 1–3 d; shadow-confidence/evaluation contract | Same frozen geometry, appearance residual on/off |
| O8 Data movement / repeated raster work | Bounded decoding, cached static attributes, later projection reuse | Stale cache or changed depth order | 0.5–1 d buffers; 2–4 d custom raster cache | Profile first; exact-render parity and end-to-end timing |
| O9 Training/device memory | Mixed precision for supported operations; FP32 sensitive state | Gradient underflow, unstable covariance/opacity; CUDA support uncertain | 1–3 d; renderer audit; avoid global autocast assumption | Fixed tiny input numerical/gradient parity, then one timed run |
| O10 Output size/playback | Static-once package, frame window, later SH/quantization/pruning | Thin skis disappear, decoder stalls; player format mismatch | 0.5–1 d existing player; custom format >3 d requires new decision | Full PLY baseline then one codec/window change with frozen model |
| O11 Missing source detail | Future closer/targeted cameras or resolution, uniform-control capture | New data changes information and total capture cost | 1–2 d planning; separate acquisition approval | Equal rendered-pixel/capture-time design; no resampling pretended as detail recovery |

Do not combine O1/O2/O3/O4 in one treatment. O8/O9 need a demonstrated runtime/memory bottleneck; O10 cannot repair failed reconstruction. A2/A3 or another backend may be selected after diagnosis and dependency review, with a separately approved package comparison. The all-stage ledger also covers transfers, checkpoint recovery and evaluation overhead; see the atomic candidate queue in the sequential protocol.

## Progressive experiment sequence

1. **P01 preparation** freezes B0, A0, protocol, scope, budgets, metrics and code/data identities; prepare the all-stage ledger and one comparison card. I1 priors are an option awaiting approval. Complete documentation and missing-field list; stop.
2. **D0 whole-pipeline diagnosis** starts with existing acquisition/preparation/transfer/training/export/player records and identifies missing measurements. Only separately approved measurements are executed. Diagnostic inference after evaluator implementation/review uses existing static/dynamic checkpoints, train/validation and already-consulted historical held-outs. Record seen/new camera/new time/joint matrix and all missing labels. No optimizer steps.
3. **O0 ordinary control**: same HUST family, data and random initialization; permit only explicitly documented schedule extension so learning rate/densification remain meaningful. Record snapshots at 3, 10 and 20 GPU minutes (if authorized). A larger model or restored plane scale is a separate O5 control, not silently bundled.
4. **O1** loss balancing versus the accepted parent, with B0 and the matched ordinary O0 control retained, at the same GPU-active training budget, same machine/session when possible, same seed and evaluation. A second comparison subtracts preprocessing from a fixed end-to-end budget; report both, even if rankings reverse.
5. Provisional reconstruction queue: **O3 initialization**, then **O2 static/dynamic separation**, then sampling/capacity/motion factors as justified. This is a queue, not a mandate: select the next stage from measured bottlenecks. Split and freeze are separate treatments where technically separable. Every Ck is compared with B0 and its accepted parent; static preprocessing/fitting is charged. Human rejection leaves the parent unchanged.
6. Repeat only the provisional winner and matched ordinary control with three seeds if the initial effect exceeds noise and quality risk is acceptable; total extra budget needs approval. Randomize run order where practical. Different GPU types/versions invalidate a direct timing pair unless a matched control is rerun; never analytically rescale RTX 4090/A100 timing to T4.
7. Evaluate one resource factor at a time across preparation, transfers, checkpoints, evaluation, rendering, export and visualization. Lossless infrastructure experiments can precede final quality feasibility if their parity is verified. Defer lossy compression/pruning until fidelity can be meaningfully judged. No pruning to make an invisible athlete faster.
8. Freeze final configuration, thresholds and hashes before the independent final evaluator receives sealed assets. Once final results are inspected, further changes create a new development cycle requiring a new final holdout.

## New acquisition and final-test independence — design only

Existing camera/time tests are contaminated by development inspection. A future **within-scene** final set can use new camera positions plus source times absent from all fitting and validation. It will not prove cross-scene generalization.

The following 220-image example covers the original short pilot only. The currently recorded full 0–5.02-s requirement changes acquisition/time normalization and needs a new scope card, ordinary scope-matched reference and budget; neither capture nor training is authorized here.

Proposed sealed extension ceiling: four new cameras ×31 original times =124 spatial observations; 12 fitting cameras ×six new physical times =72 temporal observations; four new cameras ×six new times =24 joint observations; total 220. A custodian freezes exact positions and midpoint source frames before any pixel inspection; for example source frames congruent to 3 modulo 4 lie between the pilot's frames congruent to 1 modulo 4. Final times must be absent from validation, masks, motion estimation and initialization too. Exact camera placement/time list is a P01 decision, not permission to capture now.

Do not improve training acquisition with final-image residuals. For O11 training cameras, optimize image-derived coverage/athlete pixel size and occlusion diversity from development data, compare to uniform capture at the same rendered-pixel or wall-time budget, and preserve the sealed final set. More magnification may truncate equipment; require full-body/equipment margin and views on both sides of the rail. Temporal sampling must cover high projected motion and contact/occlusion changes; 30 Hz is a historical choice, not a validated sampling bound. Capture controls must report exposure/noise/blur and synchronization assumptions. All synthetic render and label costs are charged.

## Positive, negative and inconclusive outcomes

- **Development promotion:** a candidate meets its preregistered incremental benefit and quality non-regression limits against its accepted parent, with cumulative B0 results disclosed. It may be `ACCEPTED_FOR_DEVELOPMENT` by the human while final Q gates still fail. This is not final success and does not consume the sealed test. The 15% figure below is a proposed final criterion, not a mandatory threshold at every step.
- **Positive quality result:** all agreed Q gates pass on the sealed set, no protocol leak, and independent review confirms occlusions/equipment. “Optimization succeeds” additionally requires ≥15% lower cold total cost than a matched quality-feasible ordinary control, or a separately approved material resource improvement without quality loss. Report uncertainty and all trials.
- **Negative:** under a valid matched experiment, a change worsens Q1/Q2/Q3, does not meet the declared improvement, or increases total cost without achieving a required quality threshold. Preserve and reject it; a faster training loop alone is not sufficient.
- **Inconclusive:** missing class labels, interrupted run, no comparable GPU, unverifiable resume, protocol leak, unavailable weights/license, unmatched preprocessing, insufficient seeds or effect within uncertainty. Lack of a free GPU is not a negative scientific result.
- **Stop immediately:** nonfinite states, invalid calibration/schema/provenance, forbidden data access, memory/disk ceilings, corrupt checkpoint, runtime approaching the 30-min run ceiling, or user cancellation. Save only valid bounded evidence; do not resume automatically or buy capacity.
- **Stop the affected branch:** ordinary fitting dominates a more complex architecture; missing image information requires separately approved acquisition; or two approved single-factor attempts fail while cost rises. Preserve the accepted parent and reassess with the human. Other pipeline stages remain in the ledger; success of ordinary training does not end transfer/export/playback optimization. Exhausted total budget stops execution, not evidence retention.

No result in this dossier authorizes any of these experiments.
