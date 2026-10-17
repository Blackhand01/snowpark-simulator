"""Small asymmetric procedural object for a real backend test before snowpark."""
import argparse
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector
from build_scene import camera,material
from capture_scene import calibration
from p2_support import write,render

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--views',type=int,choices=[8,32],default=8);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.output.resolve();out.mkdir(exist_ok=False)
assert out.is_relative_to(Path(__file__).resolve().parents[1]/'outputs')
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.seed=1729;scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=scene.render.resolution_y=128;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
world=bpy.data.worlds.new('Tiny_world');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.65,.7,.8,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.6;scene.world=world
mats=[material('Tiny_red',(.65,.035,.015)),material('Tiny_blue',(.025,.16,.65)),material('Tiny_yellow',(.8,.5,.015))]
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,.55));obj=bpy.context.object
for m in mats:obj.data.materials.append(m)
for face in obj.data.polygons:face.material_index=face.index%3
bevel=obj.modifiers.new('Tiny_bevel','BEVEL');bevel.width=.025;bevel.segments=2
bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=10,radius=.20,location=(.58,-.26,.95));bpy.context.object.data.materials.append(mats[2])
light=bpy.data.lights.new('Tiny_sun','SUN');light.energy=3;light.angle=.12;o=bpy.data.objects.new('Tiny_sun',light);scene.collection.objects.link(o);o.rotation_euler=(.4,-.3,-.6)
col=bpy.data.collections.new('Tiny_cameras');scene.collection.children.link(col);cams=[];center=Vector((0,0,.6))
for i in range(a.views):
    theta=2*math.pi*i/a.views;el=math.radians(20)
    pos=center+Vector((math.cos(theta)*math.cos(el),math.sin(theta)*math.cos(el),math.sin(el)))*3
    cams.append(camera(f'Tiny_camera_{i:03d}',tuple(pos),tuple(center),40,col))
scene.camera=cams[0];bpy.ops.wm.save_as_mainfile(filepath=str(out/'tiny.blend'));(out/'images').mkdir();frames=[];records=[]
for i,cam in enumerate(cams):
    scene.camera=cam;bpy.context.view_layer.update();cal=calibration(scene,cam);path=out/'images'/f'camera_{i:03d}.png';records.append(render(scene,path))
    frames.append(dict(file_path='./'+str(path.relative_to(out)),transform_matrix=cal['camera_to_world_blender'],camera_id=f'camera_{i:03d}',split='test' if i in [1,1+a.views//2] else 'train',**cal))
for split in ['train','test']:
    k=frames[0]['K'];write(out/f'transforms_{split}.json',dict(camera_model='OPENCV',w=128,h=128,fl_x=k[0][0],fl_y=k[1][1],cx=k[0][2],cy=k[1][2],frames=[dict(file_path=f['file_path'],transform_matrix=f['transform_matrix']) for f in frames if f['split']==split]))
write(out/'cameras.json',dict(frames=frames));write(out/'render-records.json',records);write(out/'tiny-result.json',dict(status='RENDERED',views=a.views,train=a.views-2,test=2,object='Procedural colored cube plus offset sphere; no external asset',blender=bpy.app.version_string))
