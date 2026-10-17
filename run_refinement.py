"""Run staged, versioned morphology refinement; a snow choice is explicit."""
import argparse,datetime,hashlib,json
from pathlib import Path
import shutil,subprocess,time,tomllib

ROOT=Path(__file__).resolve().parent
BLENDER='/Applications/Blender.app/Contents/MacOS/Blender'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['compare','finish','verify','reproduce'])
    p.add_argument('--output',type=Path);p.add_argument('--snow',choices=['baseline','pbr']);p.add_argument('--reason')
    a=p.parse_args()
    if a.stage=='compare':
        assert a.output is None,'A new compare always gets a new output directory'
        out=ROOT/'outputs'/datetime.datetime.now(datetime.timezone.utc).strftime('refine-%Y%m%dT%H%M%S-%fZ');out.mkdir()
        shutil.copy2(ROOT/'refine_config.toml',out/'config.toml')
        frozen={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for d in (ROOT/'outputs').iterdir() if d.is_dir() and d.name.startswith(('p1-','p2-')) for f in d.rglob('*') if f.is_file()}
        (out/'preserved-before.json').write_text(json.dumps(frozen,indent=2)+'\n')
    else:
        if not a.output:p.error('--output required')
        out=a.output.resolve()
    assert out.is_relative_to(ROOT/'outputs') and out.is_dir()
    c=tomllib.loads((out/'config.toml').read_text())
    if a.stage=='finish':
        comparison=json.loads((out/'snow-comparison.json').read_text())
        assert comparison['identical_geometry'] and comparison['identical_render_contract']
        if not (out/'snow-decision.json').exists():
            if not a.snow or not a.reason:p.error('--snow and --reason required after inspecting comparison renders')
            (out/'snow-decision.json').write_text(json.dumps(dict(selected=a.snow,reason=a.reason),indent=2)+'\n')
        choice=json.loads((out/'snow-decision.json').read_text())['selected']
    label=a.stage;attempt=1
    while (out/'source'/label).exists():
        assert a.stage in ['verify','reproduce'],'Build/render stages cannot overwrite a previous attempt'
        attempt+=1;label=a.stage+'-'+str(attempt)
    source=out/'source'/label;source.mkdir(parents=True,exist_ok=False)
    names=['refine_profile.py','refine_geometry.py','refine_athlete.py','refine_scene.py','verify_refinement.py','build_scene.py','athlete_proxy.py','p2_support.py','compare_snow.py']
    files=[ROOT/'scripts'/n for n in names]+[ROOT/'run_refinement.py',out/'config.toml']
    manifest={}
    for f in files:shutil.copy2(f,source/f.name);manifest[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    (source/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if a.stage in ['compare','reproduce']:blend=ROOT/c['source']['p1_blend']
    elif a.stage=='finish':blend=out/('environment-baseline.blend' if choice=='baseline' else 'environment-pbr-candidate.blend')
    else:blend=out/'snowpark-refined.blend'
    command=[BLENDER,'--background','--offline-mode','--disable-autoexec','--python-exit-code','1',str(blend),'--python',str(ROOT/'scripts'/('verify_refinement.py' if a.stage=='verify' else 'refine_scene.py')),'--','--output',str(out)]
    if a.stage!='verify':command+=['--stage',a.stage,'--config',str(out/'config.toml')]
    tick=time.monotonic();log=out/(label+'-execution.log')
    assert not log.exists()
    with log.open('w') as f:proc=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=2400,cwd=ROOT)
    with (out/'execution.jsonl').open('a') as f:f.write(json.dumps(dict(stage=a.stage,attempt=attempt,command=command,exit_code=proc.returncode,seconds=time.monotonic()-tick,log=log.name))+'\n')
    print('REFINEMENT',a.stage,'EXIT',proc.returncode,'OUTPUT',out,flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)


if __name__=='__main__':main()
