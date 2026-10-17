"""Run a single motion stage in a new directory, preserving the source scene."""

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["build", "verify", "render", "preview"])
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/motion/boardslide-synced.toml"
    )
    add_blender_argument(parser)
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    if args.stage == "build":
        config = within(args.config, ROOT)
        config_data = tomllib.loads(config.read_text())
        source = within(ROOT / config_data["source"]["blend"], ROOT)
        require_hash(source, config_data["source"]["sha256"])
        prefix = (
            "boardslide-synced"
            if "retime" in config_data
            else "boardslide"
            if config_data.get("rail_slide", {}).get("style") == "boardslide"
            else "rail-double-cork"
            if "air_trick" in config_data
            else "rail-slide"
            if "rail_slide" in config_data
            else "cork"
            if "trick" in config_data
            else "motion"
        )
        output = new_run(prefix)
        shutil.copy2(config, output / "config.toml")
        if "retime" in config_data:
            manifest = within(ROOT / config_data["retime"]["manifest"], ROOT)
            shutil.copy2(manifest, output / "reference-timing.json")
        (output / "source").mkdir()
        snapshot_runtime(output / "source")
        for f in [
            Path(__file__),
            ROOT / "scripts/animate_scene.py",
            ROOT / "scripts/motion_profile.py",
            ROOT / "scripts/trick_profile.py",
            ROOT / "scripts/rail_slide_profile.py",
            ROOT / "scripts/rail_slide_scene.py",
            ROOT / "scripts/terrain_profile.py",
            ROOT / "scripts/terrain_geometry.py",
            ROOT / "scripts/scene_support.py",
            ROOT / "scripts/build_scene.py",
            ROOT / "configs/scene/terrain.toml",
        ]:
            shutil.copy2(f, output / "source" / f.name)
        for name in [
            "retime_scene.py",
            "reference_clock.py",
            "encode_preview.py",
            "compare_reference.py",
        ]:
            shutil.copy2(
                ROOT
                / ("tools" if name in {"encode_preview.py", "compare_reference.py"} else "scripts")
                / name,
                output / "source" / name,
            )
    else:
        if not args.output:
            raise ValueError("--output is required for an existing run")
        output = within(args.output, ROOT / "outputs", directory=True)
        config_data = tomllib.loads((output / "config.toml").read_text())
        source = output / "snowpark-motion.blend"
    command = blender_command(
        blender,
        str(ROOT / "scripts/animate_scene.py"),
        ["--stage", args.stage, "--output", str(output)],
        scene=str(source),
    )
    snapshot = output / datetime.datetime.now(datetime.timezone.utc).strftime(
        "stage-source-" + args.stage + "-%Y%m%dT%H%M%S-%fZ"
    )
    snapshot.mkdir(exist_ok=False)
    snapshot_runtime(snapshot)
    for f in [
        Path(__file__),
        ROOT / "scripts/animate_scene.py",
        ROOT / "scripts/motion_profile.py",
        ROOT / "scripts/trick_profile.py",
        ROOT / "scripts/rail_slide_profile.py",
        ROOT / "scripts/rail_slide_scene.py",
    ]:
        shutil.copy2(f, snapshot / f.name)
    for name in [
        "retime_scene.py",
        "reference_clock.py",
        "encode_preview.py",
        "compare_reference.py",
    ]:
        shutil.copy2(
            ROOT
            / ("tools" if name in {"encode_preview.py", "compare_reference.py"} else "scripts")
            / name,
            snapshot / name,
        )
    log = output / (
        args.stage
        + "-"
        + datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S-%f")
        + ".log"
    )
    start = time.monotonic()
    proc = run_logged(command, log, timeout=1800, cwd=ROOT)
    append_execution(
        output / "execution.jsonl",
        **dict(
            stage=args.stage,
            command=command,
            seconds=time.monotonic() - start,
            exit_code=proc.returncode,
            log=log.name,
            stage_source=str(snapshot.relative_to(output)),
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
