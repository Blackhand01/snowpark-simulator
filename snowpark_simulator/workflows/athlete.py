"""Compare snow, explicitly select a material and add a standard static rig."""

import argparse
import datetime
import hashlib
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
    parser.add_argument("stage", choices=["compare", "athlete", "verify"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--snow", choices=["baseline", "pbr"])
    parser.add_argument("--reason")
    add_blender_argument(parser)
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    config_data = tomllib.loads((ROOT / "configs/scene/athlete.toml").read_text())
    if args.stage == "compare":
        output = new_run("p2")
        original = ROOT / config_data["source"]["p1_blend"]
        require_hash(original, config_data["source"]["p1_sha256"])
        shutil.copy2(original, output / "snow-baseline.blend")
        shutil.copy2(ROOT / "configs/scene/athlete.toml", output / "p2_config.toml")
        frozen = {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in original.parent.rglob("*")
            if f.is_file()
        }
        (output / "p1-preservation-before.json").write_text(json.dumps(frozen, indent=2) + "\n")
    else:
        if not args.output:
            parser.error("--output required")
        output = within(args.output, ROOT / "outputs", directory=True)
    if args.stage == "athlete":
        report = json.loads((output / "snow-comparison.json").read_text())
        if not (report["identical_environment_geometry"] and report["identical_render_contract"]):
            raise ValueError(
                "Invalid workflow input: report['identical_environment_geometry'] and report['identical_render_contract']"
            )
        if not (output / "snow-decision.json").exists():
            if not args.snow or not args.reason:
                parser.error("--snow and --reason required for visual selection")
            (output / "snow-decision.json").write_text(
                json.dumps(
                    dict(
                        selected=args.snow,
                        reason=args.reason,
                        decision_by="Explicit visual selection",
                    ),
                    indent=2,
                )
                + "\n"
            )
        chosen = json.loads((output / "snow-decision.json").read_text())["selected"]
    script = {
        "compare": "compare_snow.py",
        "athlete": "build_athlete.py",
        "verify": "verify_athlete.py",
    }[args.stage]
    blend = (
        output
        / {
            "compare": "snow-baseline.blend",
            "athlete": "snow-pbr-candidate.blend"
            if args.stage == "athlete" and chosen == "pbr"
            else "snow-baseline.blend",
            "verify": "snowpark-athlete.blend",
        }[args.stage]
    )
    command = blender_command(
        blender, str(ROOT / "scripts" / script), ["--output", str(output)], scene=str(blend)
    )
    if args.stage != "verify":
        command += ["--config", str(output / "p2_config.toml")]
    source = output / "source"
    source.mkdir(exist_ok=True)
    snapshot_runtime(source)
    for f in [
        Path(__file__),
        ROOT / "configs/scene/athlete.toml",
        *[
            ROOT / "scripts" / n
            for n in [
                "scene_support.py",
                "compare_snow.py",
                "athlete_proxy.py",
                "build_athlete.py",
                "verify_athlete.py",
            ]
        ],
    ]:
        target = source / f.name
        if target.exists():
            if not target.read_bytes() == f.read_bytes():
                raise ValueError(f"SOURCE_CHANGED: {f}")
        else:
            shutil.copy2(f, target)
    log = output / (args.stage + "-execution.log")
    if log.exists():
        log = output / (
            args.stage
            + "-"
            + datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S")
            + "-execution.log"
        )
    tick = time.monotonic()
    proc = run_logged(command, log, timeout=1800, cwd=ROOT)
    append_execution(
        output / "execution.jsonl",
        **dict(
            stage=args.stage,
            command=command,
            exit_code=proc.returncode,
            seconds=time.monotonic() - tick,
            log=log.name,
        ),
    )
    print("P2_STAGE", args.stage, "EXIT", proc.returncode, "OUTPUT", output, flush=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
