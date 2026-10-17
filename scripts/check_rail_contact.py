"""Verify per-time intentional ski/rail clearance in an existing saved clip."""
import json
from pathlib import Path
import sys
import tomllib
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from animate_scene import points

out=Path(sys.argv[sys.argv.index('--')+1]).resolve();c=tomllib.loads((out/'config.toml').read_text());m=c['motion']
assert c['trick']['family']=='rail_to_cork'
scene=bpy.context.scene;tree=BVHTree.FromObject(scene.objects['Rail_tube'],bpy.context.evaluated_depsgraph_get());rows=[]
for half in range(2*round(m['takeoff_s']*m['fps'])+1):
    f=1+half*.5;scene.frame_set(int(f),subframe=f-int(f));deps=bpy.context.evaluated_depsgraph_get()
    pp=points(scene.objects['ATH_Ski_L'],deps);gaps=[]
    for i in range(0,len(pp)-3,4):
        p=(pp[i]+pp[i+1])*.5;hit,*_=tree.ray_cast(Vector((p.x,p.y,30)),Vector((0,0,-1)),100)
        if hit is not None:gaps.append(p.z-hit.z)
    rows.append(dict(frame=f,min_gap_m=min(gaps) if gaps else None,passed=bool(gaps) and .003<min(gaps)<.025))
result=dict(status='PASS' if all(r['passed'] for r in rows) else 'FAIL',sampled_times=len(rows),samples=rows,
            limits='Intentional 3–25 mm rendering clearance on left ski at every half frame; no contact forces or balance validation')
target=out/'rail-contact-profile.json';assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(rows));assert result['status']=='PASS'
