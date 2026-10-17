"""Count off-axis inversion excursions from the actual saved orientation action."""
import json
import math
from pathlib import Path
import sys
import tomllib

import bpy
from mathutils import Euler,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refine_profile import grade,solve

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
c=tomllib.loads((out/'config.toml').read_text());m=c['motion']
profile=solve(tomllib.loads((Path(__file__).resolve().parents[1]/'refine_config.toml').read_text())['terrain'])
scene=bpy.context.scene;events=[];was_down=False;lowest=1
for half in range(2*(scene.frame_end-1)+1):
    f=1+half*.5;scene.frame_set(int(f),subframe=f-int(f))
    control=scene.objects['ANIM_Orientation'];y=scene.objects['ANIM_Translation'].location.y
    up=control.matrix_world.to_quaternion()@Vector((0,0,1))
    ground_up=Euler((math.atan(grade(y,profile)),0,0)).to_quaternion()@Vector((0,0,1))
    dot=up.dot(ground_up);down=dot<0;lowest=min(lowest,dot)
    if down and not was_down:events.append(f)
    was_down=down
expected={'double_cork_experimental':2,'triple_cork_experimental':3}.get(c['trick']['family'],1)
result=dict(status='PASS' if len(events)==expected else 'FAIL',inversion_excursions=len(events),expected_excursions=expected,entry_frames=events,min_up_dot=lowest,
            interpretation='Artistic off-axis excursion count; not certification of a sports trick or biomechanics')
target=out/('single-cork-check.json' if expected==1 else 'experimental-cork-check.json');assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));assert result['status']=='PASS'
