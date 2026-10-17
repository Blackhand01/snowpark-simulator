"""Add only the static athlete after the recorded snow decision."""

import argparse, json
from pathlib import Path
import sys, tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_support import ROOT, write, environment_signature, render
from athlete_proxy import build
import bpy
from mathutils import Vector


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    a = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    out = a.output.resolve()
    assert out.is_relative_to(ROOT / "outputs") and not (out / "snowpark-athlete.blend").exists()
    decision = json.loads((out / "snow-decision.json").read_text())
    assert decision["selected"] in ["baseline", "pbr"]
    c = tomllib.loads(a.config.read_text())
    s = bpy.context.scene
    before = json.loads((out / "environment-before.json").read_text())
    assert environment_signature() == before, "P1_GEOMETRY_CHANGED_BEFORE_ATHLETE"
    rig, meta = build(s, c["athlete"])
    assert environment_signature() == before, "P1_GEOMETRY_CHANGED_BY_ATHLETE"
    col = bpy.data.collections.new("P2_Views")
    s.collection.children.link(col)
    d = bpy.data.cameras.new("P2_detail")
    cam = bpy.data.objects.new("P2_detail", d)
    col.objects.link(cam)
    cam.location = c["athlete"]["preview_position"]
    cam.rotation_euler = (
        (Vector(c["athlete"]["preview_target"]) - cam.location).to_track_quat("-Z", "Y").to_euler()
    )
    d.lens = c["athlete"]["preview_lens_mm"]
    d.clip_end = 500
    s.camera = s.objects["Preview_main"]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                v = area.spaces.active
                v.region_3d.view_location = (-1, 0, 0.7)
                v.region_3d.view_distance = 10
                v.overlay.show_extras = False
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "snowpark-athlete.blend"))
    report = dict(athlete=meta, snow_decision=decision, environment_unchanged=True, renders=[])
    write(out / "athlete-build.json", report)
    for camera, filename in [
        (s.objects["Preview_main"], "athlete-main.png"),
        (cam, "athlete-detail.png"),
    ]:
        s.camera = camera
        report["renders"].append(render(s, out / filename))
        write(out / "athlete-build.json", report)
    print("P2_ATHLETE_BUILT")


if __name__ == "__main__":
    main()
