"""Stream held-out views from one time-conditioned model; score the athlete ROI."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from colab_4dgs import configuration
from snowpark_simulator.pilot4d import sha, write_json


def psnr(reference, prediction):
    return -10 * math.log10(max(float(np.mean((reference - prediction) ** 2)), 1e-12))


def frame_metrics(reference, prediction, roi, mask):
    x0, y0, x1, y1 = roi
    ref, pred = reference[y0:y1, x0:x1], prediction[y0:y1, x0:x1]
    visible = mask > 127
    if not visible.any() or min(ref.shape[:2]) < 11:
        raise ValueError("Invalid visible-athlete region")
    return dict(
        full_psnr_db=psnr(reference, prediction),
        athlete_roi_psnr_db=psnr(ref, pred),
        athlete_roi_ssim=float(
            structural_similarity(
                ref,
                pred,
                data_range=1,
                channel_axis=2,
                gaussian_weights=True,
                sigma=1.5,
                use_sample_covariance=False,
            )
        ),
        visible_athlete_mae=float(np.abs(reference - prediction)[visible].mean()),
        background_psnr_db=psnr(reference[~visible], prediction[~visible]),
    )


def evaluate(backend, data, model_path, output, mode):
    import imageio.v2 as imageio
    import torch

    sys.path.insert(0, str(backend))
    from arguments import ModelParams, OptimizationParams, PipelineParams, ModelHiddenParams
    from gaussian_renderer import render
    from scene import Scene
    from scene.gaussian_model import GaussianModel

    output.mkdir(parents=True, exist_ok=False)
    (output / "predictions").mkdir()
    parser = argparse.ArgumentParser()
    lp, op, pp, hp = (
        ModelParams(parser),
        OptimizationParams(parser),
        PipelineParams(parser),
        ModelHiddenParams(parser),
    )
    args = parser.parse_args([])
    for values in configuration(mode, data / "evaluation", model_path).values():
        for key, value in values.items():
            setattr(args, key, value)
    records = [
        r for r in json.loads((data / "records.json").read_text()) if r["group"].startswith("test_")
    ]
    model = GaussianModel(args.sh_degree, hp.extract(args))
    scene = Scene(lp.extract(args), model, load_iteration=4500, shuffle=False)
    views = scene.getTestCameras()
    assert len(views) == len(records) == 134
    background = torch.ones(3, device="cuda")
    metrics = []
    prediction_hashes = {}
    writers = {
        i: imageio.get_writer(output / f"camera_{i:03d}-comparison.mp4", fps=30, macro_block_size=1)
        for i in (3, 14)
    }
    with torch.no_grad():
        try:
            for i, record in enumerate(records):
                camera = views[i]
                image = render(camera, model, pp.extract(args), background, stage="fine")["render"]
                pixels = np.rint(image.clamp(0, 1).permute(1, 2, 0).cpu().numpy() * 255).astype(
                    np.uint8
                )
                name = Path(record["image"]).name
                prediction_hashes.setdefault(record["camera_index"], set()).add(
                    hashlib.sha256(pixels.tobytes()).hexdigest()
                )
                Image.fromarray(pixels).save(output / "predictions" / name)
                reference8 = np.array(Image.open(data / record["image"]).convert("RGB"))
                mask = np.array(Image.open(data / record["mask"]).convert("L"))
                reference, prediction = (
                    reference8.astype(np.float32) / 255,
                    pixels.astype(np.float32) / 255,
                )
                values = frame_metrics(reference, prediction, record["athlete_roi"], mask)
                metrics.append(
                    dict(
                        image=name,
                        camera_index=record["camera_index"],
                        sample_index=record["sample_index"],
                        group=record["group"],
                        **values,
                    )
                )
                if record["camera_index"] in writers:
                    difference = np.clip(np.abs(reference - prediction) * 3 * 255, 0, 255).astype(
                        np.uint8
                    )
                    panel = np.concatenate((reference8, pixels, difference), axis=1)
                    writers[record["camera_index"]].append_data(panel)
                    if record["sample_index"] in (0, 10, 20, 30):
                        Image.fromarray(panel).save(
                            output / name.replace(".png", "-comparison.png")
                        )
                del image, camera
        finally:
            for writer in writers.values():
                writer.close()
    grouped = {}
    if mode == "static" and any(len(hashes) != 1 for hashes in prediction_hashes.values()):
        raise RuntimeError("INVALID_STATIC_CONTROL: fixed-camera predictions vary with time")
    for group in ("test_spatial", "test_temporal"):
        rows = [r for r in metrics if r["group"] == group]
        grouped[group] = {
            key: float(np.mean([r[key] for r in rows]))
            for key in rows[0]
            if key not in ("image", "camera_index", "sample_index", "group")
        }
        grouped[group]["fraction_roi_psnr_above_20db"] = sum(
            r["athlete_roi_psnr_db"] >= 20 for r in rows
        ) / len(rows)
    write_json(
        output / "metrics.json",
        dict(
            status="EVALUATED_NOT_VISUALLY_ACCEPTED",
            mode=mode,
            model_files_sha256={
                p.name: sha(p)
                for p in sorted((model_path / "point_cloud/iteration_4500").iterdir())
                if p.is_file()
            },
            unique_predictions_by_camera={k: len(v) for k, v in prediction_hashes.items()},
            groups=grouped,
            frames=metrics,
            limits="Image reconstruction only; no metric geometry, logo or physical validity claim",
        ),
    )
    print("EVALUATED", mode, json.dumps(grouped), flush=True)


def compare(data, static, dynamic, output):
    control = json.loads((static / "metrics.json").read_text())
    candidate = json.loads((dynamic / "metrics.json").read_text())
    records = json.loads((data / "records.json").read_text())
    checks = {}
    for group in ("test_spatial", "test_temporal"):
        a, b = control["groups"][group], candidate["groups"][group]
        checks[group + "_roi_psnr"] = b["athlete_roi_psnr_db"] >= 23
        checks[group + "_roi_ssim"] = b["athlete_roi_ssim"] >= 0.85
        checks[group + "_90pct_above_20db"] = b["fraction_roi_psnr_above_20db"] >= 0.9
        checks[group + "_gain_3db"] = b["athlete_roi_psnr_db"] - a["athlete_roi_psnr_db"] >= 3
        checks[group + "_stable_background"] = (
            b["background_psnr_db"] >= a["background_psnr_db"] - 1
        )
    temporal = {}
    for label, folder in (("static", static), ("dynamic", dynamic)):
        errors = []
        for camera in (3, 14):
            sequence = sorted(
                (r for r in records if r["camera_index"] == camera), key=lambda r: r["sample_index"]
            )
            previous = None
            for item in sequence:
                pred = (
                    np.array(
                        Image.open(folder / "predictions" / Path(item["image"]).name),
                        dtype=np.float32,
                    )
                    / 255
                )
                gt = np.array(Image.open(data / item["image"]), dtype=np.float32) / 255
                residual = pred - gt
                if previous is not None:
                    old, roi = previous
                    box = item["athlete_roi"]
                    x0, y0, x1, y1 = (
                        min(roi[0], box[0]),
                        min(roi[1], box[1]),
                        max(roi[2], box[2]),
                        max(roi[3], box[3]),
                    )
                    errors.append(float(np.abs(residual - old)[y0:y1, x0:x1].mean()))
                previous = residual, item["athlete_roi"]
        temporal[label] = float(np.mean(errors))
    checks["temporal_residual_reduction_25pct"] = temporal["dynamic"] <= 0.75 * temporal["static"]
    write_json(
        output,
        dict(
            status="QUANTITATIVE_PASS_REQUIRES_VISUAL_REVIEW"
            if all(checks.values())
            else "QUANTITATIVE_FAIL",
            checks=checks,
            temporal_residual_mae=temporal,
            static_groups=control["groups"],
            dynamic_groups=candidate["groups"],
            visual_review="NOT_YET_PERFORMED",
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("evaluate", "compare"))
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--mode", choices=("static", "dynamic"))
    parser.add_argument("--static", type=Path)
    parser.add_argument("--dynamic", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "evaluate":
        evaluate(
            args.backend.resolve(),
            args.data.resolve(),
            args.model.resolve(),
            args.output.resolve(),
            args.mode,
        )
    else:
        compare(
            args.data.resolve(),
            args.static.resolve(),
            args.dynamic.resolve(),
            args.output.resolve(),
        )
