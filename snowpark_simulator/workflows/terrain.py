"""Refine the downhill terrain and rail supports in a versioned scene."""

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
    parser.add_argument("stage", choices=["compare", "finish", "verify", "reproduce"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--snow", choices=["baseline", "pbr"])
    parser.add_argument("--reason")
    add_blender_argument(parser)
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    if args.stage == "compare":
        if args.output is not None:
            raise ValueError("A new compare always gets a new output directory")
        output = new_run("refine")
        shutil.copy2(ROOT / "configs/scene/terrain.toml", output / "config.toml")
        frozen = {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for d in (ROOT / "outputs").iterdir()
            if d.is_dir() and d.name.startswith(("p1-", "p2-"))
            for f in d.rglob("*")
            if f.is_file()
        }
        (output / "preserved-before.json").write_text(json.dumps(frozen, indent=2) + "\n")
    else:
        if not args.output:
            parser.error("--output required")
        output = within(args.output, ROOT / "outputs", directory=True)
    config_data = tomllib.loads((output / "config.toml").read_text())
    if args.stage == "finish":
        comparison = json.loads((output / "snow-comparison.json").read_text())
        if not (comparison["identical_geometry"] and comparison["identical_render_contract"]):
            raise ValueError(
                "Invalid workflow input: comparison['identical_geometry'] and comparison['identical_render_contract']"
            )
        if not (output / "snow-decision.json").exists():
            if not args.snow or not args.reason:
                parser.error("--snow and --reason required after inspecting comparison renders")
            (output / "snow-decision.json").write_text(
                json.dumps(dict(selected=args.snow, reason=args.reason), indent=2) + "\n"
            )
        choice = json.loads((output / "snow-decision.json").read_text())["selected"]
    label = args.stage
    attempt = 1
    while (output / "source" / label).exists():
        if args.stage not in ["verify", "reproduce"]:
            raise ValueError("Build/render stages cannot overwrite a previous attempt")
        attempt += 1
        label = args.stage + "-" + str(attempt)
    source = output / "source" / label
    source.mkdir(parents=True, exist_ok=False)
    snapshot_runtime(source)
    names = [
        "terrain_profile.py",
        "terrain_geometry.py",
        "athlete_fit.py",
        "refine_terrain.py",
        "verify_terrain.py",
        "build_scene.py",
        "athlete_proxy.py",
        "scene_support.py",
        "compare_snow.py",
    ]
    files = [ROOT / "scripts" / n for n in names] + [Path(__file__), output / "config.toml"]
    manifest = {}
    for f in files:
        shutil.copy2(f, source / f.name)
        manifest[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    (source / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if args.stage in ["compare", "reproduce"]:
        blend = ROOT / config_data["source"]["p1_blend"]
    elif args.stage == "finish":
        blend = output / (
            "environment-baseline.blend"
            if choice == "baseline"
            else "environment-pbr-candidate.blend"
        )
    else:
        blend = output / "snowpark-refined.blend"
    command = blender_command(
        blender,
        str(
            ROOT
            / "scripts"
            / ("verify_terrain.py" if args.stage == "verify" else "refine_terrain.py")
        ),
        ["--output", str(output)],
        scene=str(blend),
    )
    if args.stage != "verify":
        command += ["--stage", args.stage, "--config", str(output / "config.toml")]
    tick = time.monotonic()
    log = output / (label + "-execution.log")
    if log.exists():
        raise ValueError("Stage log already exists; create a fresh attempt")
    proc = run_logged(command, log, timeout=2400, cwd=ROOT)
    append_execution(
        output / "execution.jsonl",
        **dict(
            stage=args.stage,
            attempt=attempt,
            command=command,
            exit_code=proc.returncode,
            seconds=time.monotonic() - tick,
            log=log.name,
        ),
    )
    print("REFINEMENT", args.stage, "EXIT", proc.returncode, "OUTPUT", output, flush=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
