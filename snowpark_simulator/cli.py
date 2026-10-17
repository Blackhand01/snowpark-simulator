"""One explicit CLI for scene creation, capture and optional reconstruction."""

import argparse
import subprocess
from importlib import import_module

# Keep the registry descriptive and lazy: listing commands never starts a stage.
WORKFLOWS = {
    "scene": ("snowpark_simulator.workflows.scene", "Build and verify the initial static snowpark"),
    "athlete": (
        "snowpark_simulator.workflows.athlete",
        "Compare snow, select a material, and add the static rig",
    ),
    "terrain": (
        "snowpark_simulator.workflows.terrain",
        "Refine piste morphology and terrain contact",
    ),
    "appearance": (
        "snowpark_simulator.workflows.appearance",
        "Refine clothing and equipment around the existing rig",
    ),
    "presentation": (
        "snowpark_simulator.workflows.presentation",
        "Restore snow grooves and material preview",
    ),
    "motion": (
        "snowpark_simulator.workflows.motion",
        "Build or inspect a configured kinematic movement",
    ),
    "capture": (
        "snowpark_simulator.workflows.capture",
        "Capture calibrated views, freeze pose, or verify a dataset",
    ),
    "conditions": (
        "snowpark_simulator.workflows.conditions",
        "Render the explicitly configured appearance variants",
    ),
    "brush": (
        "snowpark_simulator.workflows.brush",
        "Run an installed optional Gaussian Splatting backend",
    ),
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python3 -m snowpark_simulator",
        description="Procedural snowpark scenes and controlled synthetic-image experiments.",
        epilog="\n".join(f"{name:14} {entry[1]}" for name, entry in WORKFLOWS.items())
        + "\n\nUse COMMAND --help for stages and inputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=WORKFLOWS,
        help="Workflow to execute",
    )
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    module = import_module(WORKFLOWS[args.command][0])
    try:
        module.main(args.arguments)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(2, f"{args.command}: {error}\n")


if __name__ == "__main__":
    main()
