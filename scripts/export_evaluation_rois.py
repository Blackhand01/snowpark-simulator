"""Project true scene bounds for evaluation only; never used for training/init."""
import argparse
import json
from pathlib import Path
import sys
import bpy
from bpy_extras.object_utils import world_to_camera_view

p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(__file__).resolve().parents[1]
assert a.scene.resolve().is_relative_to(root/'outputs') and a.output.resolve().is_relative_to(root/'outputs') and not a.output.exists()
bpy.ops.wm.open_mainfile(filepath=str(a.scene.resolve()));scene=bpy.context.scene;dg=bpy.context.evaluated_depsgraph_get();w=scene.render.resolution_x;h=scene.render.resolution_y
objects=[o for o in scene.objects if o.type=='MESH' and (o.name=='Rail_tube' or o.name.startswith('Rail_end_'))];assert len(objects)>=3
vertices=[]
for obj in objects:
    ev=obj.evaluated_get(dg);mesh=ev.to_mesh();vertices.extend([ev.matrix_world@v.co for v in mesh.vertices]);ev.to_mesh_clear()
result=dict(purpose='Evaluation-only projected rail bounding rectangles, not visibility/segmentation masks; includes background and occluding pixels',source=str(a.scene),objects=[o.name for o in objects],views={})
for i in json.loads(scene['capture_config'])['capture']['test_camera_indices']:
    cam=bpy.data.objects[f'CAP_Camera_{i:03d}'];points=[world_to_camera_view(scene,cam,v) for v in vertices];assert all(v.z>0 for v in points)
    x=[v.x*w for v in points];y=[(1-v.y)*h for v in points];box=[max(0,int(min(x))-3),max(0,int(min(y))-3),min(w,int(max(x))+4),min(h,int(max(y))+4)];assert box[2]>box[0] and box[3]>box[1]
    result['views'][f'camera_{i:03d}']=box
a.output.write_text(json.dumps(result,indent=2)+'\n');print('RAIL_ROIS',result['views'])
