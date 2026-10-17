"""P2 records and invariants; imports no historical generator."""

import array
import hashlib
import json
from pathlib import Path
import struct
import time

import bpy

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def environment_signature():
    result = {}
    for o in sorted(bpy.data.collections["P1_Snowpark"].all_objects, key=lambda x: x.name):
        h = hashlib.sha256()
        if o.type == "MESH":
            v = array.array("f", [0]) * (3 * len(o.data.vertices))
            o.data.vertices.foreach_get("co", v)
            h.update(v.tobytes())
            for p in o.data.polygons:
                h.update(struct.pack("<" + "I" * len(p.vertices), *p.vertices))
        elif o.type == "CURVE":
            for spline in o.data.splines:
                for p in spline.points:
                    h.update(struct.pack("<4f", *p.co))
            h.update(str((o.data.bevel_depth, o.data.bevel_resolution)).encode())
        result[o.name] = dict(
            type=o.type,
            geometry_sha256=h.hexdigest(),
            matrix=[list(r) for r in o.matrix_world],
            modifiers=[
                dict(
                    type=m.type,
                    **(
                        {k: getattr(m, k) for k in ["width", "segments"]}
                        if m.type == "BEVEL"
                        else {k: getattr(m, k) for k in ["thickness", "offset"]}
                        if m.type == "SOLIDIFY"
                        else {}
                    ),
                )
                for m in o.modifiers
            ],
        )
    return result


def render_contract(scene):
    c = scene.camera
    return dict(
        camera=c.name,
        matrix=[list(r) for r in c.matrix_world],
        lens=c.data.lens,
        sensor_width=c.data.sensor_width,
        resolution=[
            scene.render.resolution_x,
            scene.render.resolution_y,
            scene.render.resolution_percentage,
        ],
        engine=scene.render.engine,
        device=scene.cycles.device,
        samples=scene.cycles.samples,
        seed=scene.cycles.seed,
        denoising=scene.cycles.use_denoising,
        adaptive=scene.cycles.use_adaptive_sampling,
        threads=scene.render.threads,
        view_transform=scene.view_settings.view_transform,
        exposure=scene.view_settings.exposure,
        gamma=scene.view_settings.gamma,
        frame=scene.frame_current,
        lights={
            o.name: dict(
                type=o.data.type,
                energy=o.data.energy,
                color=list(o.data.color),
                angle=o.data.angle,
                matrix=[list(r) for r in o.matrix_world],
            )
            for o in scene.objects
            if o.type == "LIGHT"
        },
        world_color=list(scene.world.node_tree.nodes["Background"].inputs[0].default_value),
        world_strength=scene.world.node_tree.nodes["Background"].inputs[1].default_value,
    )


def render(scene, path):
    assert not path.exists(), "RENDER_OVERWRITE_FORBIDDEN"
    scene.render.filepath = str(path)
    tick = time.monotonic()
    bpy.ops.render.render(write_still=True)
    assert path.is_file()
    return dict(
        file=path.name,
        seconds=time.monotonic() - tick,
        bytes=path.stat().st_size,
        sha256=sha(path),
        contract=render_contract(scene),
    )
