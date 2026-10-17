"""Measure the reopened mesh, contacts, rig and real View3D navigation operators."""
import argparse,json,math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from p2_support import ROOT,sha,write
from refine_geometry import fingerprint,stable_fingerprint


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve()
    s=bpy.context.scene;config=json.loads(s['config_json']);checks={}
    def check(name,value,detail=None):
        checks[name]=dict(passed=bool(value),detail=detail)
        assert value,(name,detail)
    check('correct_reopened_scene',s.get('milestone')=='REFINED_STATIC_WITH_ATHLETE')
    expected=json.loads((out/'final-fingerprint.json').read_text());actual=fingerprint(s)
    check('saved_geometry_matches',expected.keys()==actual.keys() and
          all(expected[n]['geometry']==actual[n]['geometry'] for n in expected))
    visible=[n for n in expected if not s.objects[n].hide_viewport and not s.objects[n].hide_render]
    check('saved_visible_world_transforms_match',all(expected[n]['matrix']==actual[n]['matrix'] for n in visible),len(visible))
    write(out/'stable-final-fingerprint.json',stable_fingerprint(s))
    old=json.loads((out/'preserved-before.json').read_text())
    changed=[f for f,h in old.items() if sha(ROOT/f)!=h]
    check('previous_outputs_unchanged',not changed,dict(files=len(old),changed=changed))
    ground=s.objects['Snow_terrain'];columns={}
    for v in ground.data.vertices:
        pnt=ground.matrix_world@v.co;columns.setdefault(round(pnt.x,5),[]).append((pnt.y,pnt.z))
    slopes=[];negative=0
    for values in columns.values():
        values.sort()
        for (ya,za),(yb,zb) in zip(values,values[1:]):
            g=(zb-za)/(yb-ya);slopes.append(g);negative+=g<=0
    middle=columns[min(columns,key=abs)];run=middle[-1][0]-middle[0][0];drop=middle[-1][1]-middle[0][1]
    arc=sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(middle,middle[1:]))
    metrics=dict(horizontal_length_m=run,surface_length_m=arc,drop_m=drop,width_m=max(columns)-min(columns),
                 average_grade_percent=100*drop/run,average_angle_degrees=math.degrees(math.atan(drop/run)),
                 min_local_grade_percent=100*min(slopes),max_local_grade_percent=100*max(slopes),
                 max_local_angle_degrees=math.degrees(math.atan(max(slopes))),non_descending_segments=negative,
                 measured_segments=len(slopes),descent_axis='-Y')
    write(out/'measured-morphology.json',metrics)
    write(out/'centerline-profile.json',dict(points_y_z_m=middle,descent_axis='-Y'))
    check('actual_surface_length',abs(arc-config['terrain']['surface_length_m'])<.005,arc)
    check('actual_drop',abs(drop-config['terrain']['drop_m'])<.001,drop)
    check('no_counter_slopes_or_flat_segments',negative==0,metrics)
    check('local_max_grade_within_reference',max(slopes)<=config['terrain']['reference_max_grade']+1e-5)
    # The apron must meet every core boundary point, including both ends of the run.
    apron=s.objects['Alpine_background_360']
    exterior={(round(v.co.x,5),round(v.co.y,5),round(v.co.z,5)) for v in apron.data.vertices}
    xs=[v.co.x for v in ground.data.vertices];ys=[v.co.y for v in ground.data.vertices]
    xmin,xmax,ymin,ymax=min(xs),max(xs),min(ys),max(ys)
    boundary=[v for v in ground.data.vertices if v.co.x in [xmin,xmax] or v.co.y in [ymin,ymax]]
    missing=[v.index for v in boundary if tuple(round(x,5) for x in v.co) not in exterior]
    check('continuous_landscape_at_all_piste_edges',not missing,dict(boundary_points=len(boundary),unmatched=len(missing)))
    deps=bpy.context.evaluated_depsgraph_get();tree=BVHTree.FromObject(ground,deps)
    def surface(point):
        hit,*_=tree.ray_cast(Vector((point.x,point.y,50)),Vector((0,0,-1)),120)
        assert hit is not None
        return hit.z
    def nearest(obj,point):
        return BVHTree.FromObject(obj,deps).find_nearest(point)[3]
    gaps=[]
    tube=s.objects['Rail_tube']
    n=config['rail']['radial_segments']
    a=sum((tube.matrix_world@v.co for v in list(tube.data.vertices)[:n]),Vector())/n
    b=sum((tube.matrix_world@v.co for v in list(tube.data.vertices)[2*n:3*n]),Vector())/n
    rail_metrics=dict(axis_length_m=(b-a).length,
                      outside_diameter_m=max(v.co.x for v in tube.data.vertices)-min(v.co.x for v in tube.data.vertices),
                      longitudinal_grade_percent=100*(b.z-a.z)/(b.y-a.y),
                      longitudinal_angle_degrees=math.degrees(math.atan((b.z-a.z)/(b.y-a.y))))
    check('actual_rail_dimensions',abs(rail_metrics['axis_length_m']-config['rail']['length_m'])<.001 and
          abs(rail_metrics['outside_diameter_m']-config['rail']['diameter_m'])<.001,rail_metrics)
    write(out/'measured-rail.json',rail_metrics)
    for v in tube.data.vertices:
        pnt=tube.matrix_world@v.co;gaps.append(pnt.z-surface(pnt))
    check('rail_clear_of_snow',min(gaps)>.15,dict(min_gap_m=min(gaps),max_gap_m=max(gaps)))
    for name in ['Rail_tube','Rail_end_front','Rail_end_back']:
        bm=bmesh.new();bm.from_mesh(s.objects[name].data)
        detail=dict(nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),volume_m3=abs(bm.calc_volume(signed=True)))
        bm.free();check('closed_volume_'+name,detail['nonmanifold_edges']==0 and detail['volume_m3']>0,detail)
    contact=[]
    for i in range(len(config['rail']['support_y_m'])):
        foot=s.objects[f'Footing_{i}'];saddle=s.objects[f'Saddle_{i}']
        bottom=[foot.matrix_world@v.co for v in list(foot.data.vertices)[:4]]
        errors=[p.z-surface(p) for p in bottom]
        check('footing_ground_contact_'+str(i),max(abs(e) for e in errors)<.002,errors)
        top_center=sum((v.co for v in list(saddle.data.vertices)[4:]),Vector())/4
        dist=nearest(tube,top_center)
        check('rail_saddle_contact_'+str(i),dist is not None and dist<.002,dist)
        for side in ['L','R']:
            post=s.objects[f'Support_{i}_{side}']
            lower=[nearest(foot,v.co) for v in list(post.data.vertices)[:4]]
            upper=[nearest(saddle,v.co) for v in list(post.data.vertices)[4:]]
            check(f'support_contacts_{i}_{side}',max(lower+upper)<.002,dict(lower_m=lower,upper_m=upper))
    def evaluated_points(name):
        bpy.context.view_layer.update();dep=bpy.context.evaluated_depsgraph_get();o=s.objects[name].evaluated_get(dep)
        data=o.to_mesh();points=[o.matrix_world@v.co for v in data.vertices];o.to_mesh_clear();return points
    ski_gaps=[]
    for name in ['ATH_Ski_L','ATH_Ski_R']:
        for pnt in evaluated_points(name):ski_gaps.append(pnt.z-surface(pnt))
    check('ski_ground_contact',.003<min(ski_gaps)<.012,dict(min_gap_m=min(ski_gaps),max_gap_m=max(ski_gaps)))
    athlete_xmax=max(p.x for o in bpy.data.collections['P2_Athlete'].all_objects
                     if o.type=='MESH' and not o.hide_render for p in evaluated_points(o.name))
    check('athlete_clear_of_rail_and_supports',athlete_xmax<-config['rail']['foot_half_width_m']-.05,athlete_xmax)
    rig=s.objects['Athlete_Rig'];check('rig_has_22_bones',len(rig.data.bones)==22)
    for bone,part in [('forearm.L','ATH_Glove_L'),('thigh.R','ATH_Ski_R'),('head','ATH_Helmet')]:
        before=evaluated_points(part);pb=rig.pose.bones[bone];old_matrix=pb.matrix_basis.copy();old_mode=pb.rotation_mode
        pb.rotation_mode='XYZ';pb.rotation_euler.x=.25
        after=evaluated_points(part);moved=max((x-y).length for x,y in zip(before,after))
        check('actual_fk_'+part,moved>.01,moved)
        pb.matrix_basis=old_matrix;pb.rotation_mode=old_mode
        restored=evaluated_points(part);check('restore_'+part,max((x-y).length for x,y in zip(before,restored))<1e-5)
    check('no_actions_drivers_or_tricks',not bpy.data.actions and not any(o.animation_data and (o.animation_data.action or o.animation_data.drivers) for o in s.objects))
    check('no_dense_displacement',all(m.type not in ['SUBSURF','DISPLACE'] for m in ground.modifiers))
    pair=json.loads((out/'snow-comparison.json').read_text())
    check('controlled_material_comparison',pair['identical_geometry'] and pair['identical_render_contract'])
    if json.loads((out/'snow-decision.json').read_text())['selected']=='pbr':
        textures=list({node.image.name:node.image for mat in ground.data.materials if mat and mat.use_nodes
                       for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image}.values())
        check('pbr_textures_packed',len(textures)==3 and all(img.packed_file and tuple(img.size)==(1024,1024) for img in textures),
              [dict(name=img.name,packed=bool(img.packed_file),size=list(img.size)) for img in textures])
    check('all_mesh_coordinates_finite',all(math.isfinite(x) for o in s.objects if o.type=='MESH' for v in o.data.vertices for x in v.co))
    for f in ['main.png','slope-side.png','rail-close.png','overview.png']:
        img=bpy.data.images.load(str(out/f),check_existing=False)
        check('render_'+f,tuple(img.size)==(config['render']['width'],config['render']['height']));bpy.data.images.remove(img)
    # This uses real Blender View3D operators in the reopened process, not camera renders.
    navigation=dict(mode='Blender View3D operator test in background process',manual_gui_interaction=False,steps=[])
    try:
        area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
        region=next(r for r in area.regions if r.type=='WINDOW');rv=area.spaces.active.region_3d
        with bpy.context.temp_override(area=area,region=region):
            for name,kwargs in [('view_orbit',dict(type='ORBITLEFT')),('view_pan',dict(type='PANRIGHT')),('zoom',dict(delta=1))]:
                operator=getattr(bpy.ops.view3d,name);operator.get_rna_type()
                before=(tuple(rv.view_rotation),tuple(rv.view_location),rv.view_distance)
                result=operator(**kwargs);after=(tuple(rv.view_rotation),tuple(rv.view_location),rv.view_distance)
                ok='FINISHED' in result and before!=after
                navigation['steps'].append(dict(operator='view3d.'+name,passed=ok,result=list(result),before=before,after=after))
        navigation['status']='PASS' if all(x['passed'] for x in navigation['steps']) else 'NOT_VERIFIED'
    except Exception as error:navigation.update(status='NOT_VERIFIED',error=str(error))
    write(out/'navigation.json',navigation)
    write(out/'verification.json',dict(status='PASS',checks=checks,blender=bpy.app.version_string,build=bpy.app.build_hash.decode(),
           blend_sha256=sha(bpy.data.filepath),morphology=metrics,navigation_status=navigation['status'],scene_saved_by_verifier=False))
    print('REFINEMENT_VERIFY_PASS',len(checks),json.dumps(metrics),navigation['status'])


if __name__=='__main__':main()
