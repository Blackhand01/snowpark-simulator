"""Bake the approved 4DGS pilot into 31 standard Gaussian PLY frames, without training."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from colab_4dgs import configuration
from snowpark_simulator.pilot4d import BACKEND_COMMIT, sha, write_json


def unique_timestamps(records, count=31):
    """Return one record index per sample; repeated camera views are not new frames."""
    selected = {}
    for index, record in enumerate(records):
        sample, stamp = record["sample_index"], float(record["time"])
        if not isinstance(sample, int) or not 0 <= sample < count:
            raise ValueError("Unexpected sample index")
        if not math.isfinite(stamp) or not math.isclose(stamp, sample / (count - 1), abs_tol=1e-8):
            raise ValueError("Unexpected normalized timestamp")
        selected.setdefault(sample, index)
    if set(selected) != set(range(count)):
        raise ValueError("The complete set of unique timestamps is required")
    return [selected[sample] for sample in range(count)]


def export(backend, data, model_path, evidence_path, output):
    import numpy as np
    from PIL import Image
    from plyfile import PlyData
    import torch

    sys.path.insert(0, str(backend))
    from arguments import ModelParams, OptimizationParams, PipelineParams, ModelHiddenParams
    from gaussian_renderer import render
    from scene import Scene
    from scene.gaussian_model import GaussianModel

    revision = subprocess.check_output(
        ["git", "-C", str(backend), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != BACKEND_COMMIT:
        raise ValueError("Unexpected backend revision")
    evidence = json.loads(evidence_path.read_text())
    if evidence["mode"] != "dynamic":
        raise ValueError("Expected the evaluated dynamic checkpoint")
    model_dir = model_path / "point_cloud/iteration_4500"
    before = {name: sha(model_dir / name) for name in evidence["model_files_sha256"]}
    if before != evidence["model_files_sha256"]:
        raise ValueError("Checkpoint differs from the evaluated pilot")
    records = [
        r for r in json.loads((data / "records.json").read_text()) if r["group"].startswith("test_")
    ]
    indices = unique_timestamps(records)
    output.mkdir(parents=True, exist_ok=False)
    frames = output / "ply-sequence"
    frames.mkdir()
    checks = output / "render-parity"
    checks.mkdir()
    parser = argparse.ArgumentParser()
    lp, op, pp, hp = (
        ModelParams(parser),
        OptimizationParams(parser),
        PipelineParams(parser),
        ModelHiddenParams(parser),
    )
    args = parser.parse_args([])
    for values in configuration("dynamic", data / "evaluation", model_path).values():
        for key, value in values.items():
            setattr(args, key, value)
    torch.set_num_threads(4)
    model = GaussianModel(args.sh_degree, hp.extract(args))
    scene = Scene(lp.extract(args), model, load_iteration=4500, shuffle=False)
    views = scene.getTestCameras()
    if len(views) != len(records):
        raise ValueError("Camera/metadata count mismatch")
    model._deformation.eval().requires_grad_(False)
    baked = GaussianModel(args.sh_degree, hp.extract(args))
    background = torch.ones(3, device="cuda")
    entries, parity = [], []
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        for sample, index in enumerate(indices):
            camera, record = views[index], records[index]
            if not math.isclose(float(camera.time), float(record["time"]), abs_tol=1e-7):
                raise ValueError("Backend timestamp does not match capture metadata")
            stamp = torch.full((len(model.get_xyz), 1), float(camera.time), device="cuda")
            xyz, scale, rotation, opacity, features = model._deformation(
                model.get_xyz,
                model._scaling,
                model._rotation,
                model._opacity,
                model.get_features,
                stamp,
            )
            for attribute, values in (
                ("_xyz", xyz),
                ("_scaling", scale),
                ("_rotation", rotation),
                ("_opacity", opacity),
                ("_features_dc", features[:, :1]),
                ("_features_rest", features[:, 1:]),
            ):
                if not torch.isfinite(values).all():
                    raise ValueError("Nonfinite exported Gaussian attributes")
                setattr(baked, attribute, torch.nn.Parameter(values.detach(), requires_grad=False))
            path = frames / f"snowpark_{sample:04d}.ply"
            # Upstream writer preserves log scales, opacity logits, WXYZ rotations and SH order.
            baked.save_ply(str(path))
            parsed = PlyData.read(path)["vertex"]
            if len(parsed) != len(model.get_xyz) or len(parsed.properties) != 62:
                raise ValueError("Incomplete standard degree-3 Gaussian PLY")
            entries.append(
                dict(
                    file=str(path.relative_to(output)),
                    sample_index=sample,
                    normalized_time=float(camera.time),
                    source_time_s=record["source_time_s"],
                    source_frame=record["source_frame"],
                    gaussians=len(parsed),
                    bytes=path.stat().st_size,
                    sha256=sha(path),
                )
            )
            if sample in (0, 15, 30):
                baked.load_ply(str(path))
                for camera_index in (3, 14):
                    view_index = next(
                        i
                        for i, r in enumerate(records)
                        if r["sample_index"] == sample and r["camera_index"] == camera_index
                    )
                    view = views[view_index]
                    native = render(view, model, pp.extract(args), background, stage="fine")[
                        "render"
                    ]
                    reloaded = render(view, baked, pp.extract(args), background, stage="coarse")[
                        "render"
                    ]
                    delta = (native - reloaded).abs()
                    maximum, mean = float(delta.max()), float(delta.mean())
                    if maximum > 1e-6:
                        raise ValueError(f"Export rendering mismatch: {maximum}")
                    for label, image in (("native", native), ("ply", reloaded)):
                        pixels = np.rint(
                            image.clamp(0, 1).permute(1, 2, 0).cpu().numpy() * 255
                        ).astype(np.uint8)
                        Image.fromarray(pixels).save(
                            checks / f"camera_{camera_index:03d}_sample_{sample:03d}-{label}.png"
                        )
                    parity.append(
                        dict(
                            camera_index=camera_index,
                            sample_index=sample,
                            maximum_absolute_pixel_error=maximum,
                            mean_absolute_pixel_error=mean,
                        )
                    )
            print("EXPORTED", sample, float(camera.time), len(parsed), flush=True)
    after = {name: sha(model_dir / name) for name in before}
    if before != after or model.optimizer is not None:
        raise ValueError("Source checkpoint changed or an optimizer was created")
    if len({entry["sha256"] for entry in entries}) != 31:
        raise ValueError("The dynamic sequence contains identical frames")
    write_json(
        output / "manifest.json",
        dict(
            status="EXPORTED_AND_RENDER_EQUIVALENT_NO_TRAINING",
            backend_revision=revision,
            source_model_files_sha256=before,
            source_checkpoint_preserved=before == after,
            source_config_sha256=sha(model_path / "pilot-config.py"),
            script_sha256=sha(Path(__file__)),
            frames=entries,
            frame_count=31,
            playback_fps=30,
            source_time_span_s=[0.9, 1.9],
            coordinates="Native normalized model coordinates; unchanged",
            normalization=json.loads((data / "preparation.json").read_text()),
            gaussian_attributes="Degree-3 SH, log scale, opacity logit, WXYZ quaternion; no pruning or compression",
            render_parity=parity,
            export_seconds=time.monotonic() - started,
            peak_allocated_cuda_bytes=torch.cuda.max_memory_allocated(),
            optimizer_created=False,
            backwards_executed=0,
            training_steps=0,
            quality="Unchanged negative pilot quality; conversion does not repair the reconstruction",
        ),
    )
    print("EXPORT_PASS", (output / "manifest.json").read_text(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("backend", "data", "model", "evidence", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    export(
        args.backend.resolve(),
        args.data.resolve(),
        args.model.resolve(),
        args.evidence.resolve(),
        args.output.resolve(),
    )
