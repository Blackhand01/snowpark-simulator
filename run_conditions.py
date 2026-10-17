"""Execute the explicit P9 matrix sequentially, preserving input and prior runs."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parent
matrix=json.loads((ROOT/'conditions.json').read_text());names=[]
for c in matrix['conditions']:
    assert re.fullmatch('[a-z_]+',c['name']) and c['name'] not in names;names.append(c['name'])
    assert c['lighting'] in ['baseline','sun','overcast','backlight'] and -3<=c['exposure_ev']<=3 and .25<=c['gain']<=4
    assert c['white_balance_kelvin'] is None or 2000<=c['white_balance_kelvin']<=12000
    assert isinstance(c['snow_count'],int) and 0<=c['snow_count']<=1000 and 0<c['snow_brightness']<=2
    assert 0<=c['haze_density']<=.1 and 0<=c['blur_exposure_s']<=1/30 and 0<=c['snow_texture_strength']<=.25 and 0<=c['snow_relief_m']<=.01
    assert isinstance(c['occluder'],bool) and isinstance(c['seed'],int)
dataset=ROOT/matrix['dataset'];baseline=ROOT/matrix['baseline'];assert json.loads((baseline/'artifact-verification.json').read_text())['status']=='PASS';assert (baseline/'acceptance.json').is_file();assert json.loads((dataset/'acceptance.json').read_text())['status']=='PASS_AUTO_VALIDATED'
out=ROOT/'outputs'/datetime.datetime.now(datetime.timezone.utc).strftime('conditions-%Y%m%dT%H%M%S-%fZ');out.mkdir(exist_ok=False);shutil.copy2(ROOT/'conditions.json',out/'conditions.json');(out/'source').mkdir()
for file in [Path(__file__),ROOT/'scripts/render_conditions.py',ROOT/'scripts/capture_scene.py',ROOT/'scripts/p2_support.py']:shutil.copy2(file,out/'source'/file.name)
inputs=[dataset/'frozen-pose.blend',dataset/'capture.blend',baseline/'model_5000.ply'];hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs};(out/'input-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n');print('CONDITIONS_OUTPUT',out,flush=True)
for name in names:
    cmd=['/Applications/Blender.app/Contents/MacOS/Blender','--background','--offline-mode','--disable-autoexec','--python-exit-code','1','--python',str(ROOT/'scripts/render_conditions.py'),'--','--run',str(out),'--condition',name];start=time.monotonic()
    with (out/(name+'.log')).open('x') as log:proc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
    with (out/'execution.jsonl').open('a') as f:f.write(json.dumps(dict(condition=name,command=cmd,seconds=time.monotonic()-start,exit_code=proc.returncode))+'\n')
    print(name,'exit',proc.returncode,flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)
assert all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==sha for f,sha in hashes.items());(out/'render-completion.json').write_text(json.dumps(dict(status='RENDER_MATRIX_COMPLETE_NOT_YET_HOST_VERIFIED',conditions=len(names),input_hashes_unchanged=True),indent=2)+'\n')
