"""Verify the dynamic capture and package calibrated data for Colab.

Ground-truth masks are evaluation-only. Initialization uses only training
camera axes; no mesh, depth, rig or earlier reconstruction enters the fit.
"""

import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import zipfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from snowpark_simulator.pilot4d import (
    SOURCE_SHA256,
    sha,
    validate_plan,
    validate_records,
    write_json,
)


def training_normalization(records):
    origins, projectors = [], []
    for item in records:
        if item["group"] != "train":
            continue
        matrix = np.array(item["camera_to_world_blender"], dtype=np.float64)
        direction = -matrix[:3, 2]
        direction /= np.linalg.norm(direction)
        origins.append(matrix[:3, 3])
        projectors.append(np.eye(3) - np.outer(direction, direction))
    if len(origins) < 3:
        raise ValueError("At least three training-camera rays are required")
    center = np.linalg.solve(sum(projectors), sum(p @ o for p, o in zip(projectors, origins)))
    scale = float(np.median(np.linalg.norm(np.array(origins) - center, axis=1)) * 0.35)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Degenerate training-camera scale")
    return center, scale


def normalized_matrix(item, center, scale):
    matrix = np.array(item["camera_to_world_blender"], dtype=np.float64)
    matrix[:3, 3] = (matrix[:3, 3] - center) / scale
    return matrix.tolist()


def verify_capture(source):
    completed = json.loads((source / "capture-result.json").read_text())
    if (
        completed["status"] != "CAPTURED_REQUIRES_HOST_VERIFICATION"
        or completed["source_sha256"] != SOURCE_SHA256
    ):
        raise ValueError("Expected a completed capture of the approved animated scene")
    validate_plan(json.loads((source / "plan.json").read_text()))
    records = [json.loads(line) for line in (source / "records.jsonl").read_text().splitlines()]
    counts = validate_records(records)
    if completed["counts"] != counts:
        raise ValueError("Capture completion counts disagree with the image records")
    intrinsic = np.array(records[0]["K"])
    images_by_camera = {}
    for item in records:
        if not np.allclose(item["K"], intrinsic, rtol=0, atol=0.0001):
            raise ValueError("This pilot requires shared, fixed camera intrinsics")
        images_by_camera.setdefault(item["camera_index"], set()).add(item["image_sha256"])
        for kind in ("image", "mask"):
            path = (source / item[kind]).resolve()
            if not path.is_relative_to(source.resolve()):
                raise ValueError("Image path escapes the capture")
            if sha(path) != item[kind + "_sha256"]:
                raise ValueError(f"Image hash mismatch: {path.name}")
            with Image.open(path) as image:
                if image.size != (640, 480):
                    raise ValueError("Image resolution changed")
                if kind == "mask" and not np.any(np.array(image) > 0):
                    raise ValueError("No visible athlete pixels in mask")
        if item["reprojection_max_error_px"] > 0.001:
            raise ValueError("Capture reprojection failed")
    if any(len(hashes) != 31 for hashes in images_by_camera.values()):
        raise ValueError("Expected 31 distinct rendered images per fixed camera")
    poses = {}
    cameras = {}
    for item in records:
        poses.setdefault(item["sample_index"], set()).add(item["pose_sha256"])
        cameras.setdefault(item["camera_index"], set()).add(
            json.dumps(item["camera_to_world_blender"])
        )
    if (
        any(len(v) != 1 for v in poses.values())
        or len({next(iter(v)) for v in poses.values()}) != 31
    ):
        raise ValueError("Expected 31 distinct poses, each fixed across simultaneous views")
    if any(len(v) != 1 for v in cameras.values()):
        raise ValueError("Pilot cameras must be fixed across time")
    return records, counts


def prepare(source, output):
    records, counts = verify_capture(source)
    output.mkdir(parents=True, exist_ok=False)
    center, scale = training_normalization(records)
    for subdir in ("images", "masks", "fit", "evaluation"):
        (output / subdir).mkdir()
    for item in records:
        for kind in ("image", "mask"):
            destination = (
                output / ("images" if kind == "image" else "masks") / Path(item[kind]).name
            )
            shutil.copy2(source / item[kind], destination)
    first = records[0]
    header = dict(
        camera_angle_x=2 * math.atan(640 / (2 * first["K"][0][0])),
        w=640,
        h=480,
    )
    converted = []
    for item in records:
        converted.append(
            dict(
                file_path="../images/" + Path(item["image"]).stem,
                transform_matrix=normalized_matrix(item, center, scale),
                time=item["time"],
                camera_id=item["camera_index"],
                sample_id=item["sample_index"],
                group=item["group"],
            )
        )
    training = [f for f in converted if f["group"] == "train"]
    validation = [f for f in converted if f["group"] == "validation"]
    final = [f for f in converted if f["group"].startswith("test_")]
    for folder, held_out in (("fit", validation), ("evaluation", final)):
        write_json(output / folder / "transforms_train.json", dict(**header, frames=training))
        write_json(output / folder / "transforms_test.json", dict(**header, frames=held_out))
    rng = np.random.default_rng(1729)
    xyz = rng.uniform(-1, 1, (10000, 3))
    colors = rng.integers(40, 216, (10000, 3))
    with (output / "fit/fused.ply").open("x") as stream:
        stream.write("ply\nformat ascii 1.0\nelement vertex 10000\n")
        stream.write("property float x\nproperty float y\nproperty float z\n")
        stream.write("property float nx\nproperty float ny\nproperty float nz\n")
        stream.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for point, color in zip(xyz, colors):
            stream.write(
                " ".join([*(f"{v:.8f}" for v in point), "0", "0", "0", *(str(v) for v in color)])
                + "\n"
            )
    shutil.copy2(output / "fit/fused.ply", output / "evaluation/fused.ply")
    write_json(output / "records.json", records)
    write_json(
        output / "preparation.json",
        dict(
            status="VERIFIED_DYNAMIC_CAPTURE",
            counts=counts,
            model_to_world_translation_m=center.tolist(),
            model_to_world_scale_m=scale,
            initialization="10000 shared random points; training-camera axes only",
            init_sha256=sha(output / "fit/fused.ply"),
            ground_truth_initialization=False,
            final_test_visible_to_fit_loader=False,
            source_capture=str(source.relative_to(ROOT)),
        ),
    )
    files = sorted(p for p in output.rglob("*") if p.is_file())
    write_json(output / "file-hashes.json", {str(p.relative_to(output)): sha(p) for p in files})
    print("VERIFIED_DATASET", json.dumps(counts), flush=True)


def bundle(data, destination):
    """Whitelist only synthetic data and the pilot's code; no private references."""
    code = [
        ROOT / "snowpark_simulator/__init__.py",
        ROOT / "snowpark_simulator/pilot4d.py",
        ROOT / "tools/colab_4dgs.py",
        ROOT / "tools/evaluate_4dgs.py",
    ]
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in code:
            archive.write(path, "code/" + str(path.relative_to(ROOT)))
        for path in sorted(data.rglob("*")):
            if path.is_file():
                archive.write(path, "data/" + str(path.relative_to(data)))
    print("COLAB_BUNDLE", str(destination), sha(destination), destination.stat().st_size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    for path in (args.source, args.output, args.bundle):
        if path and not path.resolve().is_relative_to(ROOT / "outputs"):
            parser.error("Pilot inputs and outputs must stay inside outputs/")
    prepare(args.source.resolve(), args.output.resolve())
    if args.bundle:
        bundle(args.output.resolve(), args.bundle.resolve())
