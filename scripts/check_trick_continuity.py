"""Test phase-boundary continuity including velocity, both spin signs and 3 angles."""
import argparse
import copy
import json
from pathlib import Path
import tomllib
from trick_profile import sample_trick


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists()
    c=tomllib.loads(a.config.read_text());rows=[]
    for n in [360,540,720]:
        for direction in [-1,1]:
            d=copy.deepcopy(c);d['trick']['rotation_degrees']=n;d['trick']['direction']=direction
            m=d['motion'];eps=1e-5;bad=[];maxjump=0;maxdv=0
            boundaries=[m['takeoff_s'],m['takeoff_s']+m['flight_s']/2,m['prepare_s'],m['takeoff_s']+m['flight_s'],m['recover_s']]
            if 'axis_release_start_fraction' in d['trick']:boundaries.append(m['takeoff_s']+m['flight_s']*d['trick']['axis_release_start_fraction'])
            for t in boundaries:
                left,right,center=sample_trick(t-eps,d),sample_trick(t+eps,d),sample_trick(t,d)
                for k in ['y','altitude','crouch','torso_pitch','ski_pitch','arm_swing','accessory_pitch','spin','tilt']:
                    jump=abs(right[k]-left[k]);dv=abs((right[k]-center[k])/eps-(center[k]-left[k])/eps)
                    maxjump=max(maxjump,jump);maxdv=max(maxdv,dv)
                    if jump>.001 or dv>.01:bad.append([t,k,jump,dv])
            rows.append(dict(degrees=n,direction=direction,max_boundary_delta=maxjump,max_one_sided_derivative_difference=maxdv,failed=bad))
    result=dict(status='PASS' if all(not x['failed'] for x in rows) else 'FAIL',cases=rows,
                method='Two-sided finite differences, epsilon 1e-5 s; value tolerance .001 m/rad, derivative tolerance .01 m/s or rad/s; no physics validation')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(rows),'cases');assert result['status']=='PASS'


if __name__=='__main__':main()
