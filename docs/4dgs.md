# 4D Gaussian Splatting: experiment status and viewing

The pilot asks whether one time-conditioned Gaussian model reconstructs the
athlete's rail reorientation at unseen camera angles and intermediate times.
The static control and dynamic model use the same inputs and iteration budget.
This is an image-reconstruction experiment, not a biomechanics validation.

## Inputs and scope

The profile in [`4dgs-pilot.json`](../configs/capture/4dgs-pilot.json) is deliberately
tied to the approved local boardslide scene and its SHA-256 hash. The scene and
datasets are excluded from Git. A fresh clone can reproduce the static demo;
it cannot recreate this exact pilot without that approved input artifact.

The capture covers scene time 0.9–1.9 s, frames 109–229 at 120 fps, sampled at
30 Hz. Sixteen fixed cameras on two elevation rings produce 496 RGB images at
640×480, with an evaluation-only visible-athlete mask from the same Cycles render.
Capture leaves the source animation intact but exports only that one-second
window. It never rebuilds terrain, rail or clothing.

| Partition | Images | Role |
| --- | --- | --- |
| Training | 300 | 12 cameras × 25 times |
| Validation | 62 | 2 cameras × 31 times; available during fitting |
| Final spatial test | 62 | 2 further cameras × 31 times |
| Final temporal test | 72 | 12 training cameras × 6 times excluded from fitting |

Initialization is one shared 10,000-point random cloud derived from training
camera axes/radius only. Meshes, masks, depth, bones and previous reconstructions
do not initialize or supervise the model. The world/model similarity transform
is recorded so scene coordinates remain interpretable.

## Local capture and verification

Use a **new** output directory for every attempt. Example commands, from the
repository root on the supported Mac installation:

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --offline-mode --disable-autoexec --python-exit-code 1 \
  outputs/boardslide-synced-20261017T182924-532391Z/snowpark-motion.blend \
  --python scripts/capture_motion.py -- \
  --plan configs/capture/4dgs-pilot.json \
  --output outputs/MY_NEW_PILOT/capture

python3 -B tools/prepare_4dgs.py \
  --source outputs/MY_NEW_PILOT/capture \
  --output outputs/MY_NEW_PILOT/colab-data \
  --bundle outputs/MY_NEW_PILOT/pilot-input.zip
```

Add `--smoke` to the Blender command for two real 64×48, one-sample export checks;
that output is intentionally rejected as a full training dataset. The full
capture uses 24 Cycles samples, four threads and seed 1729. It stops below
8 GiB free disk or after 2.5 hours. It writes a new `.blend`, RGB/masks,
camera calibration, pose hashes, frame/time IDs, per-image timings and records.

For an interrupted full-resolution capture, add `--resume-from outputs/OLD/capture`
and keep `--output` pointed at a **new** directory. Use the identical plan. Recovery
copies only hash-verified RGB/mask pairs, checks their poses and cameras against the
reopened source, and renders missing views. The original attempt remains unchanged;
the complete recovered dataset must still pass all host checks before fitting.

The host verifier requires a completed capture from the approved source and rejects
missing/changed images, empty masks, repeated RGB frames, frozen pose/time metadata,
moving capture cameras, changed intrinsics and train/test leakage. The bundle contains
only synthetic data, neutral metadata and the small pilot runner. No personal
reference image, reference video, secret, environment or unrelated project is included.

## Colab Free

Open [`4dgs_colab.ipynb`](../notebooks/4dgs_colab.ipynb) in Google Colab and select
**T4 GPU**, standard RAM. No cell provisions a paid runtime, purchases compute
units, mounts Drive, starts SSH, or runs keep-alive code. Verify free-tier access
in Colab's Resources panel; availability and session duration are not guaranteed.
Upload `pilot-input.zip` when the notebook requests it.

The notebook isolates the legacy backend from Colab's newer Python. It records
Python, PyTorch, toolkit/compiler and GPU versions, pins the backend revision,
compiles its rasterizer and applies an auditable adapter. It then performs a
100-step render/backpropagation test using the **actual** training/validation
images. Full-model memory is different from an allocation or one-Gaussian test.
Fitting proceeds only after this model/calibration/memory check succeeds.
The smoke uses the initial 10,000 Gaussians; it does not establish peak memory
after densification. Resource checks continue during production fitting.

Each production run gets 500 coarse and 4,500 fine iterations. Static mode disables
all temporal deformation; dynamic mode enables position/scale/rotation deformation
while keeping opacity/color deformation disabled. Both start from the same cloud
and seed. Diagnostic weights are discarded. Stops: 30 minutes per model,
12 GiB allocated GPU memory, 200,000 Gaussians and three hours for the notebook
session. Exceeding a limit is a recorded failure, not permission to shrink the protocol.

## Backend adaptation and licenses

The pinned [HUST 4DGaussians](https://github.com/hustvl/4DGaussians/tree/843d5ac636c37e4b611242287754f3d4ed150144)
synthetic loader otherwise forces 800×800 and assumes square dimensions. The
adapter preserves native resolution, fixes width/height and camera conversion,
uses declared views instead of a demo orbit, and records seeds/resources.
Camera matrices loaded on CUDA must agree with neutral calibration within 0.5 px.
Coarse initialization selects every camera whose normalized time is zero. The
upstream selector assumes a DyNeRF dataset wrapper and cannot handle the Blender
camera list. The adapter preserves zero-time initialization without relying on
camera ordering or an inferred dataset stride. The diagnostic loss explicitly
moves reference pixels onto the prediction's device before comparison.

`transforms_test.json` under the fitting directory contains **validation** views.
Final-test views enter a separate loader only after both models finish. Upstream
code otherwise uses its test views during fitting reports, so this distinction
is necessary to avoid leakage.

The exact pinned `simple-knn` tree lacks its referenced license file. It is neither
built nor executed. A bounded native PyTorch calculation supplies the mean squared
distance to three other points during initialization, checked against an
independent numerical reference. This does not remove the other license constraints:
the root repository is Apache-2.0, but retained Inria headers and the mandatory
[rasterizer license](https://github.com/ingra14m/depth-diff-gaussian-rasterization/blob/e49506654e8e11ed8a62d22bcb693e943fdecacf/LICENSE.md)
restrict components to non-commercial research/evaluation without further consent.
This pipeline is **not cleared for commercial sponsor work**.

## Evaluation and evidence

The evaluator reopens each model in a separate process and streams predictions
without holding a complete video in GPU memory. It saves two final-camera
comparison videos: reference, reconstruction and amplified absolute error.
The static control must produce identical pixels across times at each fixed camera;
otherwise evaluation stops. Hashes identify both the Gaussian cloud and deformation files.

Targets, separately for final spatial and temporal groups:

- Athlete region-of-interest (ROI) mean PSNR ≥23 dB and SSIM ≥0.85.
- At least 90% of images with ROI PSNR ≥20 dB.
- ROI PSNR improvement ≥3 dB over the static control.
- Background PSNR loss no greater than 1 dB versus the static control.
- Temporal residual-error reduction ≥25% at the two final spatial-test cameras.

PSNR measures pixel error; SSIM measures local structural similarity. The temporal
score compares consecutive reconstruction-error images over adjacent athlete ROIs;
it is not optical flow or a physical motion measurement. Full-frame scores are
context only because static snow can conceal a poor athlete reconstruction.

A quantitative pass still requires visual rejection of persistent ghost bodies,
severe transparency, missing equipment or rail deformation. The one-second pilot
does not establish full-trick, geometric, real-camera or commercial quality.

Download the result archive before leaving Colab. Checkpoints, configuration,
adapter patch, software records, timings, memory logs, predictions and metrics
must be preserved in a new local output directory. Public notebooks have empty
outputs; actual run evidence belongs in local `outputs/`.

## Observed Free T4 pilot: 18 October 2026

**Execution completed; reconstruction quality failed the declared acceptance criteria.**
The actual 496-image input passed archive/file hashes and camera checks. An isolated
Python 3.10.22 / PyTorch 1.13.1+cu117 environment and CUDA 11.8 compiler built the
pinned rasterizer on a Tesla T4 (15,360 MiB). The actual-data diagnostic completed
100 render/backpropagation steps; maximum camera reprojection error was 0.000020 px.
No paid runtime, subscription or compute-unit purchase was used.

| Model | Training time | Final Gaussians | Peak allocated CUDA memory |
| --- | ---: | ---: | ---: |
| Static control | 154.55 s | 16,636 | 137.1 MiB |
| Dynamic | 183.22 s | 17,507 | 204.8 MiB |

Both completed 500 coarse + 4,500 fine steps from the same random initialization.
Separate evaluation processes scored 134 final images per model. The static
control passed fixed-camera pixel invariance across time.

| Final group | Static athlete ROI PSNR | Dynamic athlete ROI PSNR | Dynamic ROI SSIM | Dynamic frames ≥20 dB |
| --- | ---: | ---: | ---: | ---: |
| New cameras | 12.88 dB | 12.96 dB | 0.631 | 0% |
| New times | 13.78 dB | 18.84 dB | 0.739 | 37.5% |

Only 2 of 11 predeclared checks passed. Temporal residual error improved by 1.50%,
below the required 25%; new-camera background PSNR also lost 2.10 dB. The temporal
gain alone does not establish a usable moving reconstruction. Neither the budget
nor the thresholds were adjusted after observing the test results. This run
establishes Free T4 feasibility for the bounded protocol, not acceptable novel-view
quality or suitability for presentation/sponsor use.

Two compatibility failures were retained: the diagnostic originally mixed CPU and
CUDA images, and the upstream coarse selector expected a DyNeRF wrapper. The fixes
above changed no data, splits or fitting parameters. A fresh adaptation of pristine
pinned sources reproduced the effective backend files byte for byte; 39 local
tests passed. The failed static attempt stopped before its first optimization step.

Visual review rejected all eight sampled new-camera dynamic comparisons (two
cameras, four times): severe transparency, missing equipment, weak rail detail and
colored floaters. Two held-out-time comparisons from training cameras showed a
blurred, incomplete athlete even where the rail was better reconstructed. Four
comparison videos decoded successfully; continuous playback was not visually
reviewed. These observations support the negative metric result, without isolating
its cause.

Local evidence is retained in `outputs/4dgs-pilot-20261018T101121-285573Z/`:
`REPORT.md`, `comparison.json`, integrity checks, source snapshots and extracted
`cloud-results/`. The 445,752,901-byte cloud archive passed SHA-256 and all ZIP CRC
checks (389 entries); final model hashes match the evaluation records. Archive
SHA-256: `1343ed2fa933535c706f59d76c96f3bee5b2152ba673330f7f846a2d97a2a1fb`.
Raw datasets, checkpoints and failed attempts remain local and excluded from Git.
The approved source scene and input archive retained their original content hashes.
Further training or protocol changes require a separate decision.

## Exported pilot animation

The evaluated dynamic checkpoint was exported without training into 31 numbered
PLY frames (17,507 Gaussians/frame; 134,641,246 bytes total). Six reload/render
comparisons matched the original backend exactly. Frame and checkpoint hashes
passed. SuperSplat 3.5.2 recognized the sequence and its 31-frame timeline, but
playback and navigation of the skier have not yet been validated interactively.

The export, integrity evidence and screenshots are in
`outputs/4dgs-ply-20261018T113620-018590Z/REPORT.md`. Reproduction uses
`python tools/export_4dgs.py --help` inside the existing backend CUDA environment;
the report and `cloud-export/execution.json` retain the executed command. The Mac
only needs a compatible viewer for these baked files, not the training backend.

[SuperSplat](https://developer.playcanvas.com/user-manual/supersplat/editor/import-export/)
remains an alternative for PLY-sequence inspection, with full-scene loading per
frame. Single-scene PLY support or a camera-path timeline in another viewer does
not establish support for an animated scene.

## Optional local viewer: Chronosplat

On 18 October 2026, the existing [Chronosplat](https://github.com/tcwilsonart/Chronosplat)
1.0.0 player (revision `2278aa9321d46e3d99f4a8174d37e676be91e5e0`) was built
without player-source changes and served only on localhost. No custom viewer,
paid service, public model upload or new training was used. Its official
SplatTransform 3.1.7 converter used the Apple M1 GPU; original PLY hashes remained
unchanged.

| Check | Observed result |
| --- | --- |
| Frame and Gaussian count | All 31 frames and 17,507 Gaussians/frame retained; degree-3 view-dependent color retained |
| Compression | PLY 134,641,246 bytes → SOG 22,181,056 bytes, approximately 6.07× smaller |
| Conversion | 148.16 s on Apple M1; one frame converted at a time |
| Playback | Approximately 22–24 effective fps against a 30-fps target; every-frame mode; five timeline wraps observed |
| Memory strategy | All 31 compressed frames cached for this short clip; zero failed loads in observed UI states |
| Memory verification | No out-of-memory failure observed; player-only unified/GPU memory was not isolated |
| Camera gestures | User manually confirmed orbit, zoom and pan while paused on 18 October 2026; the automated gesture checks remained interrupted |
| Reconstruction quality | Existing blur, incomplete athlete and novel-view artifacts remain |

SOG compresses each frame; it is not an inter-frame video codec. A six-frame cache
showed stalls and roughly 5–9 fps in sampled readings. Full caching improved this
short clip's usability but does **not** establish memory-bounded playback of a
longer sequence. No 30-fps or long-duration memory pass is claimed.

### Open the existing local run

From this repository root, restart the already built player if needed:

```sh
./outputs/4dgs-player-20261018T125220-542663Z/start-player.command
```

Then open this URL in Chrome:

<http://127.0.0.1:8765/?seq=snowpark-gpu&ahead=30&behind=0&concurrency=4&prebuffer=31&maxPixelRatio=1&paused=1&stats=1>

Play/Pause or Space controls time; the timeline seeks through the sequence.
The upstream controls provide left-drag orbit, right-drag pan and wheel zoom.
Pause leaves the camera available for bullet-time inspection. The user confirmed
that paused orbit, zoom and pan work. Reset restores the initial view; explicit
timeline-seeking verification remains open. `maxPixelRatio=1` reduces Retina
rendering cost without changing the model.
The presentation manifest uses the source scene's Z-up axis.

The helper serves `chronosplat/dist/` on `127.0.0.1` only; keep the server running
while viewing. It uses Python's standard file server and requires neither a new
conversion nor a training backend. The initial optional setup used Node ≥22,
Python/NumPy, `npm ci` from the upstream lockfile and `npm run build`. This local
run and its sequence are excluded from Git; a fresh repository clone does not
include the player installation or private model outputs.

See `outputs/4dgs-player-20261018T125220-542663Z/REPORT.md` for measurements,
compression comparisons, source pin and limitations. The three same-renderer
PLY/SOG pairs scored 49.28–51.86 dB PSNR; those global-image comparisons assess
compression, not athlete reconstruction quality. Reports retain source hashes,
commands, screenshots and OS memory samples. Historical output directories remain
unchanged.

## Dense export: 121 frames without training

On 18 October 2026 the evaluated dynamic checkpoint was reopened on **Colab Free
CPU**, using its pinned deformation network, and evaluated at 121 endpoint-inclusive
times over scene time **0.9–1.9 s**. The interval is 8.333 ms. No new capture,
training, optimizer, backward pass or paid resource was used. The 90 additional
states are model estimates; the failed reconstruction quality remains unchanged.

All 31 original times passed a CPU-versus-original-CUDA Gaussian-attribute check
(maximum absolute difference 9.54e-7). Their PLYs were then copied byte identically
into every fourth new output slot. The original export and all four evaluated
model-file hashes remain unchanged. This is an attribute comparison, not a new
CUDA render-parity test. The export loop took 12.04 s; the subprocess took 14.07 s.
All 121 downloaded file hashes and the archive CRC passed. Raw PLYs total 525.5 MB.

Exporter: [`tools/resample_4dgs.py`](../tools/resample_4dgs.py). Reproducible inputs,
the recovered result and current viewer evidence are retained locally in
`outputs/4dgs-121-20261018T153250-993896Z/REPORT.md`. The original 31-frame exporter
keeps its historical contract. The new exporter requires PyTorch, NumPy and
`plyfile`; these are not dependencies of the static Blender workflow.

Chronosplat loaded the actual 121-frame sequence. Paused keyboard seeking reached
frames **39 and 40**, corresponding to scene times **1.216667 and 1.225 s**, which
bracket the configured rotation-start marker at 1.218333 s. That marker describes
the source animation; it is not a measured onset in the imperfect reconstruction.
Native UI evidence is authoritative where browser DOM snapshots lag the canvas.
The completed SOG derivative contains all 121 frames (86.6 MB versus 525.5 MB
raw). Its hashes, ZIP CRC, 17,507 Gaussians/frame and degree-3 color passed checks.
The final player cached 121/121 frames with zero failures. Visible stats showed
approximately **60–60.1 effective fps** at a 120-fps target, with no buffering stalls
in those samples: every-frame playback therefore takes about two seconds for the
one-second action. Paused stepping 39 → 40 → 39 and the settled final pause were
verified. No isolated memory measurement or sustained 120-fps pass is claimed.
SOG is lossy; raw masters are retained. The report includes the final localhost
URL, screenshot and `start-player.command` for restarting the viewer.

The FPS field controls requested **playback speed**, not the number of saved
frames. All 121 files remain available at every setting. With every-frame mode,
120 fps requests approximately one second of playback; 60 fps requests two
seconds; 30 fps requests four seconds. If decoding/rendering is slower, playback
takes longer while preserving the frame order. The player holds the final endpoint
for another frame interval, so its nominal 120-fps loop reads 1.00833 s.
"Buffering 2/3" means two of three requested consecutive frames are ready before
starting; the supported `prebuffer=0` option removes this initial wait, without
removing any saved frames or guaranteeing stall-free playback.

## Next training requirement: complete 5.02-second action

**Requested on 18 October 2026; not captured or trained yet.** The next experiment
must reconstruct the full approved animated scene, including the athlete, skis,
rail and surrounding snowpark throughout the action. The source configuration
[`boardslide-synced.toml`](../configs/motion/boardslide-synced.toml) declares
5.02 seconds at 120 fps. The frozen local `build-report.json` records 5.02 seconds,
and the preview timing manifest records 3,012 ticks at 600 ticks/s, also 5.02 s.
These describe the approved synthetic animation, not measured physical dynamics.

| Required phase | Source-scene timing |
| --- | --- |
| Approach and entry takeoff | Start at 0 s; takeoff at 0.685 s |
| First rail contact | Approximately 0.918 s |
| Slide and reorientation | Contact through rail release at 2.085 s |
| Exit flight and landing | Snow contact at approximately 2.518 s |
| Recovery and run-out | Recovered at 3.02 s; continue through the 5.02-s scene end |

The current [`4dgs-pilot.json`](../configs/capture/4dgs-pilot.json) samples only
0.9–1.9 s, frames 109–229. Its 31 exported PLYs contain exactly the time window
that was captured and fitted. The proper approach, release, landing and run-out
are absent from that dataset. More exported frames or a longer playback timeline
cannot recover those missing observations from this checkpoint.

Requirements for the next separately versioned protocol:

- Capture the full 0–5.02-s source action with timestamp/frame provenance;
  include the actual first and last states, with the sampling/end-point rule
  declared explicitly. At approximately 30 Hz this is roughly 151–152 timestamps,
  not the present 31; the exact count depends on the chosen time grid.
- Check calibrated multi-camera coverage over the complete trajectory, including
  approach and run-out. Revisit the existing rail-centered framing so the athlete
  and equipment remain supported by sufficient views throughout the scene.
- Define fresh training, validation and held-out camera/time splits across all
  phases. Normalize time over the new complete interval and record the mapping;
  do not reuse the one-second interval's normalization.
- Reassess capture, fitting, storage and Mac playback budgets. Extending duration
  does not by itself resolve the failed pilot's athlete/novel-view quality.
- Evaluate and export the whole sequence; check the first, contact, release,
  landing and last frames, held-out views, temporal artifacts and paused-camera
  navigation. Preserve all current models, frames and viewer outputs as baselines.

This records the required scope for the next training. The historical one-second
profile remains unchanged for reproducibility; no capture, notebook execution or
training is started by this documentation update.
