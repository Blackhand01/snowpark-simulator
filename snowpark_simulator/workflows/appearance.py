"""Refine clothing and equipment around the existing athlete rig."""

import argparse
import hashlib
import json
import shutil
import time
import tomllib
from pathlib import Path

from snowpark_simulator.artifacts import ROOT, new_run, snapshot_runtime, within
from snowpark_simulator.execution import (
    add_blender_argument,
    append_execution,
    blender_command,
    resolve_blender,
    run_logged,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["build", "render", "verify", "reproduce"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--geometry-only", action="store_true")
    add_blender_argument(parser)
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    if args.geometry_only and args.stage != "verify":
        parser.error("--geometry-only is valid only for verify")
    if args.stage == "build":
        if args.output is not None:
            raise ValueError("A build creates its own output directory; omit --output")
        output = new_run("athlete-look")
        shutil.copy2(ROOT / "configs/scene/appearance.toml", output / "config.toml")
        files = {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for d in (ROOT / "outputs").iterdir()
            if d.is_dir() and d != output
            for f in d.rglob("*")
            if f.is_file()
        }
        (output / "preserved-files.json").write_text(json.dumps(files, indent=2) + "\n")
    else:
        if not args.output:
            parser.error("--output required")
        output = within(args.output, ROOT / "outputs", directory=True)
    config_data = tomllib.loads((output / "config.toml").read_text())
    label = "geometry-check" if args.geometry_only else args.stage
    n = 1
    while (output / "source" / label).exists():
        if args.stage not in ["verify", "reproduce"]:
            raise ValueError("Build and render never overwrite earlier attempts")
        n += 1
        label = args.stage + "-" + str(n)
    source = output / "source" / label
    source.mkdir(parents=True)
    snapshot_runtime(source)
    inputs = [
        ROOT / "scripts" / name
        for name in [
            "athlete_clothing.py",
            "refine_appearance.py",
            "build_scene.py",
            "scene_support.py",
            "terrain_geometry.py",
            "terrain_profile.py",
        ]
    ] + [Path(__file__), output / "config.toml"]
    manifest = {}
    for f in inputs:
        shutil.copy2(f, source / f.name)
        manifest[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    (source / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    blend = (
        ROOT / config_data["source"]["blend"]
        if args.stage in ["build", "reproduce"]
        else output / "snowpark-tailored-athlete.blend"
    )
    command = blender_command(
        blender,
        str(ROOT / "scripts/refine_appearance.py"),
        ["--stage", args.stage, "--output", str(output)],
        scene=str(blend),
    )
    if args.geometry_only:
        command.append("--geometry-only")
    tick = time.monotonic()
    log = output / (label + ".log")
    proc = run_logged(command, log, timeout=3000, cwd=ROOT)
    append_execution(
        output / "execution.jsonl",
        **dict(
            stage=args.stage,
            attempt=n,
            command=command,
            exit_code=proc.returncode,
            seconds=time.monotonic() - tick,
            log=log.name,
        ),
    )
    print("ATHLETE_LOOK", args.stage, "EXIT", proc.returncode, "OUTPUT", output, flush=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
