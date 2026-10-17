"""Reopen every saved condition and inspect real scene properties/geometry."""

import argparse
import json
import math
from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_scene import pose_hash
from scene_support import sha, write

p = argparse.ArgumentParser()
p.add_argument("--run", type=Path, required=True)
a = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
root = Path(__file__).resolve().parents[1]
out = a.run.resolve()
assert out.is_relative_to(root / "outputs")
matrix = json.loads((out / "conditions.json").read_text())
dataset = root / matrix["dataset"]
data = json.loads((dataset / "dataset.json").read_text())
bpy.ops.wm.open_mainfile(filepath=str(dataset / "frozen-pose.blend"))
base_z = [v.co.z for v in bpy.data.objects["Snow_terrain"].data.vertices]
checks = {}
details = {}
for profile in matrix["conditions"]:
    name = profile["name"]
    m = json.loads((out / name / "metadata.json").read_text())
    path = out / name / "variant.blend"
    checks[name + "_saved_hash"] = sha(path) == m["variant_sha256"]
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    scene.frame_set(data["frame"])
    bpy.context.view_layer.update()
    checks[name + "_pose_saved"] = pose_hash() == data["pose_sha256"]
    checks[name + "_seed_engine"] = (
        scene.cycles.seed == profile["seed"] and scene.render.engine == "CYCLES"
    )
    checks[name + "_effective_exposure"] = (
        abs(scene.view_settings.exposure - m["effective_exposure_ev"]) < 1e-7
    )
    checks[name + "_blur_flag"] = scene.render.use_motion_blur == (profile["blur_exposure_s"] > 0)
    if profile["blur_exposure_s"]:
        checks[name + "_blur_duration"] = (
            abs(
                scene.render.motion_blur_shutter * scene.render.fps_base / scene.render.fps
                - profile["blur_exposure_s"]
            )
            < 1e-9
        )
        positions = []
        for f in [
            data["frame"] - scene.render.motion_blur_shutter / 2,
            data["frame"] + scene.render.motion_blur_shutter / 2,
        ]:
            scene.frame_set(math.floor(f), subframe=f - math.floor(f))
            bpy.context.view_layer.update()
            positions.append(scene.objects["ANIM_Translation"].matrix_world.translation.copy())
        checks[name + "_actual_motion_during_shutter"] = (positions[1] - positions[0]).length > 1e-5
        scene.frame_set(data["frame"])
        bpy.context.view_layer.update()

    if profile["white_balance_kelvin"] is not None:
        checks[name + "_wb_saved"] = (
            scene.view_settings.use_white_balance
            and abs(scene.view_settings.white_balance_temperature - profile["white_balance_kelvin"])
            < 0.1
        )
    checks[name + "_actual_particle_objects"] = (
        sum(o.name.startswith("P9_Snow_") for o in scene.objects) == profile["snow_count"]
    )
    checks[name + "_actual_occluder"] = ("P9_Controlled_occluder" in scene.objects) == profile[
        "occluder"
    ]
    checks[name + "_actual_haze"] = ("P9_Haze_volume" in scene.objects) == bool(
        profile["haze_density"]
    )
    if profile["haze_density"]:
        node = next(
            n
            for n in bpy.data.materials["P9_Haze"].node_tree.nodes
            if n.bl_idname == "ShaderNodeVolumeScatter"
        )
        checks[name + "_haze_density"] = (
            abs(node.inputs["Density"].default_value - profile["haze_density"]) < 1e-7
        )
    terrain = scene.objects["Snow_terrain"]
    dz = max(abs(v.co.z - z) for v, z in zip(terrain.data.vertices, base_z))
    checks[name + "_moderate_actual_relief"] = (
        len(terrain.data.vertices) == len(base_z)
        and dz <= profile["snow_relief_m"] + 1e-5
        and (dz > 0 if profile["snow_relief_m"] else dz == 0)
    )
    if profile["snow_texture_strength"]:
        checks[name + "_actual_texture_nodes"] = True
        for mat in terrain.data.materials:
            bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            mix = bsdf.inputs["Base Color"].links[0].from_node
            checks[name + "_actual_texture_nodes"] &= (
                mix.bl_idname == "ShaderNodeMixRGB"
                and mix.blend_type == "MULTIPLY"
                and abs(mix.inputs[0].default_value - profile["snow_texture_strength"]) < 1e-7
            )
    sun = next(o for o in scene.objects if o.type == "LIGHT" and o.data.type == "SUN")
    checks[name + "_light_persisted"] = abs(sun.data.energy - m["sun_energy"]) < 1e-7
    details[name] = dict(actual_max_terrain_z_change_m=dz, particle_objects=profile["snow_count"])
write(
    out / "scene-verification.json",
    dict(
        status="PASS" if all(checks.values()) else "FAIL",
        checks=checks,
        details=details,
        scope="Saved scene parameters/pose/geometry; not physical validation",
    ),
)
assert all(checks.values()), {k: v for k, v in checks.items() if not v}
print("PASS", len(checks), "saved-scene checks")
