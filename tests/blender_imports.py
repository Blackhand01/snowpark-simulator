"""Opt-in Blender integration check for the reorganized scene libraries.

Run through Blender --background --offline-mode --disable-autoexec --python
tests/blender_imports.py -- --output .local/blender-imports.json.
Does not build, render or save scenes. Not part of unittest discovery.
"""

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = (
    "build_scene",
    "verify_scene",
    "scene_support",
    "terrain_profile",
    "terrain_geometry",
    "refine_terrain",
    "verify_terrain",
    "athlete_proxy",
    "athlete_fit",
    "build_athlete",
    "verify_athlete",
    "athlete_clothing",
    "refine_appearance",
    "compare_snow",
    "presentation_scene",
    "motion_profile",
    "trick_profile",
    "rail_slide_profile",
    "rail_slide_scene",
    "reference_clock",
    "retime_scene",
    "animate_scene",
    "capture_scene",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / ".local"):
        raise ValueError("Integration evidence must be inside .local/")
    before = set(bpy.data.objects.keys())
    sys.path.insert(0, str(ROOT / "scripts"))
    for name in LIBRARIES:
        import_module(name)
    if set(bpy.data.objects.keys()) != before:
        raise AssertionError("Import modified scene objects")
    with output.open("x") as stream:
        json.dump(
            dict(
                status="PASS",
                libraries=list(LIBRARIES),
                blender=bpy.app.version_string,
                scene_objects_unchanged=True,
                scene_saved=False,
            ),
            stream,
            indent=2,
        )
    print("BLENDER_IMPORTS_PASS", len(LIBRARIES))


if __name__ == "__main__":
    main()
