"""Bounded HUST 4DGaussians adapter and runner, executed inside Colab.

No account API, billing, SSH, keep-alive or credential handling. The notebook
owns environment installation; this runner only uses its selected interpreter.
"""

import argparse
import difflib
import inspect
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from snowpark_simulator.pilot4d import BACKEND_COMMIT, sha, write_json


def nearest_three_squared(points, chunk_size=1024):
    """Mean squared distance to three other points, with bounded working memory.

    A native PyTorch implementation avoids the legacy simple-knn component,
    whose pinned tree does not contain its referenced LICENSE.md file.
    """
    import torch

    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 4:
        raise ValueError("Expected at least four 3D points")
    output = []
    for start in range(0, len(points), chunk_size):
        end = min(start + chunk_size, len(points))
        distance = torch.cdist(
            points[start:end], points, compute_mode="donot_use_mm_for_euclid_dist"
        ).square_()
        local = torch.arange(end - start, device=points.device)
        distance[local, local + start] = float("inf")
        output.append(distance.topk(3, largest=False).values.mean(dim=1))
    return torch.cat(output)


def replace_exact(text, original, replacement, count):
    if text.count(original) != count:
        raise ValueError(f"Unexpected backend source: {original[:60]!r}")
    return text.replace(original, replacement)


def initial_stamp_cameras(cameras):
    """Keep every view at time zero without assuming a dataset wrapper or stride."""
    selected = [camera for camera in cameras if abs(float(camera.time)) <= 1e-8]
    if not selected:
        raise ValueError("Zero-stamp initialization requires training cameras at time zero")
    return selected


def adapt(backend, output):
    revision = subprocess.check_output(
        ["git", "-C", str(backend), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != BACKEND_COMMIT:
        raise ValueError("Backend revision does not match the audit")
    output.mkdir(parents=True, exist_ok=False)
    changes = {}
    path = backend / "scene/dataset_readers.py"
    original = path.read_text()
    text = replace_exact(
        original, "image = PILtoTorch(image,(800,800))", "image = PILtoTorch(image,image.size)", 2
    )
    text = replace_exact(
        text,
        "fovy = focal2fov(fov2focal(fovx, image.shape[1]), image.shape[2])",
        "fovy = focal2fov(fov2focal(fovx, image.shape[2]), image.shape[1])",
        2,
    )
    text = replace_exact(
        text,
        "width=image.shape[1], height=image.shape[2]",
        "width=image.shape[2], height=image.shape[1]",
        2,
    )
    old = 'matrix = np.linalg.inv(np.array(frame["transform_matrix"]))\n            R = -np.transpose(matrix[:3,:3])\n            R[:,0] = -R[:,0]\n            T = -matrix[:3, 3]'
    new = 'matrix = np.diag([1., -1., -1., 1.]) @ np.linalg.inv(np.array(frame["transform_matrix"]))\n            R = matrix[:3,:3].T\n            T = matrix[:3, 3]'
    text = replace_exact(text, old, new, 1)
    text = replace_exact(
        text,
        'video_cam_infos = generateCamerasFromTransforms(path, "transforms_train.json", extension, max_time)',
        "video_cam_infos = train_cam_infos[:1]  # Declared cameras only; no demo orbit.",
        1,
    )
    path.write_text(text)
    changes[str(path.relative_to(backend))] = (original, text)
    path = backend / "scene/gaussian_model.py"
    original = path.read_text()
    text = replace_exact(
        original,
        "from simple_knn._C import distCUDA2",
        "from pilot_knn import nearest_three_squared as distCUDA2",
        1,
    )
    path.write_text(text)
    changes[str(path.relative_to(backend))] = (original, text)
    # A small original helper, not copied from the unlicensed component.
    (backend / "pilot_knn.py").write_text(inspect.getsource(nearest_three_squared) + "\n")
    (backend / "pilot_camera_selection.py").write_text(
        inspect.getsource(initial_stamp_cameras) + "\n"
    )
    path = backend / "train.py"
    original = path.read_text()
    guard = """        if iteration % 50 == 0:
            pilot_record = dict(stage=stage, iteration=iteration,
                gaussians=int(gaussians.get_xyz.shape[0]),
                allocated_bytes=torch.cuda.memory_allocated(),
                reserved_bytes=torch.cuda.memory_reserved(),
                peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                wall_seconds=_pilot_time.monotonic() - _pilot_start)
            with open(os.path.join(scene.model_path, "pilot-progress.jsonl"), "a") as pilot_log:
                pilot_log.write(__import__("json").dumps(pilot_record) + "\\n")
            if pilot_record["gaussians"] > 200000 or pilot_record["peak_allocated_bytes"] > 12 * 1024**3:
                raise RuntimeError("PILOT_RESOURCE_LIMIT")
        iter_start.record()"""
    text = replace_exact(original, "        iter_start.record()", guard, 1)
    text = replace_exact(
        text,
        "        temp_list = get_stamp_list(viewpoint_stack,0)",
        "        from pilot_camera_selection import initial_stamp_cameras\n"
        "        temp_list = initial_stamp_cameras(viewpoint_stack)",
        1,
    )
    text = replace_exact(
        text, "    safe_state(args.quiet)", "    safe_state(args.quiet)\n    setup_seed(1729)", 1
    )
    text = "import time as _pilot_time\n_pilot_start = _pilot_time.monotonic()\n" + text
    path.write_text(text)
    changes[str(path.relative_to(backend))] = (original, text)
    diff = "".join(
        "".join(
            difflib.unified_diff(a.splitlines(True), b.splitlines(True), fromfile=name, tofile=name)
        )
        for name, (a, b) in changes.items()
    )
    (output / "backend.patch").write_text(diff)
    write_json(
        output / "adapter.json",
        dict(
            backend_revision=revision,
            changed_files=list(changes),
            helper_sha256=sha(backend / "pilot_knn.py"),
            initial_stamp_helper_sha256=sha(backend / "pilot_camera_selection.py"),
            simple_knn_used=False,
            scope="loader calibration, native size, declared cameras, native Torch initialization, time-zero camera selection, seed and resource records",
        ),
    )


def configuration(mode, source, output, coarse=500, fine=4500):
    static = mode == "static"
    return dict(
        ModelParams=dict(
            source_path=str(source),
            model_path=str(output),
            eval=True,
            render_process=False,
            sh_degree=3,
            white_background=True,
        ),
        OptimizationParams=dict(
            coarse_iterations=coarse,
            iterations=fine,
            batch_size=1,
            dataloader=False,
            zerostamp_init=True,
            position_lr_max_steps=fine,
            densify_until_iter=4000,
            add_point=False,
            pruning_interval=8000,
        ),
        ModelHiddenParams=dict(
            multires=[1, 2],
            defor_depth=0,
            net_width=64,
            bounds=1.6,
            no_dx=static,
            no_ds=static,
            no_dr=static,
            no_do=True,
            no_dshs=True,
        ),
    )


def write_configuration(path, config):
    with path.open("x") as stream:
        for name, values in config.items():
            stream.write(f"{name} = {values!r}\n")


def model_probe(backend, data, output):
    """Actual CUDA rasterization/backprop; final test records are never loaded."""
    import numpy as np
    import torch

    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(backend))
    from arguments import ModelParams, OptimizationParams, PipelineParams, ModelHiddenParams
    from gaussian_renderer import render
    from scene import Scene
    from scene.gaussian_model import GaussianModel

    torch.manual_seed(1729)
    np.random.seed(1729)
    parser = argparse.ArgumentParser()
    lp, op, pp, hp = (
        ModelParams(parser),
        OptimizationParams(parser),
        PipelineParams(parser),
        ModelHiddenParams(parser),
    )
    args = parser.parse_args([])
    for values in configuration("dynamic", data / "fit", output).values():
        for key, value in values.items():
            setattr(args, key, value)
    model = GaussianModel(args.sh_degree, hp.extract(args))
    torch.cuda.reset_peak_memory_stats()
    scene = Scene(lp.extract(args), model, shuffle=False)
    train = list(scene.getTrainCameras())
    validation = list(scene.getTestCameras())
    assert len(train) == 300 and len(validation) == 62
    # Compare the real loader's CUDA camera matrices to the neutral calibration.
    # Coordinates below use image edges; raster pixel-center indices are 0.5 less.
    records = json.loads((data / "records.json").read_text())
    training_records = [r for r in records if r["group"] == "train"]
    normalization = json.loads((data / "preparation.json").read_text())
    center = np.array(normalization["model_to_world_translation_m"])
    scale = normalization["model_to_world_scale_m"]
    probes = np.c_[np.random.default_rng(1729).uniform(-0.6, 0.6, (16, 3)), np.ones(16)]
    reprojection_error = 0.0
    for camera, record in zip(train, training_records):
        assert camera.image_width == 640 and camera.image_height == 480
        c2w = np.array(record["camera_to_world_blender"])
        c2w[:3, 3] = (c2w[:3, 3] - center) / scale
        expected = (np.diag([1, -1, -1, 1]) @ np.linalg.inv(c2w) @ probes.T)[:3]
        loaded = (camera.world_view_transform.cpu().numpy().T @ probes.T)[:3]
        k = np.array(record["K"])
        px_expected = k @ expected
        px_expected = px_expected[:2] / px_expected[2:3]
        fx = 320 / math.tan(camera.FoVx / 2)
        fy = 240 / math.tan(camera.FoVy / 2)
        px_loaded = np.array([[fx, 0, 320], [0, fy, 240], [0, 0, 1]]) @ loaded
        px_loaded = px_loaded[:2] / px_loaded[2:3]
        reprojection_error = max(
            reprojection_error, float(np.linalg.norm(px_expected - px_loaded, axis=0).max())
        )
    assert reprojection_error <= 0.5, ("LOADER_CALIBRATION_FAILED", reprojection_error)
    model.training_setup(op.extract(args))
    background = torch.ones(3, device="cuda")
    started = time.monotonic()
    losses = []
    deformation_gradient_l1 = None
    for step in range(100):
        cam = train[step % len(train)]
        predicted = render(cam, model, pp.extract(args), background, stage="fine")["render"]
        reference = cam.original_image[:3].to(predicted.device)
        loss = (predicted - reference).abs().mean()
        loss.backward()
        assert torch.isfinite(loss) and torch.isfinite(model._xyz.grad).all()
        if step == 0:
            gradients = [p.grad for p in model._deformation.parameters() if p.grad is not None]
            assert gradients and all(torch.isfinite(g).all() for g in gradients)
            deformation_gradient_l1 = sum(float(g.abs().sum().detach().cpu()) for g in gradients)
            assert deformation_gradient_l1 > 0, "NO_IMAGE_GRADIENT_IN_DEFORMATION_MODEL"
        model.optimizer.step()
        model.optimizer.zero_grad(set_to_none=True)
        losses.append(float(loss.detach().cpu()))
        if torch.cuda.max_memory_allocated() > 12 * 1024**3:
            raise RuntimeError("PILOT_MEMORY_LIMIT")
    torch.cuda.synchronize()
    write_json(
        output / "memory-smoke.json",
        dict(
            status="PASS_CUDA_RENDER_BACKPROP_100_STEPS",
            train_images=len(train),
            validation_images=len(validation),
            final_test_images_loaded=0,
            loader_max_reprojection_error_px=reprojection_error,
            seconds=time.monotonic() - started,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            first_loss=losses[0],
            last_loss=losses[-1],
            first_deformation_gradient_l1=deformation_gradient_l1,
            note="Diagnostic weights discarded; production models start from the shared random cloud",
        ),
    )


def fit(backend, data, output, mode):
    output.mkdir(parents=True, exist_ok=False)
    config = configuration(mode, data / "fit", output)
    write_configuration(output / "pilot-config.py", config)
    command = [
        sys.executable,
        str(backend / "train.py"),
        "--configs",
        str(output / "pilot-config.py"),
        "-s",
        str(data / "fit"),
        "-m",
        str(output),
        "--iterations",
        "4500",
        "--coarse_iterations",
        "500",
        "--save_iterations",
        "500",
        "4500",
        "--checkpoint_iterations",
        "500",
        "1000",
        "2000",
        "3000",
        "4000",
        "4500",
        "--test_iterations",
        "500",
        "4500",
        "--quiet",
    ]
    started = time.monotonic()
    with (output / "train.log").open("x") as log:
        try:
            result = subprocess.run(
                command,
                cwd=backend,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=1800,
                check=False,
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = "TIMEOUT"
    write_json(
        output / "execution.json",
        dict(command=command, seconds=time.monotonic() - started, exit_code=code, mode=mode),
    )
    if code != 0 or not (output / "point_cloud/iteration_4500/deformation.pth").is_file():
        raise RuntimeError(f"{mode} fit did not complete; inspect {output / 'train.log'}")
    print("FIT_COMPLETED_REQUIRES_EVALUATION", mode, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("adapt", "probe", "fit"))
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("static", "dynamic"), default="dynamic")
    args = parser.parse_args()
    if args.stage == "adapt":
        adapt(args.backend.resolve(), args.output.resolve())
    elif args.stage == "probe":
        model_probe(args.backend.resolve(), args.data.resolve(), args.output.resolve())
    else:
        fit(args.backend.resolve(), args.data.resolve(), args.output.resolve(), args.mode)
