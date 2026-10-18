# A bounded 4D Gaussian Splatting pilot

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
Capture preserves the full animation and never rebuilds terrain, rail or clothing.

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
