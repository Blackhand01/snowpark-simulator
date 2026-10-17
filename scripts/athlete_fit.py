"""Reuse the tested FK rig; fit it to the measured slope and add simple loose garments."""

import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from athlete_proxy import build as build_proxy
from terrain_profile import grade
from terrain_geometry import mesh


def build(scene, c, profile):
    rig, meta = build_proxy(scene, c["athlete"])
    if c["athlete"]["freestyle_clothes"]:
        clothes(rig)
    x, y = c["athlete"]["position_xy_m"]
    rig.rotation_euler.x = math.atan(grade(y, profile))
    rig.location = (x, y, 1)
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(scene.objects["Snow_terrain"], deps)
    gaps = []
    for name in ["ATH_Ski_L", "ATH_Ski_R"]:
        o = scene.objects[name].evaluated_get(deps)
        data = o.to_mesh()
        for v in data.vertices:
            p = o.matrix_world @ v.co
            hit, *_ = tree.ray_cast(Vector((p.x, p.y, 20)), Vector((0, 0, -1)), 100)
            assert hit is not None
            gaps.append(p.z - hit.z)
        o.to_mesh_clear()
    rig.location.z += c["athlete"]["ground_clearance_m"] - min(gaps)
    rig["placement"] = "Rigid ski plane aligned to local grade; fitted to evaluated terrain"
    scene["milestone"] = "REFINED_STATIC_WITH_ATHLETE"
    bpy.context.view_layer.update()
    meta.update(
        rig_location=list(rig.location),
        slope_angle_degrees=math.degrees(rig.rotation_euler.x),
        wardrobe="Approximate dark freestyle shirt and loose trousers; no cloth physics",
    )
    return rig, meta


def clothes(rig):
    body = bpy.data.collections["ATH_Body"]
    scene = bpy.context.scene
    dark = bpy.data.materials["ATH_Navy_pants"]
    dark.diffuse_color = (0.022, 0.025, 0.032, 1)
    dark.node_tree.nodes.get("Principled BSDF").inputs[
        "Base Color"
    ].default_value = dark.diffuse_color
    for name in ["ATH_Orange_jacket", "ATH_Helmet_shell"]:
        m = bpy.data.materials[name]
        m.diffuse_color = (0.028, 0.031, 0.038, 1)
        m.node_tree.nodes.get("Principled BSDF").inputs[
            "Base Color"
        ].default_value = m.diffuse_color
    m = bpy.data.materials["ATH_Goggle_lens"]
    m.diffuse_color = (0.52, 0.20, 0.025, 1)
    m.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = m.diffuse_color
    for name in ["ATH_Jacket", "ATH_Pelvis", "ATH_Backpack"] + [
        f"ATH_{p}_{side}" for p in ["thigh", "shin", "Knee"] for side in ["L", "R"]
    ]:
        o = bpy.data.objects[name]
        o.hide_render = True
        o.hide_viewport = True
    gloves = bpy.data.materials["ATH_Rubber_gloves"].copy()
    gloves.name = "REF_Light_gloves"
    gloves.diffuse_color = (0.5, 0.51, 0.48, 1)
    gloves.node_tree.nodes.get("Principled BSDF").inputs[
        "Base Color"
    ].default_value = gloves.diffuse_color
    for side in ["L", "R"]:
        bpy.data.objects["ATH_Glove_" + side].data.materials[0] = gloves

    def garment(name, rings, side=None):
        n = 32
        vertices = []
        for z, cx, rx, ry in rings:
            for i in range(n):
                a = 2 * math.pi * i / n
                folds = 1 + 0.022 * math.sin(6 * a + z * 12) + 0.012 * math.cos(9 * a - z * 7)
                vertices.append((cx + rx * math.cos(a) * folds, ry * math.sin(a) * folds, z))
        faces = [
            tuple(reversed(range(n))),
            tuple(range((len(rings) - 1) * n, len(rings) * n)),
        ]
        faces += [
            (j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
            for j in range(len(rings) - 1)
            for i in range(n)
        ]
        o = mesh(name, vertices, faces, body, dark, True)
        o.parent = rig
        if side:
            upper = o.vertex_groups.new(name="thigh." + side)
            lower = o.vertex_groups.new(name="shin." + side)
            for v in o.data.vertices:
                w = max(0, min(1, (v.co.z - 0.43) / 0.22))
                if w:
                    upper.add([v.index], w, "REPLACE")
                if w < 1:
                    lower.add([v.index], 1 - w, "REPLACE")
        else:
            g = o.vertex_groups.new(name="chest")
            g.add(list(range(len(o.data.vertices))), 1, "REPLACE")
        mod = o.modifiers.new("ATH_Clothing_skin", "ARMATURE")
        mod.object = rig
        return o

    for side, sign in [("L", 1), ("R", -1)]:
        garment(
            "ATH_Loose_pants_" + side,
            [
                (0.19, sign * 0.19, 0.125, 0.13),
                (0.30, sign * 0.19, 0.16, 0.16),
                (0.50, sign * 0.18, 0.17, 0.17),
                (0.67, sign * 0.17, 0.17, 0.17),
                (0.85, sign * 0.15, 0.17, 0.16),
                (0.99, sign * 0.14, 0.155, 0.14),
            ],
            side,
        )
    garment(
        "ATH_Long_shirt",
        [
            (0.98, 0, 0.235, 0.155),
            (1.08, 0, 0.245, 0.155),
            (1.27, 0, 0.255, 0.16),
            (1.40, 0, 0.235, 0.15),
            (1.48, 0, 0.09, 0.09),
        ],
    )
