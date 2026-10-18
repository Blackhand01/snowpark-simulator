"""Evaluate a frozen pilot checkpoint at denser times; never fit or interpolate PLYs.

Only PyTorch, NumPy and plyfile are required. The pinned upstream deformation
network runs on CPU, without importing the CUDA renderer or training modules.
Original timestamps retain their byte-identical PLYs after numerical checks.
"""

import argparse
import ast
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from snowpark_simulator.pilot4d import BACKEND_COMMIT, sha, write_json


def time_grid(fps, original_fps=30, start=0.9, end=1.9):
    """Include both endpoints and every original time, without extrapolation."""
    if type(fps) is not int or fps < original_fps or fps % original_fps:
        raise ValueError("Output FPS must be an integer multiple of the original FPS")
    intervals = (end - start) * fps
    if not math.isclose(intervals, round(intervals), abs_tol=1e-9):
        raise ValueError("Clip duration must contain a whole number of intervals")
    return [
        dict(sample_index=i, normalized_time=i / round(intervals), source_time_s=start + i / fps)
        for i in range(round(intervals) + 1)
    ]


def model_options(config_path):
    """Read the existing literal config without executing arbitrary Python."""
    for node in ast.parse(config_path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ModelHiddenParams"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError("Missing literal ModelHiddenParams")


def export(backend, model, config, reference, output, fps):
    import numpy as np
    from plyfile import PlyData
    import torch

    baseline = json.loads((reference / "manifest.json").read_text())
    if baseline["backend_revision"] != BACKEND_COMMIT or baseline["frame_count"] != 31:
        raise ValueError("Expected the verified 31-frame pilot export")
    if sha(config) != baseline["source_config_sha256"]:
        raise ValueError("Config differs from the evaluated checkpoint")
    before = {name: sha(model / name) for name in baseline["source_model_files_sha256"]}
    if before != baseline["source_model_files_sha256"]:
        raise ValueError("Checkpoint differs from the evaluated model")
    sources = json.loads((backend / "sources.json").read_text())
    for source in sources:
        if BACKEND_COMMIT not in source["url"] or sha(backend / source["path"]) != source["sha256"]:
            raise ValueError("Unverified upstream inference source")
    original_paths = []
    for entry in baseline["frames"]:
        path = reference / entry["file"]
        if sha(path) != entry["sha256"]:
            raise ValueError("Original export changed")
        original_paths.append(path)
    rows = time_grid(
        fps, start=baseline["source_time_span_s"][0], end=baseline["source_time_span_s"][1]
    )
    stride = fps // baseline["playback_fps"]
    output.mkdir(parents=True, exist_ok=False)
    frames = output / "ply-sequence"
    frames.mkdir()
    sys.path.insert(0, str(backend))
    from arguments import ModelHiddenParams

    # This unused Tk constant is unrelated to inference and absent on some hosts.
    # Execute the otherwise unchanged pinned module, recording this import-only adaptation.
    source_path = backend / "scene/deformation.py"
    tree = ast.parse(source_path.read_text(), filename=str(source_path))
    unused_imports = []
    for node in list(tree.body):
        if isinstance(node, ast.ImportFrom) and node.module == "tkinter":
            unused_imports.append(ast.unparse(node))
            tree.body.remove(node)
    module_spec = importlib.util.spec_from_file_location("scene.deformation", source_path)
    module = importlib.util.module_from_spec(module_spec)
    exec(compile(tree, str(source_path), "exec"), module.__dict__)
    torch.set_num_threads(2)
    torch.set_grad_enabled(False)
    parser = argparse.ArgumentParser()
    hidden = ModelHiddenParams(parser)
    args = parser.parse_args([])
    for key, value in model_options(config).items():
        setattr(args, key, value)
    network = module.deform_network(hidden.extract(args)).cpu()
    network.load_state_dict(
        torch.load(model / "deformation.pth", map_location="cpu", weights_only=True), strict=True
    )
    network.eval().requires_grad_(False)
    canonical = PlyData.read(model / "point_cloud.ply")
    vertices = canonical["vertex"].data

    def tensor(names):
        return torch.from_numpy(
            np.stack([vertices[name] for name in names], axis=1).astype(np.float32)
        )

    xyz = tensor(["x", "y", "z"])
    scales = tensor([f"scale_{i}" for i in range(3)])
    rotations = tensor([f"rot_{i}" for i in range(4)])
    opacity = tensor(["opacity"])
    dc = tensor([f"f_dc_{i}" for i in range(3)]).reshape(-1, 1, 3)
    rest = tensor([f"f_rest_{i}" for i in range(45)]).reshape(-1, 3, 15).transpose(1, 2)
    features = torch.cat([dc, rest], dim=1)
    parity = []
    started = time.monotonic()
    with torch.inference_mode():
        for row in rows:
            index = row["sample_index"]
            stamp = torch.full((len(vertices), 1), row["normalized_time"], dtype=torch.float32)
            values = network(xyz, scales, rotations, opacity, features, stamp)
            if not all(torch.isfinite(value).all() for value in values):
                raise ValueError("Nonfinite Gaussian attributes")
            baked = vertices.copy()
            groups = [
                (["x", "y", "z"], values[0]),
                ([f"scale_{i}" for i in range(3)], values[1]),
                ([f"rot_{i}" for i in range(4)], values[2]),
                (["opacity"], values[3]),
                ([f"f_dc_{i}" for i in range(3)], values[4][:, :1, :].reshape(-1, 3)),
                (
                    [f"f_rest_{i}" for i in range(45)],
                    values[4][:, 1:, :].transpose(1, 2).reshape(-1, 45),
                ),
            ]
            for names, value in groups:
                array = value.cpu().numpy()
                for column, name in enumerate(names):
                    baked[name] = array[:, column]
            path = frames / f"snowpark_{index:04d}.ply"
            if index % stride == 0:
                old_index = index // stride
                previous = PlyData.read(original_paths[old_index])["vertex"].data
                errors = {}
                for name in vertices.dtype.names:
                    if not np.allclose(baked[name], previous[name], atol=1e-5, rtol=1e-5):
                        raise ValueError(f"CPU/CUDA attribute mismatch: frame {index}, {name}")
                    errors[name] = float(np.max(np.abs(baked[name] - previous[name])))
                parity.append(
                    dict(
                        original_index=old_index,
                        new_index=index,
                        maximum_attribute_error=max(errors.values()),
                        errors=errors,
                    )
                )
                shutil.copyfile(original_paths[old_index], path)
                origin = "byte_identical_original_after_cpu_checkpoint_parity"
            else:
                from plyfile import PlyElement

                PlyData([PlyElement.describe(baked, "vertex")], byte_order="<").write(path)
                origin = "frozen_checkpoint_cpu_inference"
            row.update(
                file=str(path.relative_to(output)),
                gaussians=len(vertices),
                bytes=path.stat().st_size,
                sha256=sha(path),
                origin=origin,
                source_frame=109 + index,
            )
            print("EXPORTED", index, row["source_time_s"], origin, flush=True)
    after = {name: sha(model / name) for name in before}
    if before != after or any(parameter.requires_grad for parameter in network.parameters()):
        raise ValueError("Model preservation or inference-only check failed")
    if len({row["sha256"] for row in rows}) != len(rows):
        raise ValueError("Repeated output frames")
    write_json(
        output / "manifest.json",
        dict(
            status="EXPORTED_FROZEN_CHECKPOINT_WITH_ORIGINAL_ATTRIBUTE_PARITY",
            backend_revision=BACKEND_COMMIT,
            source_model_files_sha256=before,
            source_config_sha256=sha(config),
            source_reference_manifest_sha256=sha(reference / "manifest.json"),
            source_checkpoint_preserved=before == after,
            script_sha256=sha(Path(__file__)),
            frame_count=len(rows),
            playback_fps=fps,
            source_time_span_s=baseline["source_time_span_s"],
            timestamp_span_s=rows[-1]["source_time_s"] - rows[0]["source_time_s"],
            frames=rows,
            normalization=baseline["normalization"],
            original_frame_attribute_parity=parity,
            original_frames_retained_byte_identically=len(parity),
            attribute_parity_tolerance=dict(atol=1e-5, rtol=1e-5),
            render_parity="Not executed for CPU inference; Gaussian attributes checked against all 31 verified CUDA exports",
            unused_imports_removed=unused_imports,
            torch_version=str(torch.__version__),
            device="cpu",
            export_seconds=time.monotonic() - started,
            training_steps=0,
            backwards_executed=0,
            optimizer_created=False,
            pruning=False,
            sh_degree=3,
            quality="Unchanged failed pilot quality; intermediate states are model estimates, not new observations",
        ),
    )
    print("EXPORT_PASS", len(rows), "frames; zero training steps", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("backend", "model", "config", "reference", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--fps", type=int, default=120)
    args = parser.parse_args()
    export(
        args.backend.resolve(),
        args.model.resolve(),
        args.config.resolve(),
        args.reference.resolve(),
        args.output.resolve(),
        args.fps,
    )
