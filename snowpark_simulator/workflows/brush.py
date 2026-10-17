"""Run the pinned native Brush backend in a fresh, measured local run directory."""

import argparse
import datetime
import hashlib
import json
import os
import resource
import shutil
import time
from pathlib import Path

from snowpark_simulator.artifacts import ROOT, snapshot_runtime, within
from snowpark_simulator.execution import run_logged

BINARY = ROOT / ".tools/brush-v0.3.0/binary/brush-app-aarch64-apple-darwin/brush_app"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--resolution", type=int, required=True)
    parser.add_argument("--max-splats", type=int, default=100000)
    parser.add_argument("--sh-degree", type=int, default=3)
    parser.add_argument(
        "--purpose",
        choices=["backend-development", "baseline", "view-count-development"],
        default="baseline",
    )
    args = parser.parse_args(argv)
    source = within(args.dataset, ROOT / "outputs", directory=True)
    parent = within(args.parent, ROOT / "outputs", directory=True)
    if not (
        1 <= args.steps <= 30000
        and 64 <= args.resolution <= 640
        and (10000 <= args.max_splats <= 500000)
    ):
        raise ValueError("Steps, resolution or splat count outside the supported range")
    if not BINARY.is_file():
        raise FileNotFoundError(f"Optional Brush backend not installed: {BINARY}")
    output = parent / datetime.datetime.now(datetime.timezone.utc).strftime(
        "brush-%Y%m%dT%H%M%S-%fZ"
    )
    output.mkdir(exist_ok=False)
    shutil.copy2(Path(__file__), output / "run_brush.py")
    snapshot_runtime(output)
    command = [
        str(BINARY),
        str(source),
        "--total-steps",
        str(args.steps),
        "--max-resolution",
        str(args.resolution),
        "--max-splats",
        str(args.max_splats),
        "--sh-degree",
        str(args.sh_degree),
        "--seed",
        "1729",
        "--refine-every",
        "100",
        "--growth-stop-iter",
        str(round(args.steps * 0.7)),
        "--eval-every",
        str(args.steps),
        "--export-every",
        str(args.steps),
        "--eval-save-to-disk",
        "--export-path",
        str(output),
        "--export-name",
        "model_{iter}.ply",
    ]
    env = os.environ.copy()
    env["RUST_LOG"] = "info"
    env["XDG_CACHE_HOME"] = str(output / "cache")
    env["TMPDIR"] = str(output / "tmp")
    (output / "tmp").mkdir()
    train = json.loads((source / "transforms_train.json").read_text())
    test = json.loads((source / "transforms_test.json").read_text())
    config = dict(
        command=command,
        backend="Brush v0.3.0 native Apple Silicon WebGPU/Metal candidate; actual backend checked from log",
        binary_sha256=hashlib.sha256(BINARY.read_bytes()).hexdigest(),
        train_views=len(train["frames"]),
        test_views=len(test["frames"]),
        total_steps=args.steps,
        final_checkpoint_preselected=True,
        intermediate_test_based_selection=False,
        seed=1729,
        backend_dataloader_seed_in_pinned_source=42,
        env_overrides={k: env[k] for k in ["RUST_LOG", "XDG_CACHE_HOME", "TMPDIR"]},
    )
    config.update(
        cwd=str(output),
        cache_policy="Fresh per-run working directory isolates CubeCL target/autotune cache from iCloud placeholders",
        purpose=args.purpose,
        evaluation_role="development validation on toy object"
        if args.purpose == "backend-development"
        else "held-out snowpark cameras used for view-count development after 8-view inspection; not an independent blind final test"
        if args.purpose == "view-count-development"
        else "held-out snowpark cameras; fixed final step before this first scene training",
    )
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    print("BRUSH_OUTPUT", output, flush=True)
    start = time.monotonic()
    proc = run_logged(command, output / "train.log", cwd=output, env=env, timeout=3600)
    elapsed = time.monotonic() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = dict(
        exit_code=proc.returncode,
        seconds=elapsed,
        peak_child_rss_bytes=usage.ru_maxrss,
        peak_memory_scope="macOS RUSAGE_CHILDREN RSS; not GPU allocation",
        outputs=[
            str(parser.relative_to(output))
            for parser in output.rglob("*")
            if parser.is_file() and parser.suffix in [".ply", ".png"]
        ],
        status="PROCESS_EXITED_NOT_YET_ARTIFACT_VERIFIED",
    )
    (output / "execution.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(output=str(output), **result)), flush=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
