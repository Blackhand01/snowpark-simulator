"""Reopened P2 invariants and actual FK deformation tests; no keyframes or saves."""
import argparse,json,math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from p2_support import ROOT,sha,write,environment_signature
import bpy
from mathutils import Vector


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve()
    checks={}
    def check(name,value,detail=None):
        checks[name]=dict(passed=bool(value),detail=detail)
        assert value,(name,detail)
    s=bpy.context.scene;rig=s.objects['Athlete_Rig']
    check('reopened_p2',s.get('milestone')=='P2_STATIC_RIGGED_PROXY')
    check('p1_environment_geometry_and_transforms_unchanged',environment_signature()==json.loads((out/'environment-before.json').read_text()))
    preserved=json.loads((out/'p1-preservation-before.json').read_text())
    changed=[f for f,h in preserved.items() if sha(ROOT/f)!=h]
    check('all_p1_artifacts_unchanged',not changed,changed)
    check('single_armature',sum(o.type=='ARMATURE' for o in s.objects)==1)
    check('standard_named_bones',all(n in rig.data.bones for n in ['root','pelvis','spine','chest','head','thigh.L','shin.L','foot.L','upper_arm.R','forearm.R','hand.R']),len(rig.data.bones))
    check('separate_equipment_collections',all('ATH_'+n in bpy.data.collections for n in ['Skis','Boots','Bindings','Helmet','Goggles','Poles','Backpack']))
    check('two_skis',len(bpy.data.collections['ATH_Skis'].objects)==2)
    check('two_boots',len(bpy.data.collections['ATH_Boots'].objects)==2)
    bound=list(o for o in bpy.data.collections['P2_Athlete'].all_objects if o.type=='MESH')
    check('every_proxy_part_has_rig_weights',all(o.vertex_groups and all(v.groups and abs(sum(g.weight for g in v.groups)-1)<1e-6 for v in o.data.vertices) and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers) for o in bound),len(bound))
    check('no_actions_or_object_drivers',not bpy.data.actions and not any(o.animation_data and (o.animation_data.action or o.animation_data.drivers) for o in bpy.data.objects))
    check('single_static_frame',s.frame_start==s.frame_end==1)
    check('no_nonfinite_coordinates',all(math.isfinite(x) for o in bound for v in o.data.vertices for x in v.co))
    def points(name):
        bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
        o=s.objects[name].evaluated_get(deps);mesh=o.to_mesh()
        values=[o.matrix_world@v.co for v in mesh.vertices];o.to_mesh_clear();return values
    # Exercise real skinned mesh motion, then restore every pose without creating an action.
    for bone,part in [('forearm.L','ATH_Glove_L'),('thigh.R','ATH_Ski_R'),('head','ATH_Helmet')]:
        before=points(part);pb=rig.pose.bones[bone];saved=pb.matrix_basis.copy()
        pb.rotation_mode='XYZ';pb.rotation_euler.x=.25
        after=points(part);distance=max((a-b).length for a,b in zip(before,after))
        check('fk_moves_'+part,distance>.01,dict(max_vertex_movement_m=distance,bone=bone))
        pb.matrix_basis=saved;restored=points(part)
        check('pose_restored_'+part,max((a-b).length for a,b in zip(before,restored))<1e-5)
    # The skier and skis must remain visibly beside the rail instead of intersecting it.
    for side in ['L','R']:
        ski=points('ATH_Ski_'+side)
        check('ski_clear_of_rail_'+side,max(p.x for p in ski)<-.7)
    # Contact checks use only the evaluated terrain BVH, excluding the athlete itself.
    from mathutils.bvhtree import BVHTree
    terrain=s.objects['Snow_terrain'];deps=bpy.context.evaluated_depsgraph_get()
    tree=BVHTree.FromObject(terrain,deps)
    contact=[]
    for side in ['L','R']:
        for pnt in points('ATH_Ski_'+side)[::8]:
            hit,normal,index,distance=tree.ray_cast(Vector((pnt.x,pnt.y,10)),Vector((0,0,-1)),30)
            if hit:contact.append(pnt.z-hit.z)
    check('skis_do_not_penetrate_snow',contact and min(contact)>-.005,dict(min_clearance_m=min(contact),max_sampled_clearance_m=max(contact)))
    check('no_dense_displacement_added',all(m.type not in ['SUBSURF','DISPLACE'] for m in terrain.modifiers))
    selected=json.loads((out/'snow-decision.json').read_text())['selected']
    if selected=='baseline':check('baseline_snow_retained',[x.material.name for x in terrain.material_slots]==['Snow_groomed','Snow_loose'])
    else:check('pbr_textures_packed',all(n.image.packed_file for m in terrain.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE'))
    for filename in ['athlete-main.png','athlete-detail.png']:
        img=bpy.data.images.load(str(out/filename),check_existing=False)
        check('preview_'+filename,tuple(img.size)==(1280,960));bpy.data.images.remove(img)
    write(out/'p2-verification.json',dict(status='PASS',checks=checks,blender=bpy.app.version_string,build=bpy.app.build_hash.decode(),
           blend_sha256=sha(bpy.data.filepath),pose_tests_in_memory_only=True,scene_saved_by_verifier=False,
           limitations='FK articulated proxy, no IK/soft skin/trick/physics validation. No direct GUI interaction claimed for this new artifact.'))
    print('P2_VERIFY_PASS',len(checks))


if __name__=='__main__':main()
