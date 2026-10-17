"""Compare snow shading and save readable grooves in material preview."""

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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["build", "verify"])
    parser.add_argument("--output", type=Path)
    add_blender_argument(parser)
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    if args.stage == "build":
        if args.output is not None:
            raise ValueError("A build creates its own output directory; omit --output")
        output = new_run("presentation")
        shutil.copy2(ROOT / "configs/scene/presentation.toml", output / "config.toml")
        old = {
            str(f.relative_to(ROOT)): sha(f)
            for d in (ROOT / "outputs").iterdir()
            if d.is_dir() and d != output
            for f in d.rglob("*")
            if f.is_file()
        }
        write(output / "preserved-files.json", old)
    else:
        if not args.output:
            raise ValueError("--output is required for an existing run")
        output = within(args.output, ROOT / "outputs", directory=True)
    config_data = tomllib.loads((output / "config.toml").read_text())
    source = output / "source" / args.stage
    source.mkdir(parents=True, exist_ok=False)
    snapshot_runtime(source)
    files = [Path(__file__), ROOT / "scripts/presentation_scene.py", output / "config.toml"] + [
        ROOT / "scripts" / n
        for n in ["scene_support.py", "terrain_geometry.py", "terrain_profile.py", "build_scene.py"]
    ]
    for f in files:
        shutil.copy2(f, source / f.name)
    write(source / "manifest.json", {str(f): sha(f) for f in files})
    blend = (
        ROOT / config_data["source"]["blend"]
        if args.stage == "build"
        else output / "snowpark-presentation.blend"
    )
    command = blender_command(
        blender,
        str(ROOT / "scripts/presentation_scene.py"),
        [args.stage, "--output", str(output)],
        scene=str(blend),
    )
    tick = time.monotonic()
    result = run_logged(command, output / (args.stage + ".log"), timeout=1800, cwd=ROOT)
    append_execution(
        output / "execution.jsonl",
        **dict(
            stage=args.stage,
            command=command,
            exit_code=result.returncode,
            seconds=time.monotonic() - tick,
        ),
    )
    print("PRESENTATION", args.stage, "EXIT", result.returncode, "OUTPUT", output)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
