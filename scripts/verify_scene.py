"""Independent reopened-file checks. Does not build, render or save the scene."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import bmesh
import bpy
from mathutils import Vector


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    scene=bpy.context.scene
    checks={}

    def check(name, condition, detail=None):
        checks[name]=dict(passed=bool(condition),detail=detail)
        if not condition:
            raise AssertionError(name+": "+str(detail))

    check("reopened_correct_scene",scene.name=="P1_Static_Snowpark" and scene.get("milestone")=="P1_STATIC_ONLY")
    check("no_reference_image_in_scene",not any(o.type=="EMPTY" and o.empty_display_type=="IMAGE" for o in scene.objects)
          and not any(n.type=="TEX_IMAGE" for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes))
    check("no_athlete_or_armature",not any(o.type=="ARMATURE" for o in bpy.data.objects)
          and not any("athlete" in o.name.lower() for o in scene.objects))
    animated=[o.name for o in bpy.data.objects if o.animation_data and (o.animation_data.action or o.animation_data.drivers)]
    check("no_object_animation_or_drivers",not animated,animated)
    check("single_frame",scene.frame_start==scene.frame_end==1)
    check("preview_cameras",len([o for o in scene.objects if o.type=="CAMERA"])==4)
    check("real_mesh_terrain",scene.objects["Snow_terrain"].type=="MESH")
    ground=scene.objects["Snow_terrain"]
    heights=[v.co.z for v in ground.data.vertices]
    check("terrain_has_height_relief",max(heights)-min(heights)>1,dict(min=min(heights),max=max(heights)))
    check("terrain_has_thickness",any(m.type=="SOLIDIFY" and m.thickness>0 for m in ground.modifiers))
    check("finite_mesh_coordinates",all(math.isfinite(x) for o in scene.objects if o.type=="MESH" for v in o.data.vertices for x in v.co))
    for name in ["Rail_tube","Rail_end_front","Rail_end_back"]:
        obj=scene.objects[name]
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        boundary=sum(not e.is_manifold for e in bm.edges)
        volume=abs(bm.calc_volume(signed=True))
        bm.free()
        check(name+"_closed_manifold",boundary==0,dict(nonmanifold_edges=boundary,volume_m3=volume))
        check(name+"_positive_volume",volume>0.001)
    check("mountains_surround_scene",scene.objects["Alpine_background_360"].dimensions.x>200)
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    probes={"right":((4,0,.65),(-1,0,0)),"left":((-4,0,.65),(1,0,0)),
            "front":((0,-8,.65),(0,1,0)),"back":((0,8,.65),(0,-1,0)),
            "above":((0,0,5),(0,0,-1))}
    for label,(origin,direction) in probes.items():
        hit,point,normal,index,obj,matrix=scene.ray_cast(deps,Vector(origin),Vector(direction),distance=20)
        check("rail_accessible_"+label,hit and obj.name.startswith("Rail_"),dict(hit=hit,object=obj.name if obj else None,point=list(point)))
    # Evaluated object positions are also compared at another frame: static in actual runtime.
    before={o.name:tuple(v for row in o.matrix_world for v in row) for o in scene.objects}
    scene.frame_set(17)
    after={o.name:tuple(v for row in o.matrix_world for v in row) for o in scene.objects}
    check("transforms_static_across_frames",before==after)
    scene.frame_set(1)
    for filename in ["main.png","side.png","opposite.png","high.png"]:
        p=args.output/filename
        img=bpy.data.images.load(str(p),check_existing=False)
        check("render_exists_"+filename,tuple(img.size)==(scene.render.resolution_x,scene.render.resolution_y),list(img.size))
        bpy.data.images.remove(img)
    result=dict(status="PASS",checks=checks,blender=bpy.app.version_string,build=bpy.app.build_hash.decode(),
                blend_sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
                reopened_filepath=bpy.data.filepath,scene_saved_by_verifier=False,
                scope="Reopened-file geometry and real raycast checks; GUI orbit is recorded separately.")
    (args.output/"verification.json").write_text(json.dumps(result,indent=2)+"\n")
    print("P1_VERIFY_PASS",len(checks))


if __name__=="__main__":main()
