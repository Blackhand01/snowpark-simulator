"""Bake articulated cinematic ski hop into a copy of the approved environment."""
import argparse
import csv
import json
import math
from pathlib import Path
import sys
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree
from build_scene import camera
from motion_profile import sample, validate
from p2_support import ROOT, sha, write, render
from refine_geometry import stable_fingerprint
from refine_profile import solve, grade
from trick_profile import sample_trick, quaternion as trick_quaternion, validate as validate_trick


def environment():
    names={o.name for o in bpy.data.collections['REF_Environment'].all_objects}
    return {n:v for n,v in stable_fingerprint(bpy.context.scene).items() if n in names}


def points(o, deps):
    e=o.evaluated_get(deps); mesh=e.to_mesh()
    result=[e.matrix_world@v.co for v in mesh.vertices];e.to_mesh_clear()
    return result


def pose(rig, s):
    for b in rig.pose.bones:
        b.matrix_basis=Matrix.Identity(4)
    pelvis=rig.pose.bones['pelvis'];pelvis.location=(0,-s['crouch'],0)
    # Bone Y is nearly vertical; use armature-space targets instead of guessing local axes.
    pelvis.matrix=Matrix.Translation((0,0,-s['crouch']))@rig.data.bones['pelvis'].matrix_local
    bpy.context.view_layer.update()
    for side in ['L','R']:
        thigh=rig.data.bones['thigh.'+side];shin=rig.data.bones['shin.'+side]
        hip=thigh.head_local+Vector((0,0,-s['crouch']))
        ankle=shin.tail_local.copy(); delta=ankle-hip;d=delta.length
        l1,l2=thigh.length,shin.length
        assert abs(l1-l2)<d<l1+l2
        axis=delta.normalized();a=(l1*l1-l2*l2+d*d)/(2*d)
        forward=Vector((0,-1,0));bend=(forward-axis*forward.dot(axis)).normalized()
        knee=hip+axis*a+bend*math.sqrt(max(0,l1*l1-a*a))
        for b,h,t in [(thigh,hip,knee),(shin,knee,ankle)]:
            q=(b.tail_local-b.head_local).rotation_difference(t-h)@b.matrix_local.to_quaternion()
            rig.pose.bones[b.name].matrix=Matrix.LocRotScale(h,q,Vector((1,1,1)))
            bpy.context.view_layer.update()
        b=rig.data.bones['foot.'+side]
        q=Quaternion((1,0,0),s['ski_pitch'])@b.matrix_local.to_quaternion()
        rig.pose.bones[b.name].matrix=Matrix.LocRotScale(b.head_local,q,Vector((1,1,1)))
        rig.pose.bones['upper_arm.'+side].rotation_mode='XYZ'
        rig.pose.bones['upper_arm.'+side].rotation_euler.x=s['arm_swing']
        rig.pose.bones['hand.'+side].rotation_mode='XYZ'
        rig.pose.bones['hand.'+side].rotation_euler.x=s['accessory_pitch']
    rig.pose.bones['chest'].rotation_mode='XYZ'
    rig.pose.bones['chest'].rotation_euler.x=s['torso_pitch']
    bpy.context.view_layer.update()


def controls(scene):
    col=bpy.data.collections.new('ANIM_Controls');scene.collection.children.link(col)
    objs=[]
    for name in ['ANIM_Translation','ANIM_Orientation']:
        o=bpy.data.objects.new(name,None);col.objects.link(o);o.empty_display_type='PLAIN_AXES';objs.append(o)
    objs[1].parent=objs[0]
    rig=scene.objects['Athlete_Rig'];rig.parent=objs[1];rig.matrix_parent_inverse=Matrix.Identity(4)
    rig.location=(0,0,0);rig.rotation_euler=(0,0,0)
    return objs


def build(out,c):
    m=c['motion'];validate(m);scene=bpy.context.scene;trick='trick' in c
    if trick:validate_trick(c)
    rail=trick and c['trick']['family']=='rail_to_cork'
    assert sha(ROOT/c['source']['blend'])==c['source']['sha256']
    write(out/'environment-before.json',environment())
    trans,orient=controls(scene);rig=scene.objects['Athlete_Rig']
    if trick:rig.location.z=-c['trick']['pivot_height_m']
    profile=solve(tomllib.loads((ROOT/'refine_config.toml').read_text())['terrain'])
    scene.render.fps=m['fps'];scene.frame_start=1;scene.frame_end=1+round(m['duration_s']*m['fps'])
    deps=bpy.context.evaluated_depsgraph_get();tree=BVHTree.FromObject(scene.objects['Snow_terrain'],deps)
    rows=[];signatures={};previous_orientation=None
    for f in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(f);s=sample_trick((f-1)/m['fps'],c) if trick else sample((f-1)/m['fps'],m);pose(rig,s)
        trans.location=(s['x'],s['y'],0)
        ground_grade=grade(s['y'],profile)
        if rail:
            from motion_profile import smooth
            u=max(0,min(1,(s['t']-m['takeoff_s'])/m['flight_s']))
            reference_grade=.10+(ground_grade-.10)*smooth(u)
        else:reference_grade=ground_grade
        ground=Euler((math.atan(reference_grade),0,0)).to_quaternion()
        if trick:
            orient.rotation_mode='QUATERNION'
            # Fit an upright ski plane with the current yaw, independent of off-axis tilt.
            orient.rotation_quaternion=ground@Quaternion((0,0,1),s['spin'])
        else:orient.rotation_euler=ground.to_euler()
        bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
        gaps=[];rail_plane_fit=[]
        for n in ['ATH_Ski_L','ATH_Ski_R']:
            for v in points(scene.objects[n],deps):
                hit,*_=tree.ray_cast(Vector((v.x,v.y,30)),Vector((0,0,-1)),100)
                assert hit is not None;gaps.append(v.z-hit.z)
                if rail and n=='ATH_Ski_L':rail_plane_fit.append(.72+.10*v.y+.16/math.cos(math.atan(.10))-v.z)
        trans.location.z=m['clearance_m']+s['altitude']-min(gaps)
        if rail:
            neutral_rail_z=m['clearance_m']+max(rail_plane_fit)
            ground_z=m['clearance_m']-min(gaps)
            trans.location.z+=(neutral_rail_z-ground_z)*(1-smooth(u))
        if trick:
            q=ground@trick_quaternion(s)
            if previous_orientation is not None and q.dot(previous_orientation)<0:q.negate()
            previous_orientation=q.copy()
            orient.rotation_quaternion=q
        trans.keyframe_insert('location',frame=f);orient.keyframe_insert('rotation_quaternion' if trick else 'rotation_euler',frame=f)
        for b in rig.pose.bones:
            loc,quat,scale=b.matrix_basis.decompose()
            b.rotation_mode='QUATERNION'
            b.location=loc;b.rotation_quaternion=quat;b.scale=scale
            b.keyframe_insert('location',frame=f);b.keyframe_insert('rotation_quaternion',frame=f);b.keyframe_insert('scale',frame=f)
        bpy.context.view_layer.update()
        rows.append(dict(frame=f,**s,root_z=trans.location.z))
        signatures[str(f)]=dict(translation=list(trans.location),pose={b.name:[list(r) for r in b.matrix] for b in rig.pose.bones})
    # Linear interpolation between dense samples avoids Bezier overshoot.
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    bag=strip.channelbag(slot)
                    if bag:
                        for curve in bag.fcurves:
                            for key in curve.keyframe_points:key.interpolation='LINEAR'
    with (out/'timeline.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write(out/'baked-poses.json',signatures)
    col=bpy.data.collections['ANIM_Controls']
    cam=camera('ANIM_Review',(-9,-9,5),(-1,0,1),38,col);scene.camera=cam
    r=c['render'];scene.render.resolution_x=r['width'];scene.render.resolution_y=r['height'];scene.render.resolution_percentage=100
    scene.cycles.samples=r['samples'];scene.cycles.seed=r['seed'];scene.render.threads=r['threads']
    scene['animation_interpretation']=m['interpretation'];scene['animation_config']=json.dumps(c)
    scene['animation_origin']='Translation control follows fitted ski plane; not a measured center of mass'
    freeze=1+round(m['freeze_time_s']*m['fps']);scene.frame_set(freeze)
    for sc in bpy.data.screens:
        for a in sc.areas:
            if a.type=='VIEW_3D':
                a.spaces.active.region_3d.view_location=(-2,0,1)
                a.spaces.active.region_3d.view_distance=15
    for label,t in [('takeoff',m['takeoff_s']),('midair',m['takeoff_s']+m['flight_s']/2),('landing',m['takeoff_s']+m['flight_s'])]:
        scene.timeline_markers.new(label,frame=1+round(t*m['fps']))
    assert not (out/'snowpark-motion.blend').exists()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'snowpark-motion.blend'))
    write(out/'build-report.json',dict(status='BUILT',frames=len(rows),freeze_frame=freeze,blender=bpy.app.version_string,blend_sha256=sha(out/'snowpark-motion.blend'),environment_unchanged=environment()==json.loads((out/'environment-before.json').read_text())))


def verify(out,c):
    scene=bpy.context.scene;m=c['motion'];rig=scene.objects['Athlete_Rig'];checks={};details={}
    def check(n,v,d=None):
        checks[n]=bool(v)
        if d is not None:details[n]=d
    check('environment_geometry_and_hierarchy_preserved',environment()==json.loads((out/'environment-before.json').read_text()))
    check('separate_translation_orientation_rig',rig.parent.name=='ANIM_Orientation' and rig.parent.parent.name=='ANIM_Translation')
    tree=BVHTree.FromObject(scene.objects['Snow_terrain'],bpy.context.evaluated_depsgraph_get())
    names=[o.name for o in bpy.data.collections['P2_Athlete'].all_objects if o.type=='MESH' and not o.hide_render]
    rail='trick' in c and c['trick']['family']=='rail_to_cork'
    rail_obstacles=[];collisions=[];rail_contacts=[]
    if rail:
        deps=bpy.context.evaluated_depsgraph_get()
        for o in bpy.data.collections['REF_Environment'].all_objects:
            if o.type=='MESH' and (o.name.startswith(('Rail_','Support_','Saddle_','Footing_'))):
                e=o.evaluated_get(deps);me=e.to_mesh();vv=[e.matrix_world@v.co for v in me.vertices]
                bounds=[(min(v[k] for v in vv),max(v[k] for v in vv)) for k in range(3)]
                rail_obstacles.append((o.name,BVHTree.FromPolygons(vv,[list(p.vertices) for p in me.polygons]),bounds));e.to_mesh_clear()
        rail_tree=next(t for n,t,b in rail_obstacles if n=='Rail_tube')
    prior=None;maxstep=0;mingap=100;allgap=100;minrail=100;finite=True;maxstretch=0;poseerror=0
    signatures=json.loads((out/'baked-poses.json').read_text())
    # Every frame and half-frame; evaluated skinned meshes, not only root positions.
    for half in range(2*(scene.frame_end-1)+1):
        f=1+half*.5;scene.frame_set(int(f),subframe=f-int(f));deps=bpy.context.evaluated_depsgraph_get()
        positions={}
        for n in names:
            pts=points(scene.objects[n],deps);positions[n]=pts
            finite &= all(math.isfinite(x) for p in pts for x in p)
            minrail=min(minrail,min(abs(p.x) for p in pts)-.47)
            for p in pts:
                hit,*_=tree.ray_cast(Vector((p.x,p.y,30)),Vector((0,0,-1)),100)
                assert hit is not None;gap=p.z-hit.z;allgap=min(allgap,gap)
                if n in ['ATH_Ski_L','ATH_Ski_R']:mingap=min(mingap,gap)
            if rail:
                bounds=[(min(v[k] for v in pts),max(v[k] for v in pts)) for k in range(3)]
                candidates=[(label,t) for label,t,b in rail_obstacles if all(bounds[k][0]<=b[k][1] and bounds[k][1]>=b[k][0] for k in range(3))]
                if candidates:
                    e=scene.objects[n].evaluated_get(deps);me=e.to_mesh()
                    bodytree=BVHTree.FromPolygons(pts,[list(p.vertices) for p in me.polygons]);e.to_mesh_clear()
                    for label,t in candidates:
                        pairs=bodytree.overlap(t)
                        if pairs:collisions.append(dict(frame=f,athlete=n,obstacle=label,triangle_pairs=len(pairs)))
                if n=='ATH_Ski_L' and (f-1)/m['fps']<=m['takeoff_s']:
                    for index in range(0,len(pts)-3,4):
                        p=(pts[index]+pts[index+1])*.5
                        hit,*_=rail_tree.ray_cast(Vector((p.x,p.y,30)),Vector((0,0,-1)),100)
                        if hit is not None:rail_contacts.append(p.z-hit.z)
        if prior:
            maxstep=max(maxstep,max((a-b).length for n in names for a,b in zip(positions[n],prior[n])))
        prior=positions
        for side in ['L','R']:
            for stem in ['thigh','shin']:
                b=rig.pose.bones[stem+'.'+side];maxstretch=max(maxstretch,abs((b.tail-b.head).length-b.bone.length))
        if half%2==0:
            actual=signatures[str(int(f))]['pose']
            poseerror=max(poseerror,max(abs(b.matrix[i][j]-actual[b.name][i][j]) for b in rig.pose.bones for i in range(4) for j in range(4)))
    check('finite_evaluated_geometry',finite)
    check('baked_poses_survive_reopening',poseerror<2e-5,poseerror)
    check('no_sampled_ski_ground_penetration',mingap>=-.001,dict(min_gap_m=mingap,samples='all vertices of both skis every half frame'))
    check('no_visible_part_ground_penetration',allgap>=-.001,dict(min_gap_m=allgap,samples='all evaluated vertices of every visible athlete mesh every half frame'))
    if rail:
        check('no_athlete_rail_support_surface_intersections',not collisions,collisions[:20])
        check('left_ski_rail_contact_before_takeoff',bool(rail_contacts) and .003<min(rail_contacts)<.025,dict(min_gap_m=min(rail_contacts) if rail_contacts else None,samples=len(rail_contacts),method='underside cross-section centers; intentional single-ski cinematic grind'))
    else:check('whole_visible_athlete_clear_of_rail_lane',minrail>0,minrail)
    check('leg_bone_lengths_preserved',maxstretch<1e-5,maxstretch)
    check('temporal_mesh_step_bounded',maxstep<.18,dict(max_half_frame_vertex_step_m=maxstep,threshold_m=.18))
    f1=1;f2=1+round((m['takeoff_s']+m['flight_s']/2)*m['fps'])
    scene.frame_set(f1);first=rig.pose.bones['thigh.L'].matrix_basis.copy();scene.frame_set(f2)
    check('real_leg_articulation',sum(abs(first[i][j]-rig.pose.bones['thigh.L'].matrix_basis[i][j]) for i in range(4) for j in range(4))>.05)
    scene.frame_set(scene.frame_end)
    orientation=scene.objects['ANIM_Orientation'];q=orientation.rotation_quaternion if 'trick' in c else orientation.rotation_euler.to_quaternion()
    expected=Euler((math.atan(grade(m['end_y_m'],solve(tomllib.loads((ROOT/'refine_config.toml').read_text())['terrain']))),0,0)).to_quaternion()
    if 'trick' in c:expected=expected@Quaternion((0,0,1),math.radians(c['trick']['rotation_degrees']*c['trick']['direction']))
    check('landing_orientation_matches_config',abs(q.dot(expected))>.99999)
    check('images_packed',all(i.packed_file for i in bpy.data.images if i.source=='FILE'))
    write(out/'verification.json',dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,details=details,blender=bpy.app.version_string,blend_sha256=sha(bpy.data.filepath),sampled_times=2*(scene.frame_end-1)+1,limits='Cinematic motion only. Sampled vertices/rail-lane exclusion do not certify every triangle-pair intersection, cloth folds, or biomechanics.'))
    assert all(checks.values()),checks


def render_frames(out,c):
    scene=bpy.context.scene;records=[]
    target=out
    if (out/'takeoff.png').exists():
        import datetime
        target=out/datetime.datetime.now(datetime.timezone.utc).strftime('render-review-%Y%m%dT%H%M%S-%fZ')
        target.mkdir(exist_ok=False)
    # Camera tracks each representative pose so equipment is inspectable.
    cam=scene.objects['ANIM_Review'];m=c['motion']
    frames=[('takeoff',m['takeoff_s']),('midair',m['takeoff_s']+m['flight_s']/2),('landing',m['takeoff_s']+m['flight_s'])]
    if 'trick' in c:frames.append(('rotation',m['takeoff_s']+m['flight_s']*.35))
    for label,t in frames:
        scene.frame_set(1+round(t*m['fps']))
        center=scene.objects['ANIM_Translation'].location+Vector((0,0,0 if 'trick' in c else .9))
        cam.location=center+Vector((-3.6,-5.3,2));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=45
        records.append(render(scene,target/(label+'.png')))
        write(target/'renders.json',records)


def preview(out,c):
    scene=bpy.context.scene;m=c['motion'];cam=scene.objects['ANIM_Review']
    scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=480;scene.render.resolution_y=360
    scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL'
    scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
    folder=out/'preview';folder.mkdir(exist_ok=False);records=[]
    for f in range(scene.frame_start,scene.frame_end+1,3):
        scene.frame_set(f);center=scene.objects['ANIM_Translation'].location+Vector((0,0,.2 if 'trick' in c else .9))
        cam.location=center+Vector((-5.6,-7.3,3));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=45
        scene.render.filepath=str(folder/f'{f:04d}.png');bpy.ops.render.render(write_still=True)
        records.append(dict(frame=f,file=str((folder/f'{f:04d}.png').relative_to(out))))
    write(out/'preview.json',dict(engine='BLENDER_WORKBENCH',diagnostic_only=True,frame_stride=3,fps=m['fps']/3,frames=records))


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True,choices=['build','verify','render','preview']);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve()
    assert out.is_relative_to(ROOT/'outputs')
    c=tomllib.loads((out/'config.toml').read_text())
    if 'retime' in c:
        from retime_scene import build as build_timed, verify as verify_timed, preview as preview_timed, render_frames as render_timed
        {'build':build_timed,'verify':verify_timed,'preview':preview_timed,'render':render_timed}[a.stage](out,c)
        return
    if 'rail_slide' in c:
        from rail_slide_scene import build as build_slide, verify as verify_slide, preview as preview_slide, render_frames as render_slide
        {'build':build_slide,'verify':verify_slide,'preview':preview_slide,'render':render_slide}[a.stage](out,c)
        return
    {'build':build,'verify':verify,'render':render_frames,'preview':preview}[a.stage](out,c)


if __name__=='__main__':main()
