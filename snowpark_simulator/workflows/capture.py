"""Capture one frozen pose or independently validate an existing dataset."""

import argparse
import datetime
import json
import shutil
import time
import tomllib
from pathlib import Path

from snowpark_simulator.artifacts import ROOT, new_run, require_hash, snapshot_runtime, within
from snowpark_simulator.execution import (
    add_blender_argument,
    append_execution,
    blender_command,
    resolve_blender,
    run_logged,
)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["capture", "freeze", "verify"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/capture/pose.toml")
    add_blender_argument(parser)
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    if args.stage == "capture":
        config = within(args.config, ROOT)
        config_data = tomllib.loads(config.read_text())
        source = within(ROOT / config_data["source"]["blend"], ROOT)
        require_hash(source, config_data["source"]["sha256"])
        output = new_run("capture")
        shutil.copy2(config, output / "config.toml")
        (output / "source").mkdir()
        snapshot_runtime(output / "source")
        for f in [
            Path(__file__),
            ROOT / "scripts/capture_scene.py",
            ROOT / "scripts/scene_support.py",
            ROOT / "scripts/build_scene.py",
            ROOT / "scripts/animate_scene.py",
            ROOT / "scripts/motion_profile.py",
            ROOT / "scripts/trick_profile.py",
            ROOT / "scripts/terrain_geometry.py",
            ROOT / "scripts/terrain_profile.py",
        ]:
            shutil.copy2(f, output / "source" / f.name)
    else:
        if not args.output:
            raise ValueError("--output is required for an existing run")
        output = within(args.output, ROOT / "outputs", directory=True)
        source = output / ("frozen-pose.blend" if args.stage == "verify" else "capture.blend")
    snap = output / datetime.datetime.now(datetime.timezone.utc).strftime(
        "stage-source-" + args.stage + "-%Y%m%dT%H%M%S-%fZ"
    )
    snap.mkdir(exist_ok=False)
    snapshot_runtime(snap)
    for file in [Path(__file__), ROOT / "scripts/capture_scene.py"]:
        shutil.copy2(file, snap / file.name)
    command = blender_command(
        blender,
        str(ROOT / "scripts/capture_scene.py"),
        ["--stage", args.stage, "--output", str(output)],
        scene=str(source),
    )
    log = output / (
        args.stage
        + "-"
        + datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S-%f")
        + ".log"
    )
    t = time.monotonic()
    proc = run_logged(command, log, timeout=1800, cwd=ROOT)
    append_execution(
        output / "execution.jsonl",
        **dict(
            stage=args.stage,
            command=command,
            seconds=time.monotonic() - t,
            exit_code=proc.returncode,
            log=log.name,
        ),
    )
    print(
        json.dumps(dict(output=str(output), stage=args.stage, exit_code=proc.returncode)),
        flush=True,
    )
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
