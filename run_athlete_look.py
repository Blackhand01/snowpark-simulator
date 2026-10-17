"""Create and inspect a new athlete appearance version; preserve all earlier output files."""
import argparse,datetime,hashlib,json,shutil,subprocess,time,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BLENDER='/Applications/Blender.app/Contents/MacOS/Blender'


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['build','render','verify','reproduce']);p.add_argument('--output',type=Path)
    p.add_argument('--geometry-only',action='store_true');a=p.parse_args()
    assert not a.geometry_only or a.stage=='verify'
    if a.stage=='build':
        assert a.output is None
        out=ROOT/'outputs'/datetime.datetime.now(datetime.timezone.utc).strftime('athlete-look-%Y%m%dT%H%M%S-%fZ');out.mkdir()
        shutil.copy2(ROOT/'athlete_look.toml',out/'config.toml')
        files={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for d in (ROOT/'outputs').iterdir()
               if d.is_dir() and d!=out for f in d.rglob('*') if f.is_file()}
        (out/'preserved-files.json').write_text(json.dumps(files,indent=2)+'\n')
    else:
        if not a.output:p.error('--output required')
        out=a.output.resolve()
    assert out.is_relative_to(ROOT/'outputs') and out.is_dir()
    c=tomllib.loads((out/'config.toml').read_text());label='geometry-check' if a.geometry_only else a.stage;n=1
    while (out/'source'/label).exists():
        assert a.stage in ['verify','reproduce'],'Build and render never overwrite earlier attempts'
        n+=1;label=a.stage+'-'+str(n)
    source=out/'source'/label;source.mkdir(parents=True)
    inputs=[ROOT/'scripts'/name for name in ['athlete_look.py','build_athlete_look.py','athlete_look_evidence.py','build_scene.py','p2_support.py','refine_geometry.py','refine_profile.py']]+[ROOT/'run_athlete_look.py',out/'config.toml']
    manifest={}
    for f in inputs:shutil.copy2(f,source/f.name);manifest[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
    (source/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    blend=ROOT/c['source']['blend'] if a.stage in ['build','reproduce'] else out/'snowpark-tailored-athlete.blend'
    command=[BLENDER,'--background','--offline-mode','--disable-autoexec','--python-exit-code','1',str(blend),'--python',str(ROOT/'scripts/build_athlete_look.py'),'--','--stage',a.stage,'--output',str(out)]
    if a.geometry_only:command.append('--geometry-only')
    tick=time.monotonic();log=out/(label+'.log')
    with log.open('w') as f:proc=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=3000,cwd=ROOT)
    with (out/'execution.jsonl').open('a') as f:f.write(json.dumps(dict(stage=a.stage,attempt=n,command=command,exit_code=proc.returncode,seconds=time.monotonic()-tick,log=log.name))+'\n')
    print('ATHLETE_LOOK',a.stage,'EXIT',proc.returncode,'OUTPUT',out,flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)


if __name__=='__main__':main()
