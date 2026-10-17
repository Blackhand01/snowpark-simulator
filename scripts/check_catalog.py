"""Test catalog schema, unsafe ranges, phase continuity and inversion counts."""
import argparse
import copy
import json
import math
from pathlib import Path
import tomllib
from trick_profile import sample_trick,validate


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
    root=Path(__file__).resolve().parents[1];catalog=json.loads((root/'trick_catalog.json').read_text());cases=[];mutations=[]
    for entry in catalog['entries']:
        c=tomllib.loads((root/entry['config']).read_text());validate(c);m=c['motion'];k=c['trick'];eps=1e-5
        bad=[];maxjump=0;maxdv=0
        times=[m['takeoff_s'],m['takeoff_s']+m['flight_s']/2,m['prepare_s'],m['takeoff_s']+m['flight_s'],m['recover_s']]
        if 'axis_release_start_fraction' in k:times.append(m['takeoff_s']+m['flight_s']*k['axis_release_start_fraction'])
        for t in times:
            aa,bb,zz=sample_trick(t-eps,c),sample_trick(t+eps,c),sample_trick(t,c)
            for field in ['y','altitude','crouch','torso_pitch','ski_pitch','arm_swing','accessory_pitch','spin','tilt']:
                jump=abs(aa[field]-bb[field]);dv=abs((bb[field]-zz[field])/eps-(zz[field]-aa[field])/eps)
                maxjump=max(maxjump,jump);maxdv=max(maxdv,dv)
                if jump>.001 or dv>.01:bad.append([t,field,jump,dv])
        old=False;events=0
        for i in range(5001):
            s=sample_trick(m['duration_s']*i/5000,c)
            down=math.cos(s['tilt'])**2+math.sin(s['tilt'])**2*math.cos(s['spin'])<0
            events+=int(down and not old);old=down
        expected={'double_cork_experimental':2,'triple_cork_experimental':3}.get(k['family'],1)
        cases.append(dict(id=entry['id'],schema_passed=True,max_boundary_delta=maxjump,max_derivative_delta=maxdv,discontinuities=bad,inversion_excursions=events,expected_excursions=expected,passed=not bad and events==expected))
        for group,key,value in [('motion','fps',True),('motion','fps',121),('motion','height_m',float('nan')),('motion','x_m',16),('trick','direction',True),('trick','direction',0),('trick','axis_tilt_degrees',90),('trick','rotation_degrees',999),('trick','axis_release_start_fraction',float('nan')),('source','blend','../outside.blend'),('render','samples',0)]:
            d=copy.deepcopy(c);d[group][key]=value;rejected=False
            try:validate(d)
            except (AssertionError,KeyError,TypeError):rejected=True
            mutations.append(dict(id=entry['id'],field=group+'.'+key,rejected=rejected))
        d=copy.deepcopy(c);del d['trick']['discipline'];rejected=False
        try:validate(d)
        except (AssertionError,KeyError):rejected=True
        mutations.append(dict(id=entry['id'],field='missing trick.discipline',rejected=rejected))
    result=dict(status='PASS' if all(x['passed'] for x in cases) and all(x['rejected'] for x in mutations) else 'FAIL',configs=cases,invalid_config_cases=mutations,limits='Analytic profile/schema tests; mesh and collision checks are separate Blender executions')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],len(cases),'configs,',len(mutations),'invalid configs rejected');assert result['status']=='PASS'


if __name__=='__main__':main()
