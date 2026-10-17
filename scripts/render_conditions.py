"""Controlled visual variants of the accepted pose; no weather/sensor dynamics."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_scene import pose_hash, calibration
from scene_support import render, sha, write

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--run", type=Path, required=True)
p.add_argument("--condition", required=True)
a = p.parse_args(sys.argv[sys.argv.index("--") + 1 :])
run = a.run.resolve()
assert run.is_relative_to(ROOT / "outputs")
matrix = json.loads((run / "conditions.json").read_text())
profile = next(c for c in matrix["conditions"] if c["name"] == a.condition)
dataset = ROOT / matrix["dataset"]
data = json.loads((dataset / "dataset.json").read_text())
frames = [
    f for f in json.loads((dataset / "cameras.json").read_text())["frames"] if f["split"] == "test"
]
assert len(frames) == 2
out = run / a.condition
out.mkdir(exist_ok=False)
(out / "images").mkdir()
source = dataset / ("capture.blend" if profile["blur_exposure_s"] else "frozen-pose.blend")
before = sha(source)
bpy.ops.wm.open_mainfile(filepath=str(source))
scene = bpy.context.scene
scene.frame_set(data["frame"])
bpy.context.view_layer.update()
assert pose_hash() == data["pose_sha256"]
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.seed = profile["seed"]
scene.cycles.samples = data["render_contract"]["samples"]
scene.render.threads_mode = "FIXED"
scene.render.threads = 4
scene.view_settings.exposure = (
    data["render_contract"]["exposure"] + profile["exposure_ev"] + math.log2(profile["gain"])
)
if profile["white_balance_kelvin"] is not None:
    scene.view_settings.use_white_balance = True
    scene.view_settings.white_balance_temperature = profile["white_balance_kelvin"]
    scene.view_settings.white_balance_tint = 0
scene.render.use_motion_blur = profile["blur_exposure_s"] > 0
scene.render.motion_blur_shutter = (
    profile["blur_exposure_s"] * scene.render.fps / scene.render.fps_base
    if profile["blur_exposure_s"]
    else 0.5
)
scene.render.motion_blur_position = "CENTER"
sun = next(o for o in scene.objects if o.type == "LIGHT" and o.data.type == "SUN")
background = scene.world.node_tree.nodes["Background"]
light = profile["lighting"]
if light == "sun":
    sun.data.energy *= 1.25
    background.inputs["Strength"].default_value *= 0.75
    sun.data.angle = 0.035
elif light == "overcast":
    sun.data.energy = 0
    background.inputs["Strength"].default_value *= 2.5
    background.inputs["Color"].default_value = (0.75, 0.8, 0.85, 1)
elif light == "backlight":
    origin = Vector(data["athlete_origin_world_m"])
    cam = scene.objects[frames[0]["camera_object"]]
    delta = cam.matrix_world.translation - origin
    direction = Vector((delta.x, delta.y, -abs(delta.z))).normalized()
    sun.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    sun.data.energy *= 1.5
    background.inputs["Strength"].default_value *= 0.3
col = bpy.data.collections.new("P9_Conditions")
scene.collection.children.link(col)


def move_to_conditions(obj):
    for previous in list(obj.users_collection):
        previous.objects.unlink(obj)
    col.objects.link(obj)


def surface(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.65
    return mat


particle_records = []
if profile["snow_count"]:
    rng = random.Random(profile["seed"])
    brightness = min(0.95, 0.85 * profile["snow_brightness"])
    mat = surface("P9_Suspended_snow", (brightness, brightness, brightness))
    mesh = None
    for i in range(profile["snow_count"]):
        xyz = (rng.uniform(-6, 6), rng.uniform(-7.8, 4.2), rng.uniform(0.2, 5.5))
        radius = rng.uniform(0.015, 0.04)
        if mesh is None:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1)
            obj = bpy.context.object
            mesh = obj.data
            mesh.materials.append(mat)
            move_to_conditions(obj)
        else:
            obj = bpy.data.objects.new(f"P9_Snow_{i:04d}", mesh)
            col.objects.link(obj)
        obj.name = f"P9_Snow_{i:04d}"
        obj.location = xyz
        obj.scale = (radius,) * 3
        particle_records.append([*xyz, radius])
if profile["haze_density"]:
    bpy.ops.mesh.primitive_cube_add(size=60, location=(0, 0, 10))
    obj = bpy.context.object
    obj.name = "P9_Haze_volume"
    move_to_conditions(obj)
    mat = bpy.data.materials.new("P9_Haze")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    scatter = nodes.new("ShaderNodeVolumeScatter")
    scatter.inputs["Density"].default_value = profile["haze_density"]
    scatter.inputs["Color"].default_value = (0.85, 0.9, 0.98, 1)
    scatter.inputs["Anisotropy"].default_value = 0
    mat.node_tree.links.new(scatter.outputs[0], output.inputs["Volume"])
    obj.data.materials.append(mat)
if profile["occluder"]:
    origin = Vector(data["athlete_origin_world_m"]) + Vector((0, 0, 0.7))
    cam = scene.objects[frames[0]["camera_object"]]
    pos = origin.lerp(cam.matrix_world.translation, 0.4)
    pos.z = 1.8
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.13, depth=4, location=pos)
    obj = bpy.context.object
    obj.name = "P9_Controlled_occluder"
    move_to_conditions(obj)
    obj.data.materials.append(surface("P9_Orange_marker", (0.8, 0.16, 0.025)))
terrain = scene.objects["Snow_terrain"]
max_dz = 0
if profile["snow_relief_m"]:
    for v in terrain.data.vertices:
        dz = (
            profile["snow_relief_m"]
            * math.sin(2 * math.pi * v.co.x / 1.1)
            * math.sin(2 * math.pi * v.co.y / 1.6)
        )
        v.co.z += dz
        max_dz = max(max_dz, abs(dz))
    terrain.data.update()
    assert max_dz <= profile["snow_relief_m"] + 1e-9
if profile["snow_texture_strength"]:
    for mat in terrain.data.materials:
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
        base = bsdf.inputs["Base Color"]
        old = base.links[0].from_socket if base.is_linked else None
        color = tuple(base.default_value)
        mix = nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = profile["snow_texture_strength"]
        mix.inputs[1].default_value = color
        if old:
            links.new(old, mix.inputs[1])
        geom = nodes.new("ShaderNodeNewGeometry")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 4.0
        noise.inputs["Detail"].default_value = 2.0
        links.new(geom.outputs["Position"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], mix.inputs[2])
        links.new(mix.outputs[0], base)
bpy.context.view_layer.update()
assert pose_hash() == data["pose_sha256"]
scene.camera = scene.objects[frames[0]["camera_object"]]
scene["p9_profile"] = json.dumps(profile)
bpy.ops.wm.save_as_mainfile(filepath=str(out / "variant.blend"))
images = []
for frame in frames:
    scene.camera = scene.objects[frame["camera_object"]]
    bpy.context.view_layer.update()
    meta = calibration(scene, scene.camera)
    assert all(frame[k] == meta[k] for k in meta)
    record = render(scene, out / "images" / (frame["camera_id"] + ".png"))
    assert pose_hash() == data["pose_sha256"]
    images.append(
        dict(
            camera_id=frame["camera_id"],
            file_path="images/" + frame["camera_id"] + ".png",
            split="test",
            pose_id=data["pose_id"],
            pose_sha256=data["pose_sha256"],
            **meta,
            **record,
        )
    )
assert sha(source) == before
write(
    out / "metadata.json",
    dict(
        status="RENDERED_NOT_YET_HOST_VERIFIED",
        profile=profile,
        source=str(source.relative_to(ROOT)),
        source_sha256=before,
        variant_sha256=sha(out / "variant.blend"),
        blender=bpy.app.version_string,
        python=sys.version,
        seed=profile["seed"],
        center_frame=data["frame"],
        center_pose_sha256=data["pose_sha256"],
        effective_exposure_ev=scene.view_settings.exposure,
        white_balance_enabled=scene.view_settings.use_white_balance,
        effective_white_balance_kelvin=scene.view_settings.white_balance_temperature,
        blur_exposure_s=profile["blur_exposure_s"],
        actual_blur_shutter_frames=scene.render.motion_blur_shutter,
        fps=scene.render.fps,
        sun_energy=sun.data.energy,
        sun_matrix=[list(v) for v in sun.matrix_world],
        world_strength=background.inputs["Strength"].default_value,
        particles_sha256=hashlib.sha256(json.dumps(particle_records).encode()).hexdigest(),
        particle_count=len(particle_records),
        max_terrain_z_change_m=max_dz,
        images=images,
        limits="Rendering proxies only: gain mapped to EV, display white balance, static seeded snow spheres, homogeneous scattering volume, approved kinematic blur. Backlight relative to first evaluation camera; world lighting fixed across cameras. No sensor/noise, wind or granular dynamics; no GS retraining.",
    ),
)
print("CONDITION_RENDERED", a.condition, len(images))
