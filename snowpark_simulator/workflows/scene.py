"""Build a static snowpark, render four views and independently reopen it."""

import argparse
import datetime
import hashlib
import json
import shutil
import time
from pathlib import Path

from snowpark_simulator.artifacts import ROOT, new_run, snapshot_runtime, within
from snowpark_simulator.execution import (
    add_blender_argument,
    blender_command,
    resolve_blender,
    run_logged,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    add_blender_argument(parser)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/scene/static.toml")
    parser.add_argument(
        "--without-reference",
        action="store_true",
        help="Build procedurally without a local reference photograph",
    )
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    config = within(args.config, ROOT)
    if not config.is_relative_to(ROOT):
        raise ValueError("Configuration must be inside the repository")
    reference = ROOT / "references/snowpark-rail.png"
    if not args.without_reference and (not reference.is_file()):
        raise FileNotFoundError(reference)
    output = new_run("p1")
    shutil.copy2(config, output / "config.toml")
    source = output / "source"
    source.mkdir()
    snapshot_runtime(source)
    for path in [Path(__file__), ROOT / "scripts/build_scene.py", ROOT / "scripts/verify_scene.py"]:
        shutil.copy2(path, source / path.name)
    inputs = [
        Path(__file__),
        ROOT / "scripts/build_scene.py",
        ROOT / "scripts/verify_scene.py",
        config,
    ]
    if not args.without_reference:
        inputs.append(reference)
    hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in inputs
    }
    report = dict(
        started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        output=str(output),
        input_sha256=hashes,
        steps=[],
    )
    report_path = output / "execution.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    steps = [
        (
            "build",
            blender_command(
                blender,
                ROOT / "scripts/build_scene.py",
                ["--config", str(output / "config.toml"), "--output", str(output)],
            ),
        ),
        (
            "reopen-verify",
            blender_command(
                blender,
                ROOT / "scripts/verify_scene.py",
                ["--output", str(output)],
                scene=output / "snowpark.blend",
            ),
        ),
    ]
    if args.without_reference:
        steps[0][1].append("--without-reference")
    for name, command in steps:
        print(name, str(output), flush=True)
        tick = time.monotonic()
        proc = run_logged(command, output / (name + ".log"), timeout=1800, cwd=ROOT)
        report["steps"].append(
            dict(
                name=name,
                command=command,
                exit_code=proc.returncode,
                seconds=time.monotonic() - tick,
                log=name + ".log",
            )
        )
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        if proc.returncode:
            raise SystemExit(f"{name} failed ({proc.returncode}); inspect {output}/{name}.log")
    report["status"] = "BUILD_AND_REOPEN_VERIFIED"
    report["gui_viewport_verified"] = False
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print("P1_OUTPUT", str(output), flush=True)


if __name__ == "__main__":
    main()
