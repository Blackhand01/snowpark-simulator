"""Independently decode the matrix and compare a fixed GS with changed targets."""

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import numpy as np
from PIL import Image
from evaluate_brush import metrics

p = argparse.ArgumentParser()
p.add_argument("run", type=Path)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = a.run.resolve()
assert out.is_relative_to(root / "outputs")
matrix = json.loads((out / "conditions.json").read_text())
dataset = root / matrix["dataset"]
baseline = root / matrix["baseline"]
data = json.loads((dataset / "dataset.json").read_text())
cameras = [
    f for f in json.loads((dataset / "cameras.json").read_text())["frames"] if f["split"] == "test"
]
checks = {}
rows = []
pixels = {}
meta = {}
baseline_evidence = json.loads((baseline / "artifact-verification.json").read_text())
checks["baseline_predictions_unchanged"] = all(
    hashlib.sha256(Path(v["prediction"]).read_bytes()).hexdigest() == v["prediction_sha256"]
    for v in baseline_evidence["views"]
)
execution = [json.loads(v) for v in (out / "execution.jsonl").read_text().splitlines()]
checks["all_conditions_exit0"] = len(execution) == len(matrix["conditions"]) and all(
    v["exit_code"] == 0 for v in execution
)
for profile in matrix["conditions"]:
    name = profile["name"]
    m = json.loads((out / name / "metadata.json").read_text())
    meta[name] = m
    checks[name + "_profile_and_pose"] = (
        m["profile"] == profile and m["center_pose_sha256"] == data["pose_sha256"]
    )
    checks[name + "_effective_exposure"] = (
        abs(
            m["effective_exposure_ev"]
            - (
                data["render_contract"]["exposure"]
                + profile["exposure_ev"]
                + math.log2(profile["gain"])
            )
        )
        < 1e-6
    )
    checks[name + "_particle_count"] = m["particle_count"] == profile["snow_count"]
    if profile["white_balance_kelvin"] is not None:
        checks[name + "_white_balance"] = (
            m["white_balance_enabled"]
            and abs(m["effective_white_balance_kelvin"] - profile["white_balance_kelvin"]) < 0.1
        )
    if profile["blur_exposure_s"]:
        checks[name + "_actual_blur_exposure"] = (
            abs(m["actual_blur_shutter_frames"] / m["fps"] - profile["blur_exposure_s"]) < 1e-9
        )
    for camera in cameras:
        cid = camera["camera_id"]
        path = out / name / "images" / (cid + ".png")
        record = next(v for v in m["images"] if v["camera_id"] == cid)
        with Image.open(path) as im:
            im.load()
            checks[name + "_" + cid + "_rgb_size"] = (
                im.mode == "RGB" and list(im.size) == camera["resolution"]
            )
            image = np.asarray(im).copy()
        checks[name + "_" + cid + "_file_hash"] = (
            hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        )
        pixels[name, cid] = image
        gt = np.asarray(Image.open(dataset / camera["file_path"]).convert("RGB"))
        pred = np.asarray(Image.open(baseline / "eval_5000" / (cid + ".png")).convert("RGB"))
        shift = metrics(gt, image)
        fixed = metrics(pred, image)
        rows.append(
            dict(
                condition=name,
                camera=cid,
                target_shift_psnr_db=shift["psnr_db"],
                target_shift_ssim=shift["ssim_skimage"],
                target_shift_mse=shift["mse_rgb_0_1"],
                fixed_gs_psnr_db=fixed["psnr_db"],
                fixed_gs_ssim=fixed["ssim_skimage"],
            )
        )
for camera in cameras:
    cid = camera["camera_id"]
    checks[cid + "_control_repeat_exact"] = np.array_equal(
        pixels["control", cid], pixels["control_repeat", cid]
    )
    checks[cid + "_control_equals_original_exact"] = np.array_equal(
        pixels["control", cid],
        np.asarray(Image.open(dataset / camera["file_path"]).convert("RGB")),
    )
    checks[cid + "_snow_repeat_exact"] = np.array_equal(
        pixels["snow_density", cid], pixels["snow_repeat", cid]
    )
checks["seeded_particle_geometry_repeats"] = (
    meta["snow_density"]["particles_sha256"]
    == meta["snow_repeat"]["particles_sha256"]
    == meta["snow_intensity"]["particles_sha256"]
)
checks["brightness_changes_pixels_at_fixed_density"] = any(
    not np.array_equal(
        pixels["snow_density", c["camera_id"]], pixels["snow_intensity", c["camera_id"]]
    )
    for c in cameras
)
for profile in matrix["conditions"]:
    if profile["name"] not in ["control", "control_repeat"]:
        checks[profile["name"] + "_changes_render"] = any(
            v["target_shift_mse"] > 0 for v in rows if v["condition"] == profile["name"]
        )
inputs = json.loads((out / "input-hashes.json").read_text())
checks["source_blends_and_gs_model_unchanged"] = all(
    hashlib.sha256((root / f).read_bytes()).hexdigest() == sha for f, sha in inputs.items()
)
result = dict(
    status="PASS" if all(checks.values()) else "FAIL",
    checks=checks,
    rows=rows,
    metric_definition="Same documented RGB PSNR/SSIM as P8. Target shift compares Blender condition vs original Blender; fixed_gs compares same baseline prediction against changed target. No variant training.",
    scope="Evaluation subset only; model fixed, no evidence of real-camera robustness or retraining robustness",
)
target = out / "host-verification.json"
assert not target.exists()
target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
assert result["status"] == "PASS", {k: v for k, v in checks.items() if not v}
with (out / "metrics.csv").open("x") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
os.environ["MPLCONFIGDIR"] = str(root / "outputs/sequence-auto-20261017T155416-617400Z/mpl-cache")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

for camera in cameras:
    cid = camera["camera_id"]
    fig, axes = plt.subplots(5, 4, figsize=(13, 13))
    for ax in axes.flat:
        ax.axis("off")
    for ax, profile in zip(axes.flat, matrix["conditions"]):
        name = profile["name"]
        row = next(v for v in rows if v["condition"] == name and v["camera"] == cid)
        ax.imshow(pixels[name, cid])
        ax.set_title(
            f"{name}\nfixed GS {row['fixed_gs_psnr_db']:.2f} dB / {row['fixed_gs_ssim']:.3f}",
            fontsize=9,
        )
    fig.suptitle(
        cid + " — controlled Blender targets; scores against fixed original GS",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(out / (cid + "-conditions.png"), dpi=130)
    plt.close(fig)
print("PASS", len(checks), "host checks;", len(rows), "evaluations")
