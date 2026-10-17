"""Versioned athlete-only appearance refinement, comparison and independent checks."""
import argparse,json,sys,tomllib,math,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from athlete_look import Tailor
from build_scene import camera
from p2_support import ROOT,sha,write,render,render_contract
from refine_geometry import stable_fingerprint


def appearance_signature():
    data={}
    for n,e in stable_fingerprint(bpy.context.scene).items():
        if n.startswith('LOOK_'):data[n]=e
    return data


def existing_signature():
    names={o.name for o in bpy.data.collections['REF_Environment'].all_objects}|{'Athlete_Rig','ATH_Ski_L','ATH_Ski_R'}
    return {k:v for k,v in stable_fingerprint(bpy.context.scene).items() if k in names}


def cameras(scene):
    c=bpy.data.collections.new('LOOK_Review_Cameras');scene.collection.children.link(c)
    rig=scene.objects['Athlete_Rig']
    def world(xyz):return tuple(rig.matrix_world@Vector(xyz))
    result={}
    for name,pos,target,lens in [
        ('Portrait',(-2.0,-3.7,1.7),(0,-.04,.93),65),
        ('Back',(2.1,3.45,1.8),(0,.02,.93),65),
        ('Face',(-.43,-1.16,1.84),(0,-.03,1.635),76),
        ('Equipment',(-.75,-1.3,.58),(0,-.025,.18),62)]:
        result[name]=camera('LOOK_Camera_'+name,world(pos),world(target),lens,c)
    return result


def setup(scene,size,samples,c):
    scene.render.resolution_x=size[0];scene.render.resolution_y=size[1];scene.render.resolution_percentage=100
    scene.cycles.samples=samples;scene.cycles.seed=c['seed'];scene.render.threads=c['threads']


def points(name):
    bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    o=bpy.context.scene.objects[name].evaluated_get(deps);mesh=o.to_mesh()
    result=[o.matrix_world@v.co for v in mesh.vertices];o.to_mesh_clear();return result


def verify(out,c,geometry_only=False):
    scene=bpy.context.scene;checks={}
    report_path=out/('geometry-verification.json' if geometry_only else 'verification.json')
    def check(name,yes,detail=None):
        checks[name]=dict(passed=bool(yes),detail=detail)
        write(report_path,dict(status='RUNNING',checks=checks))
        assert yes,(name,detail)
    check('reopened_correct_scene',scene.get('appearance_stage')=='TAILORED_STATIC_ATHLETE')
    check('environment_rig_and_ski_preserved',existing_signature()==json.loads((out/'preserved-scene-signature.json').read_text()))
    check('saved_appearance_geometry_matches',appearance_signature()==json.loads((out/'appearance-signature.json').read_text()))
    rig=scene.objects['Athlete_Rig'];check('existing_22_bones',len(rig.data.bones)==22)
    keep={'ATH_Ski_L','ATH_Ski_R','ATH_Pole_L','ATH_Pole_R','ATH_Pole_basket_L','ATH_Pole_basket_R'}
    check('legacy_parts_fully_hidden',all(o.hide_render and o.hide_viewport for o in bpy.data.collections['P2_Athlete'].all_objects
                                        if o.type=='MESH' and not o.name.startswith('LOOK_') and o.name not in keep))
    cloth=scene.objects['LOOK_Continuous_pants'];bm=bmesh.new();bm.from_mesh(cloth.data)
    islands=0;seen=set()
    for v in bm.verts:
        if v in seen:continue
        islands+=1;queue=[v];seen.add(v)
        while queue:
            node=queue.pop()
            for edge in node.link_edges:
                other=edge.other_vert(node)
                if other not in seen:seen.add(other);queue.append(other)
    detail=dict(connected_components=islands,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),vertices=len(bm.verts))
    bm.free();check('pants_one_continuous_closed_mesh',islands==1 and detail['nonmanifold_edges']==0,detail)
    look=list(bpy.data.collections['LOOK_Tailored_Athlete'].all_objects)
    check('no_cloth_or_particle_simulation',all(m.type not in ['CLOTH','FLUID','SOFT_BODY','PARTICLE_SYSTEM'] for o in look for m in o.modifiers))
    check('all_appearance_parts_bound_to_existing_rig',all(any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers) for o in look))
    check('finite_vertices_and_normalised_weights',all(math.isfinite(x) for o in look for v in o.data.vertices for x in v.co) and
          all(abs(sum(g.weight for g in v.groups)-1)<1e-5 for o in look for v in o.data.vertices))
    deps=bpy.context.evaluated_depsgraph_get();tree=BVHTree.FromObject(scene.objects['Snow_terrain'],deps)
    gaps=[]
    for name in ['ATH_Ski_L','ATH_Ski_R']:
        for pnt in points(name):
            hit,*_=tree.ray_cast(Vector((pnt.x,pnt.y,20)),Vector((0,0,-1)),100);assert hit
            gaps.append(pnt.z-hit.z)
    check('ski_ground_contact_preserved',.003<min(gaps)<.012,dict(min_gap_m=min(gaps),max_gap_m=max(gaps)))
    check('athlete_clear_of_rail',max(p.x for o in look for p in points(o.name))<-.51)
    for part,bone in [('LOOK_Continuous_pants','thigh.L'),('LOOK_Compression_sleeve_L','forearm.L'),
                      ('LOOK_Leather_glove_L','forearm.L'),('LOOK_Boot_shell_R','foot.R'),('LOOK_Panoramic_visor','head')]:
        initial=points(part);b=rig.pose.bones[bone];matrix=b.matrix_basis.copy();mode=b.rotation_mode
        b.rotation_mode='XYZ';b.rotation_euler.x=.15
        posed=points(part);motion=max((x-y).length for x,y in zip(initial,posed))
        check('fk_'+part,motion>.001,motion);b.matrix_basis=matrix;b.rotation_mode=mode
        restored=points(part);check('restored_'+part,max((x-y).length for x,y in zip(initial,restored))<1e-5)
    check('no_actions_or_drivers',not bpy.data.actions and not any(o.animation_data and (o.animation_data.action or o.animation_data.drivers) for o in scene.objects))
    old=json.loads((out/'preserved-files.json').read_text());bad=[p for p,h in old.items() if sha(ROOT/p)!=h]
    check('old_outputs_unchanged',not bad,dict(files=len(old),changed=bad))
    renders=['before.png','after.png'] if geometry_only else ['before.png','after.png','portrait.png','back.png','face.png','equipment.png','context.png']
    for name in renders:
        check('render_'+name,(out/name).is_file() and (out/name).stat().st_size>10000)
    pair=json.loads((out/'appearance-comparison.json').read_text())
    check('same_comparison_camera_light_settings',pair['identical_contract'])
    check('all_source_texture_images_packed',all(i.packed_file for i in bpy.data.images if i.name.startswith('snow_01_')))
    write(report_path,dict(status='PASS',geometry_only=geometry_only,checks=checks,blend_sha256=sha(bpy.data.filepath),blender=bpy.app.version_string,
          scene_saved_by_verifier=False,limitations='No global collision certification or biomechanical validation'))
    print('LOOK_VERIFY_PASS',len(checks))


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['build','render','verify','reproduce'],required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--geometry-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=a.output.resolve();c=tomllib.loads((out/'config.toml').read_text());scene=bpy.context.scene
    assert sha(ROOT/c['source']['blend'])==c['source']['sha256']
    if a.stage=='verify':verify(out,c,a.geometry_only);return
    if a.stage in ['build','reproduce']:
        before=existing_signature()
        if a.stage=='build':
            write(out/'preserved-scene-signature.json',before)
            cams=cameras(scene);scene.camera=cams['Portrait'];r=c['render']
            setup(scene,(r['comparison_size'],r['comparison_size']),r['comparison_samples'],r)
            before_render=render(scene,out/'before.png')
        tailor=Tailor(c['wardrobe']);meta=tailor.build()
        assert existing_signature()==before,'ENVIRONMENT_RIG_OR_SKIS_MODIFIED'
        if a.stage=='reproduce':
            assert appearance_signature()==json.loads((out/'appearance-signature.json').read_text()),'LOOK_REBUILD_DIFFERS'
            write(out/'reproducibility.json',dict(status='PASS',objects=len(tailor.created),method='Independent rebuild from preserved source scene; exact mesh, bone binding hierarchy and transform signatures'))
            return
        after_render=render(scene,out/'after.png')
        write(out/'appearance-comparison.json',dict(before=before_render,after=after_render,identical_contract=before_render['contract']==after_render['contract']))
        scene['appearance_stage']='TAILORED_STATIC_ATHLETE';scene['appearance_config']=json.dumps(c)
        # Free viewport on the athlete; all original geometry remains present.
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':
                    view=area.spaces.active;view.region_3d.view_location=tuple(tailor.rig.matrix_world@Vector((0,0,.92)))
                    view.region_3d.view_distance=4.7;view.region_3d.view_rotation=cams['Portrait'].rotation_euler.to_quaternion()
                    view.region_3d.view_perspective='PERSP';view.overlay.show_extras=False
        for o in scene.objects:o.select_set(False)
        tailor.rig.select_set(True);bpy.context.view_layer.objects.active=tailor.rig
        write(out/'appearance-signature.json',appearance_signature());write(out/'build-report.json',dict(athlete=meta,blender=bpy.app.version_string))
        assert not (out/'snowpark-tailored-athlete.blend').exists()
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'snowpark-tailored-athlete.blend'))
    elif a.stage=='render':
        r=c['render'];records=[]
        for name,filename in [('Portrait','portrait.png'),('Back','back.png'),('Face','face.png'),('Equipment','equipment.png')]:
            scene.camera=scene.objects['LOOK_Camera_'+name]
            setup(scene,(r['detail_size'],r['detail_size']),r['detail_samples'],r)
            records.append(render(scene,out/filename));write(out/'presentation-renders.json',records)
        scene.camera=scene.objects['Preview_main'];setup(scene,(r['context_width'],r['context_height']),r['context_samples'],r)
        records.append(render(scene,out/'context.png'));write(out/'presentation-renders.json',records)
    print('LOOK_STAGE_COMPLETE',a.stage)


if __name__=='__main__':main()
