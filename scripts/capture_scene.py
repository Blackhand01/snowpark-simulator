"""Minimal RGB/pinhole export with explicit Blender and OpenCV camera conventions."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import shutil
import sys
import tomllib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix,Vector
from animate_scene import points
from build_scene import camera
from p2_support import ROOT,sha,write,render,render_contract


def pose_hash():
    deps=bpy.context.evaluated_depsgraph_get();h=hashlib.sha256()
    for o in sorted(bpy.data.collections['P2_Athlete'].all_objects,key=lambda o:o.name):
        if o.type!='MESH' or o.hide_render:continue
        h.update(o.name.encode())
        for p in points(o,deps):h.update(struct.pack('<3f',*p))
    return h.hexdigest()


def calibration(scene,cam):
    w=scene.render.resolution_x;h=scene.render.resolution_y
    p=cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=w,y=h,scale_x=1,scale_y=1)
    k=Matrix(((w*.5*p[0][0],0,w*.5*(1-p[0][2])),(0,h*.5*p[1][1],h*.5*(1+p[1][2])),(0,0,1)))
    c2w=cam.matrix_world.copy();cv=c2w@Matrix.Diagonal((1,-1,-1,1));w2c=cv.inverted()
    return dict(K=[list(r) for r in k],camera_to_world_blender=[list(r) for r in c2w],camera_to_world_opencv=[list(r) for r in cv],world_to_camera_opencv=[list(r) for r in w2c],resolution=[w,h],lens_mm=cam.data.lens,sensor_width_mm=cam.data.sensor_width,sensor_fit=cam.data.sensor_fit)


def reprojection_error(scene,cam,meta):
    k=Matrix(meta['K']);w2c=Matrix(meta['world_to_camera_opencv']);w,h=meta['resolution'];errors=[]
    deps=bpy.context.evaluated_depsgraph_get()
    for name in ['Rail_tube','ATH_Ski_L','ATH_Ski_R','LOOK_Panoramic_visor']:
        pp=points(scene.objects[name],deps)
        for v in pp[::max(1,len(pp)//24)]:
            local=w2c@v
            if local.z<=.05:continue
            pix=k@local;pix/=pix.z;ndc=world_to_camera_view(scene,cam,v)
            errors.append(math.hypot(pix.x-ndc.x*w,pix.y-(1-ndc.y)*h))
    assert errors
    return max(errors),len(errors)


def capture(out,c):
    scene=bpy.context.scene;a=c['capture'];f=c['source']['frame']
    assert a['views'] in [8,16,32] and len(set(a['test_camera_indices']))==2 and all(0<=i<a['views'] for i in a['test_camera_indices'])
    assert sha(ROOT/c['source']['blend'])==c['source']['sha256']
    scene.frame_set(f);scene.render.resolution_x=a['width'];scene.render.resolution_y=a['height'];scene.render.resolution_percentage=100
    scene.render.pixel_aspect_x=scene.render.pixel_aspect_y=1;scene.cycles.samples=a['samples'];scene.cycles.seed=a['seed'];scene.render.threads=a['threads']
    if hasattr(scene.render,'use_motion_blur'):scene.render.use_motion_blur=False
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='8'
    col=bpy.data.collections.new(f"CAPTURE_{a['views']}_VIEW");scene.collection.children.link(col)
    center=Vector(a['center_m']);el=math.radians(a['elevation_degrees']);cameras=[]
    for i in range(a['views']):
        theta=2*math.pi*i/a['views'];pos=center+Vector((math.cos(theta)*math.cos(el),math.sin(theta)*math.cos(el),math.sin(el)))*a['radius_m']
        cam=camera(f'CAP_Camera_{i:03d}',tuple(pos),tuple(center),a['lens_mm'],col);cam.data.dof.use_dof=False;cameras.append(cam)
    scene.camera=cameras[0];scene['capture_frame']=f;scene['capture_pose_id']=f'f{f:04d}';scene['capture_config']=json.dumps(c)
    bpy.context.view_layer.update();fixed=pose_hash();scene['capture_pose_sha256']=fixed
    assert not (out/'capture.blend').exists();bpy.ops.wm.save_as_mainfile(filepath=str(out/'capture.blend'))
    (out/'images').mkdir();frames=[];records=[];maxerror=0;points_checked=0
    previous=None
    if a.get('reuse_dataset'):
        reuse=(ROOT/a['reuse_dataset']).resolve();assert reuse.is_relative_to(ROOT/'outputs')
        previous=json.loads((reuse/'dataset.json').read_text());assert previous['source_blend_sha256']==c['source']['sha256'] and previous['frame']==f and previous['pose_sha256']==fixed
        prior_views=json.loads((reuse/'cameras.json').read_text())['frames'];ratio=a['views']//len(prior_views);assert a['views']==ratio*len(prior_views)

    for i,cam in enumerate(cameras):
        scene.camera=cam;bpy.context.view_layer.update();assert scene.frame_current==f and pose_hash()==fixed
        meta=calibration(scene,cam);err,n=reprojection_error(scene,cam,meta);assert err<.001,(i,err)
        maxerror=max(maxerror,err);points_checked+=n
        path=out/'images'/f'camera_{i:03d}.png'
        if previous and i%ratio==0:
            old=prior_views[i//ratio];assert all(old[k]==meta[k] for k in meta),'Reuse requires exactly identical calibration'
            assert (old['split']=='test')==(i in a['test_camera_indices'])
            current=render_contract(scene);prior=previous['render_contract'];assert all(current[k]==prior[k] for k in current if k not in ['camera','matrix'])
            original=reuse/old['file_path'];assert sha(original)==old['sha256'];shutil.copy2(original,path)
            record=dict(file=path.name,seconds=0,bytes=path.stat().st_size,sha256=sha(path),contract=current,reused_from=str(original.relative_to(ROOT)))
        else:record=render(scene,path)
        assert pose_hash()==fixed
        entry=dict(camera_id=f'camera_{i:03d}',camera_object=cam.name,file_path=str(path.relative_to(out)),split='test' if i in a['test_camera_indices'] else 'train',pose_id=f'f{f:04d}',frame=f,scene_time_s=(f-1)/scene.render.fps,pose_sha256=fixed,azimuth_degrees=360*i/a['views'],sha256=record['sha256'],**meta)
        frames.append(entry);records.append(record);write(out/'render-records.json',records);write(out/'cameras.json',dict(schema_version=1,frames=frames))
    textures=[]
    for image in bpy.data.images:
        if image.source=='FILE':
            assert image.packed_file
            textures.append(dict(name=image.name,packed=True,packed_sha256=hashlib.sha256(bytes(image.packed_file.data)).hexdigest(),resolution=list(image.size)))
    metadata=dict(schema_version=1,format='RGB PNG + calibrated pinhole cameras; static single pose',source=c['source'],athlete_origin_world_m=list(scene.objects['ANIM_Translation'].matrix_world.translation),source_blend_sha256=sha(ROOT/c['source']['blend']),capture_blend_sha256=sha(out/'capture.blend'),blender=bpy.app.version_string,blender_build=bpy.app.build_hash.decode(),python=sys.version,seed=a['seed'],frame=f,pose_id=f'f{f:04d}',pose_sha256=fixed,units='metres, artistic configured dimensions',camera_conventions=dict(blender='camera +X right, +Y up, -Z forward; camera_to_world',opencv='camera +X right, +Y down, +Z forward; world_to_camera and camera_to_world',pixel_origin='top left image edge; pixel centers at (0.5,0.5)'),distortion=[0,0,0,0,0],depth_normals_masks='NOT_EXPORTED; no validated implementation claimed',textures=textures,materials=[m.name for m in bpy.data.materials],render_contract=records[0]['contract'],reprojection_vs_blender=dict(max_error_px=maxerror,points_checked=points_checked),train_camera_ids=[x['camera_id'] for x in frames if x['split']=='train'],test_camera_ids=[x['camera_id'] for x in frames if x['split']=='test'],limits='View count validates format only; no reconstruction-quality, logo-readability, real-camera or 4D claim')
    write(out/'dataset.json',metadata)
    for split in ['train','test']:
        ff=[dict(file_path='./'+x['file_path'],transform_matrix=x['camera_to_world_blender'],camera_id=x['camera_id'],pose_id=x['pose_id'],time=x['scene_time_s']) for x in frames if x['split']==split]
        first=frames[0];k=first['K'];write(out/f'transforms_{split}.json',dict(camera_model='OPENCV',fl_x=k[0][0],fl_y=k[1][1],cx=k[0][2],cy=k[1][2],w=a['width'],h=a['height'],camera_angle_x=2*math.atan(a['width']/(2*k[0][0])),frames=ff))
    write(out/'capture-result.json',dict(status='CAPTURED_NOT_YET_INDEPENDENTLY_VERIFIED',views=len(frames),max_reprojection_error_px=maxerror,pose_sha256=fixed))


def verify(out,c):
    scene=bpy.context.scene;data=json.loads((out/'dataset.json').read_text());frames=json.loads((out/'cameras.json').read_text())['frames'];checks={};details={}
    checks['configured_unique_cameras_and_images']=len(frames)==c['capture']['views'] and len({f['camera_id'] for f in frames})==len(frames) and len({f['file_path'] for f in frames})==len(frames)
    checks['fixed_pose_survives_reopening']=scene.frame_current==data['frame'] and pose_hash()==data['pose_sha256']
    checks['frozen_scene_has_one_frame_no_object_actions']=scene.frame_start==scene.frame_end==data['frame'] and not any(o.animation_data and (o.animation_data.action or o.animation_data.drivers) for o in scene.objects)
    train=set(data['train_camera_ids']);test=set(data['test_camera_ids']);checks['configured_train_two_test_disjoint']=len(train)==c['capture']['views']-2 and len(test)==2 and not train&test and train|test=={f['camera_id'] for f in frames}
    checks['source_blend_unchanged']=sha(ROOT/c['source']['blend'])==c['source']['sha256']
    maximum=0;roundtrip=0
    for f in frames:
        cam=scene.objects[f['camera_object']];cal=calibration(scene,cam)
        checks[f['camera_id']+'_image_hash']=sha(out/f['file_path'])==f['sha256']
        checks[f['camera_id']+'_saved_camera_matches']=cal=={k:f[k] for k in cal}
        error,n=reprojection_error(scene,cam,f);maximum=max(maximum,error)
        identity=Matrix(f['world_to_camera_opencv'])@Matrix(f['camera_to_world_opencv']);roundtrip=max(roundtrip,max(abs(identity[i][j]-(1 if i==j else 0)) for i in range(4) for j in range(4)))
        checks[f['camera_id']+'_positive_focal_and_proper_rotation']=f['K'][0][0]>0 and f['K'][1][1]>0 and abs(Matrix(f['world_to_camera_opencv']).to_3x3().determinant()-1)<1e-5
    checks['reprojection_agrees_with_independent_blender_projection']=maximum<.001;checks['camera_matrices_are_inverse']=roundtrip<1e-5
    checks['no_motion_blur_or_depth_of_field']=not getattr(scene.render,'use_motion_blur',False) and all(not scene.objects[f['camera_object']].data.dof.use_dof for f in frames)
    details.update(max_reprojection_error_px=maximum,max_matrix_inverse_error=roundtrip)
    target=out/'verification-frozen.json';assert not target.exists()
    write(target,dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,details=details,reopened_blend=Path(bpy.data.filepath).name,blend_sha256=sha(bpy.data.filepath),capture_archive_sha256=sha(out/'capture.blend'),limits='PNG decoding and visual inspection performed separately; no 3DGS training test in this stage'))
    assert all(checks.values()),checks


def freeze(out,c):
    scene=bpy.context.scene;data=json.loads((out/'dataset.json').read_text());before=pose_hash();assert before==data['pose_sha256']
    removed=[]
    for o in scene.objects:
        if o.animation_data:
            removed.append(o.name);o.animation_data_clear()
    scene.frame_start=data['frame'];scene.frame_end=data['frame'];scene.frame_set(data['frame']);bpy.context.view_layer.update()
    assert pose_hash()==before
    target=out/'frozen-pose.blend';assert not target.exists();bpy.ops.wm.save_as_mainfile(filepath=str(target))
    write(out/'freeze-report.json',dict(status='PASS',pose_sha256=before,frozen_blend_sha256=sha(target),source_capture_blend_sha256=sha(out/'capture.blend'),cleared_actions_on_objects=removed,frame_range=[scene.frame_start,scene.frame_end],originals_saved=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['capture','freeze','verify'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve();assert out.is_relative_to(ROOT/'outputs')
    c=tomllib.loads((out/'config.toml').read_text());{'capture':capture,'freeze':freeze,'verify':verify}[a.stage](out,c)


if __name__=='__main__':main()
