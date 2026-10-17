"""Procedural static snowpark with configurable materials and cameras.

No imports from historical generators, no factory reset, no third-party assets.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
import tomllib

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def material(name, color, metallic=0.0, roughness=0.7):
    # Shared local material helper pattern.
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Roughness"].default_value = roughness
    return m


def noise_bump(m, scale, strength, distance):
    n, links = m.node_tree.nodes, m.node_tree.links
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 3
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    links.new(tex.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], n.get("Principled BSDF").inputs["Normal"])
    return bump


def snow_material(name, c, groomed=False):
    m = material(name, (0.90, 0.94, 0.98), roughness=0.78)
    p = m.node_tree.nodes.get("Principled BSDF")
    p.inputs["Subsurface Weight"].default_value = 0.035
    fine = noise_bump(m, 210, 0.32, 0.009)
    if groomed:
        n, links = m.node_tree.nodes, m.node_tree.links
        coord = n.new("ShaderNodeTexCoord")
        sep = n.new("ShaderNodeSeparateXYZ")
        mul = n.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 2 * math.pi / c["terrain"]["groom_spacing_m"]
        wave = n.new("ShaderNodeMath")
        wave.operation = "SINE"
        bump = n.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.75
        bump.inputs["Distance"].default_value = c["terrain"]["groom_relief_m"]
        links.new(coord.outputs["Object"], sep.inputs[0])
        links.new(sep.outputs["X"], mul.inputs[0])
        links.new(mul.outputs[0], wave.inputs[0])
        links.new(wave.outputs[0], bump.inputs["Height"])
        links.new(fine.outputs[0], bump.inputs["Normal"])
        links.new(bump.outputs[0], p.inputs["Normal"])
    return m


def mesh_object(name, vertices, faces, collection, mat):
    data = bpy.data.meshes.new(name + "_mesh")
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def ground_z(x, y, c):
    t = c["terrain"]
    bank = t["bank_height_m"] * (1 + math.tanh((y - t["bank_y_m"]) / t["bank_transition_m"])) / 2
    # The lip is broad on the left and fades to a passage on the right.
    bank *= 0.18 + 0.82 / (1 + math.exp(min(50, (x - 1.8) / 1.5)))
    relief = 0.035 * math.sin(x * 1.7 + y * 0.6) * math.sin(y * 1.3)
    track = -.025 * math.exp(-((x - .32*y - 3.0)/.11)**2) * math.exp(-((y+5)/9)**4)
    berm = t["berm_height_m"] * math.exp(-((abs(x) - 0.74) / 0.32) ** 2) * math.exp(-(y / 4.8) ** 8)
    return t["slope_y"] * y + bank + relief + berm + track


def terrain(collection, c, groomed, rough):
    t = c["terrain"]
    nx, ny = round(t["width_m"] / t["grid_step_m"]), round(t["depth_m"] / t["grid_step_m"])
    vertices = []
    for j in range(ny + 1):
        y = -t["depth_m"] / 2 + j * t["depth_m"] / ny
        for i in range(nx + 1):
            x = -t["width_m"] / 2 + i * t["width_m"] / nx
            vertices.append((x, y, ground_z(x, y, c)))
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1,
              (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(ny) for i in range(nx)]
    obj = mesh_object("Snow_terrain", vertices, faces, collection, groomed)
    obj.data.materials.append(rough)
    for face in obj.data.polygons:
        x, y, _ = face.center
        face.material_index = int(abs(x) > 15 or y > 17 or (abs(x) < 1.1 and abs(y) < 4.5))
        face.use_smooth = True
    solid = obj.modifiers.new("Terrain_volume", "SOLIDIFY")
    solid.thickness = 0.6
    obj["role"] = "real_3d_terrain_with_volume"
    return obj


def rail(collection, c, steel, cap, scratch):
    r = c["rail"]
    n, radius, length = r["radial_segments"], r["radius_m"], r["length_m"]
    z = r["center_height_m"]
    # Separate inner/outer rings make the tube wall real geometry, including its ends.
    vertices = []
    for y in [-length / 2, length / 2]:
        for rad in [radius, radius - r["wall_thickness_m"]]:
            vertices.extend((rad * math.cos(2 * math.pi * i / n), y,
                             z + rad * math.sin(2 * math.pi * i / n) + c["terrain"]["slope_y"] * y)
                            for i in range(n))
    faces = []
    for i in range(n):
        k = (i + 1) % n
        faces.extend([(i, 2*n+i, 2*n+k, k), (n+i, n+k, 3*n+k, 3*n+i),
                      (i, k, n+k, n+i), (2*n+i, 3*n+i, 3*n+k, 2*n+k)])
    obj = mesh_object("Rail_tube", vertices, faces, collection, steel)
    for face in obj.data.polygons:
        face.use_smooth = face.index % 4 < 2
    bevel = obj.modifiers.new("Rounded_tube_rim", "BEVEL")
    bevel.width, bevel.segments = 0.008, 3
    obj["role"] = "closed_volume_tube_wall"
    for label, y in [("front", -length / 2 + 0.012), ("back", length / 2 - 0.012)]:
        # Closed disk with thickness, visibly recessed inside the outer metal rim.
        points = []
        rr = radius - r["wall_thickness_m"]
        for yy in [y - 0.012, y + 0.012]:
            points.extend((rr*math.cos(2*math.pi*i/n), yy,
                           z + rr*math.sin(2*math.pi*i/n) + c["terrain"]["slope_y"]*yy) for i in range(n))
        fs = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
        fs += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
        mesh_object("Rail_end_" + label, points, fs, collection, cap)
    rng = random.Random(c["scene"]["seed"])
    for i in range(r["scratch_count"]):
        theta = rng.uniform(0.12, math.pi - 0.12)
        y = rng.uniform(-length/2 + .10, length/2 - .25)
        delta = rng.uniform(.06, .40)
        curve = bpy.data.curves.new(f"Scratch_{i:03}", "CURVE")
        curve.dimensions, curve.bevel_depth, curve.bevel_resolution = "3D", rng.uniform(.0007, .0018), 0
        spline = curve.splines.new("POLY")
        spline.points.add(2)
        for j, point in enumerate(spline.points):
            yy = y + delta * j/2
            angle = theta + .025 * math.sin(j * 1.7 + i)
            point.co = ((radius+.0015)*math.cos(angle), yy,
                        z+(radius+.0015)*math.sin(angle)+c["terrain"]["slope_y"]*yy, 1)
        o = bpy.data.objects.new(f"Rail_scratch_{i:03}", curve)
        collection.objects.link(o)
        curve.materials.append(scratch)
    return obj


def mountains(collection, c, snow, rock):
    m = c["mountains"]
    rng = random.Random(c["scene"]["seed"] + 1)
    peaks = [(2*math.pi*i/m["peaks"] + rng.uniform(-.09,.09), rng.uniform(m["height_min_m"], m["height_max_m"]))
             for i in range(m["peaks"])]
    vertices = []
    na, nr = m["angular_segments"], m["radial_segments"]
    for j in range(nr + 1):
        frac = j / nr
        rad = 34 + frac * (m["radius_m"] + 65 - 34)
        envelope = math.sin(math.pi * frac) ** 1.3
        for i in range(na):
            a = 2*math.pi*i/na
            height = max(h * math.exp(-(math.atan2(math.sin(a-p), math.cos(a-p))/.27)**2) for p,h in peaks)
            ridge = 1 + .07*math.sin(a*49 + frac*13) + .04*math.cos(a*83-frac*31)
            vertices.append((rad*math.cos(a), rad*math.sin(a), -.8 + envelope * height * ridge))
    faces = []
    for j in range(nr):
        for i in range(na):
            a,b = j*na+i, j*na+(i+1)%na
            faces.extend([(a,b,b+na), (a,b+na,a+na)])
    obj = mesh_object("Alpine_background_360", vertices, faces, collection, snow)
    obj.data.materials.append(rock)
    for face in obj.data.polygons:
        face.material_index = int(face.normal.z < .44 and face.center.z > 5)
        face.use_smooth = True


def snow_clumps(collection, c, snow):
    rng = random.Random(c["scene"]["seed"] + 2)
    for i in range(115):
        y = rng.uniform(-4.3,4.3)
        x = rng.choice([-1,1]) * rng.uniform(.48,1.1)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1,
            location=(x,y,ground_z(x,y,c)+rng.uniform(.015,.045)))
        obj = bpy.context.object
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        collection.objects.link(obj)
        obj.name = f"Snow_clump_{i:03}"
        obj.scale = (rng.uniform(.025,.10),rng.uniform(.04,.15),rng.uniform(.025,.065))
        obj.data.materials.append(snow)


def camera(name, position, target, lens, collection):
    # Adapted from visual-hd-preview-r1/scene.py:83-84; only four preview views.
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()
    data.lens, data.sensor_width, data.clip_start, data.clip_end = lens, 36, .05, 500
    return obj


def build(c, *, without_reference=False):
    s = bpy.data.scenes.new("P1_Static_Snowpark")
    bpy.context.window.scene = s
    name = c["scene"]["collection"]
    collection = bpy.data.collections.new(name)
    s.collection.children.link(collection)
    s.unit_settings.system, s.unit_settings.scale_length = "METRIC", 1
    snow = snow_material("Snow_loose", c)
    groomed = snow_material("Snow_groomed", c, True)
    steel = material("Worn_galvanized_steel", (.34,.39,.43), c["rail"]["metallic"], c["rail"]["roughness"])
    noise_bump(steel, 95, .2, .0015)
    cap = material("Dark_steel_endcaps", (.055,.066,.078), .72, .5)
    noise_bump(cap, 65, .22, .002)
    scratch = material("Exposed_metal_scratches", (.65,.69,.72), .85, .42)
    rock = material("Alpine_rock", (.19,.23,.28), roughness=.93)
    noise_bump(rock, 5, .45, .15)
    terrain(collection,c,groomed,snow)
    rail(collection,c,steel,cap,scratch)
    mountains(collection,c,snow,rock)
    snow_clumps(collection,c,snow)
    for i,(x,y,col) in enumerate([(5,9,(.85,.065,.025)),(4,11,(.65,.8,.03)),(-9,15,(.85,.065,.025))]):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=.023,depth=1.4,location=(x,y,ground_z(x,y,c)+.65))
        o=bpy.context.object
        for old in list(o.users_collection):old.objects.unlink(o)
        collection.objects.link(o)
        o.name=f"Marker_{i}"
        o.data.materials.append(material(f"Marker_color_{i}",col,roughness=.5))
    world = bpy.data.worlds.new("Winter_daylight")
    world.use_nodes=True
    world.node_tree.nodes["Background"].inputs[0].default_value=(.48,.64,.88,1)
    world.node_tree.nodes["Background"].inputs[1].default_value=c["lighting"]["world_strength"]
    s.world=world
    light=bpy.data.lights.new("Winter_sun","SUN")
    light.energy=c["lighting"]["sun_energy"]
    light.angle=math.radians(c["lighting"]["sun_angle_degrees"])
    o=bpy.data.objects.new("Winter_sun",light)
    collection.objects.link(o)
    o.rotation_euler=tuple(math.radians(x) for x in c["lighting"]["sun_rotation_degrees"])
    p=c["preview"]
    cameras=[camera("Preview_main",p["main_position"],p["main_target"],p["main_lens_mm"],collection),
             camera("Preview_side",(12,-1,4),(0,0,.4),p["inspection_lens_mm"],collection),
             camera("Preview_opposite",(-8,11,5),(0,0,.6),p["inspection_lens_mm"],collection),
             camera("Preview_high",(7,-8,13),(0,1,0),p["inspection_lens_mm"],collection)]
    s.camera=cameras[0]
    r=c["render"]
    s.render.engine=r["engine"]
    s.cycles.device=r["device"]
    s.cycles.samples=r["samples"]
    s.cycles.seed=c["scene"]["seed"]
    s.cycles.use_denoising=r["denoising"]
    s.render.threads_mode="FIXED"
    s.render.threads=r["threads"]
    s.render.resolution_x=r["width"]
    s.render.resolution_y=r["height"]
    s.render.resolution_percentage=100
    s.render.image_settings.file_format="PNG"
    s.render.image_settings.color_mode="RGB"
    s.view_settings.view_transform=r["view_transform"]
    s.view_settings.exposure=r["exposure"]
    s.render.use_motion_blur=False
    s.frame_start=s.frame_end=1
    s["milestone"]="P1_STATIC_ONLY"
    s["reference"]="" if without_reference else "references/snowpark-rail.png (visual reference only; not loaded as texture)"
    s["reference_sha256"]="" if without_reference else sha(ROOT/"references/snowpark-rail.png")
    s["config_json"]=json.dumps(c,sort_keys=True)
    # New scene owns only generated objects. Existing user/startup scenes are not reset.
    for obj in s.objects:obj.select_set(False)
    s.objects["Rail_tube"].select_set(True)
    bpy.context.view_layer.objects.active=s.objects["Rail_tube"]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                v=area.spaces.active
                v.shading.type="SOLID"
                v.shading.color_type="MATERIAL"
                v.clip_end=500
                v.region_3d.view_location=(0,0,.4)
                v.region_3d.view_distance=12
                v.region_3d.view_rotation=cameras[0].rotation_euler.to_quaternion()
                v.region_3d.view_perspective="PERSP"
                v.overlay.show_extras=False
    return s,cameras


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--without-reference", action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    out=args.output.resolve()
    assert out.is_relative_to(ROOT/"outputs") and out.is_dir(), "OUTPUT_SCOPE"
    assert not (out/"snowpark.blend").exists(), "NO_OVERWRITE"
    c=tomllib.loads(args.config.read_text())
    start=time.monotonic()
    scene,cameras=build(c, without_reference=args.without_reference)
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"snowpark.blend"))
    meta=dict(blender=bpy.app.version_string,build=bpy.app.build_hash.decode(),python=sys.version,
              config=c,config_sha256=sha(args.config),reference_sha256=scene["reference_sha256"],
              objects=len(scene.objects),meshes=sum(o.type=="MESH" for o in scene.objects),
              vertices=sum(len(o.data.vertices) for o in scene.objects if o.type=="MESH"),renders=[])
    json_write(out/"build-report.json",meta)
    for cam in cameras:
        scene.camera=cam
        path=out/(cam.name.removeprefix("Preview_")+".png")
        scene.render.filepath=str(path)
        tick=time.monotonic()
        bpy.ops.render.render(write_still=True)
        meta["renders"].append(dict(camera=cam.name,file=path.name,seconds=time.monotonic()-tick,sha256=sha(path)))
        meta["elapsed_seconds"]=time.monotonic()-start
        json_write(out/"build-report.json",meta)
    print("P1_BUILD_COMPLETE",json.dumps(meta["renders"]))


if __name__=="__main__":
    main()
