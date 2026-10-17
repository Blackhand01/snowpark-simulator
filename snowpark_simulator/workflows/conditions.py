"""Render an explicit conditions matrix, preserving accepted inputs and prior runs."""

import argparse
import json
import shutil
from pathlib import Path

from snowpark_simulator.artifacts import (
    ROOT,
    new_run,
    require_hash,
    sha256,
    snapshot_runtime,
    within,
    write_json,
)
from snowpark_simulator.conditions import validate_conditions
from snowpark_simulator.execution import (
    add_blender_argument,
    append_execution,
    blender_command,
    resolve_blender,
    run_logged,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/conditions/matrix.json")
    add_blender_argument(parser)
    args = parser.parse_args(argv)
    blender = resolve_blender(args.blender)
    config = within(args.config, ROOT)
    matrix = json.loads(config.read_text())
    names = validate_conditions(matrix)
    dataset = within(ROOT / matrix["dataset"], ROOT, directory=True)
    baseline = within(ROOT / matrix["baseline"], ROOT, directory=True)
    if json.loads((baseline / "artifact-verification.json").read_text())["status"] != "PASS":
        raise ValueError("Baseline artifact verification has not passed")
    within(baseline / "acceptance.json", ROOT)
    if json.loads((dataset / "acceptance.json").read_text())["status"] != "PASS_AUTO_VALIDATED":
        raise ValueError("Dataset acceptance has not passed")
    inputs = [
        within(path, ROOT)
        for path in [
            dataset / "frozen-pose.blend",
            dataset / "capture.blend",
            baseline / "model_5000.ply",
        ]
    ]
    hashes = {str(path.relative_to(ROOT)): sha256(path) for path in inputs}
    output = new_run("conditions")
    shutil.copy2(config, output / "conditions.json")
    source = output / "source"
    source.mkdir()
    snapshot_runtime(source)
    for path in [
        Path(__file__),
        ROOT / "scripts/render_conditions.py",
        ROOT / "scripts/capture_scene.py",
        ROOT / "scripts/scene_support.py",
    ]:
        shutil.copy2(path, source / path.name)
    write_json(output / "input-hashes.json", hashes)
    print("CONDITIONS_OUTPUT", output, flush=True)
    for name in names:
        command = blender_command(
            blender,
            ROOT / "scripts/render_conditions.py",
            ["--run", str(output), "--condition", name],
        )
        result = run_logged(command, output / (name + ".log"), timeout=1800)
        append_execution(
            output / "execution.jsonl",
            condition=name,
            command=command,
            seconds=result.seconds,
            exit_code=result.returncode,
        )
        print(name, "exit", result.returncode, flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    for path, digest in hashes.items():
        require_hash(ROOT / path, digest)
    write_json(
        output / "render-completion.json",
        dict(
            status="RENDER_MATRIX_COMPLETE_NOT_YET_HOST_VERIFIED",
            conditions=len(names),
            input_hashes_unchanged=True,
        ),
    )


if __name__ == "__main__":
    main()
