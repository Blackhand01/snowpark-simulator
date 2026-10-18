"""Capture the approved animation without freezing it or rebuilding geometry.

Blender 5.2 exports RGB and a visible athlete object-index matte in the same
Cycles render. Source files are read-only; all generated artifacts are new.
"""

import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from capture_scene import calibration, pose_hash, reprojection_error
from animate_scene import environment
from scene_support import render
from snowpark_simulator.pilot4d import (
    SOURCE_SHA256,
    group,
    sha,
    source_frame,
    validate_plan,
    validate_records,
    write_json,
)


def mask_compositor(scene):
    """Use the actual Blender 5.2 file-output API (not legacy file_slots)."""
    scene.view_layers[0].use_pass_object_index = True
    scene.view_layers[0].update_render_passes()
    tree = bpy.data.node_groups.new("PILOT_Visible_athlete_mask", "CompositorNodeTree")
    scene.compositing_node_group = tree
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    layers = tree.nodes.new("CompositorNodeRLayers")
    layers.scene = scene
    layers.layer = scene.view_layers[0].name
    output = tree.nodes.new("NodeGroupOutput")
    tree.links.new(layers.outputs["Image"], output.inputs["Image"])
    matte = tree.nodes.new("CompositorNodeIDMask")
    matte.inputs["Index"].default_value = 1
    matte.inputs["Anti-Alias"].default_value = True
    tree.links.new(layers.outputs["Object Index"], matte.inputs["ID value"])
    file_output = tree.nodes.new("CompositorNodeOutputFile")
    file_output.file_output_items.new("FLOAT", "Mask")
    file_output.file_name = "athlete"
    file_output.format.media_type = "IMAGE"
    file_output.format.file_format = "PNG"
    file_output.format.color_mode = "BW"
    file_output.format.color_depth = "8"
    file_output.save_as_render = False
    tree.links.new(matte.outputs[0], file_output.inputs["Mask"])
    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    return file_output


def athlete_bounds(scene):
    graph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in bpy.data.collections["P2_Athlete"].all_objects:
        if obj.type == "MESH" and not obj.hide_render:
            evaluated = obj.evaluated_get(graph)
            points.extend(evaluated.matrix_world @ Vector(v) for v in evaluated.bound_box)
    assert points
    return points


def roi(scene, cam, points):
    w, h = scene.render.resolution_x, scene.render.resolution_y
    ndc = [world_to_camera_view(scene, cam, p) for p in points]
    assert all(p.z > 0 for p in ndc), "ATHLETE_BEHIND_CAMERA"
    return [
        max(0, math.floor(min(p.x for p in ndc) * w) - 10),
        max(0, math.floor(min(1 - p.y for p in ndc) * h) - 10),
        min(w, math.ceil(max(p.x for p in ndc) * w) + 10),
        min(h, math.ceil(max(1 - p.y for p in ndc) * h) + 10),
    ]


def reuse_verified_records(source, output, plan):
    """Copy immutable completed images into a new attempt, never overwrite a run."""
    if json.loads((source / "plan.json").read_text()) != plan:
        raise ValueError("Recovery requires the identical capture plan")
    records = [json.loads(line) for line in (source / "records.jsonl").read_text().splitlines()]
    validate_records(records, complete=False)
    for item in records:
        for kind in ("image", "mask"):
            relative = (
                Path(kind + "s")
                / f"camera_{item['camera_index']:03d}_time_{item['sample_index']:03d}.png"
            )
            if Path(item[kind]) != relative:
                raise ValueError("Unexpected recovery image path")
            original = source / relative
            if sha(original) != item[kind + "_sha256"]:
                raise ValueError("Recovery image hash mismatch")
            if shutil.disk_usage(output).free < 8 * 1024**3:
                raise RuntimeError("FREE_DISK_BELOW_8_GIB")
            shutil.copy2(original, output / relative)
    with (output / "records.jsonl").open("x") as stream:
        for item in records:
            stream.write(json.dumps(item, allow_nan=False) + "\n")
    write_json(
        output / "resumed-from.json",
        dict(
            source=str(source.relative_to(ROOT)),
            records_sha256=sha(source / "records.jsonl"),
            reused_images=len(records),
            policy="Hash-verified copies; prior attempt remains unchanged",
        ),
    )
    return records


def capture(plan_path, output, smoke, resume=None):
    plan = json.loads(plan_path.read_text())
    validate_plan(plan)
    source = ROOT / plan["source"]
    assert Path(bpy.data.filepath).resolve() == source.resolve()
    assert sha(source) == SOURCE_SHA256
    assert not output.exists(), "CAPTURE_OVERWRITE_FORBIDDEN"
    assert output.resolve().is_relative_to(ROOT / "outputs")
    output.mkdir(parents=True)
    (output / "images").mkdir()
    (output / "masks").mkdir()
    write_json(output / "plan.json", plan)
    if resume and smoke:
        raise ValueError("Smoke mode cannot reuse full-resolution images")
    records = reuse_verified_records(resume, output, plan) if resume else []
    reused = {(r["camera_index"], r["sample_index"]): r for r in records}
    scene = bpy.context.scene
    before = environment()
    assert scene.render.fps / scene.render.fps_base == 120
    scene.render.resolution_x = 64 if smoke else 640
    scene.render.resolution_y = 48 if smoke else 480
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.cycles.samples = 1 if smoke else 24
    scene.cycles.seed = 1729
    scene.cycles.device = "CPU"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.use_motion_blur = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    assert scene.render.engine == "CYCLES"
    athlete = set(bpy.data.collections["P2_Athlete"].all_objects)
    for obj in scene.objects:
        obj.pass_index = int(obj in athlete and not obj.hide_render)
    file_output = mask_compositor(scene)
    collection = bpy.data.collections.new("PILOT_Fixed_cameras")
    scene.collection.children.link(collection)
    cameras = []
    for item in plan["cameras"]:
        data = bpy.data.cameras.new("PILOT_" + item["id"])
        cam = bpy.data.objects.new(data.name, data)
        collection.objects.link(cam)
        cam.location = item["origin_m"]
        cam.rotation_euler = (
            (Vector(item["target_m"]) - cam.location).to_track_quat("-Z", "Y").to_euler()
        )
        data.lens = 45
        data.sensor_width = 36
        data.sensor_fit = "HORIZONTAL"
        data.dof.use_dof = False
        cameras.append(cam)
    bpy.context.view_layer.update()
    # The saved copy retains the whole animation and all fixed cameras.
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "capture-motion.blend"))
    started = time.monotonic()
    for sample in range(1 if smoke else 31):
        scene.frame_set(source_frame(sample))
        bpy.context.view_layer.update()
        pose = pose_hash()
        bounds = athlete_bounds(scene)
        for index, cam in enumerate(cameras[:2] if smoke else cameras):
            assert time.monotonic() - started < 9000, "CAPTURE_WALL_BUDGET_EXCEEDED"
            assert shutil.disk_usage(output).free >= 8 * 1024**3, "FREE_DISK_BELOW_8_GIB"
            scene.camera = cam
            bpy.context.view_layer.update()
            meta = calibration(scene, cam)
            previous = reused.get((index, sample))
            if previous:
                if (
                    previous["pose_sha256"] != pose
                    or previous["camera_to_world_blender"] != meta["camera_to_world_blender"]
                ):
                    raise ValueError("Recovered pose or camera disagrees with the reopened scene")
                continue
            error, points = reprojection_error(scene, cam, meta)
            assert error < 0.001, (cam.name, error)
            stem = f"camera_{index:03d}_time_{sample:03d}"
            temporary = output / "mask-temporary" / stem
            temporary.mkdir(parents=True)
            file_output.directory = str(temporary)
            image = output / "images" / (stem + ".png")
            execution = render(scene, image)
            masks = list(temporary.rglob("*.png"))
            assert len(masks) == 1, ("EXPECTED_ONE_MASK", masks)
            mask = output / "masks" / (stem + ".png")
            masks[0].rename(mask)
            assert pose_hash() == pose, "POSE_CHANGED_DURING_RENDER"
            entry = dict(
                camera_index=index,
                sample_index=sample,
                source_frame=source_frame(sample),
                source_time_s=(source_frame(sample) - 1) / 120,
                time=sample / 30,
                group=group(index, sample),
                image=str(image.relative_to(output)),
                mask=str(mask.relative_to(output)),
                image_sha256=sha(image),
                mask_sha256=sha(mask),
                pose_sha256=pose,
                athlete_roi=roi(scene, cam, bounds),
                reprojection_max_error_px=error,
                reprojection_points=points,
                seconds=execution["seconds"],
                **meta,
            )
            with (output / "records.jsonl").open("a") as stream:
                stream.write(json.dumps(entry, allow_nan=False) + "\n")
            records.append(entry)
            print("CAPTURE_PROGRESS", len(records), 2 if smoke else 496, flush=True)
    assert environment() == before, "ENVIRONMENT_CHANGED"
    assert sha(source) == SOURCE_SHA256, "SOURCE_CHANGED"
    counts = {"smoke": len(records)} if smoke else validate_records(records)
    write_json(
        output / "capture-result.json",
        dict(
            status="SMOKE_RENDERED" if smoke else "CAPTURED_REQUIRES_HOST_VERIFICATION",
            counts=counts,
            source_sha256=sha(source),
            seconds=time.monotonic() - started,
            reused_images=len(reused),
            new_images=len(records) - len(reused),
            blender=bpy.app.version_string,
            limits="Object-index matte with antialiasing; not calibrated motion/physics",
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.resume_from and not args.resume_from.resolve().is_relative_to(ROOT / "outputs"):
        parser.error("Recovery input must stay inside outputs/")
    capture(
        args.plan.resolve(),
        args.output.resolve(),
        args.smoke,
        args.resume_from.resolve() if args.resume_from else None,
    )
