"""P2 staged runner. Compare snow first, then make an explicit visual selection."""
import argparse,datetime,hashlib,json
from pathlib import Path
import shutil,subprocess,time,tomllib

ROOT=Path(__file__).resolve().parent
BLENDER='/Applications/Blender.app/Contents/MacOS/Blender'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['compare','athlete','verify'])
    p.add_argument('--output',type=Path)
    p.add_argument('--snow',choices=['baseline','pbr'])
    p.add_argument('--reason')
    a=p.parse_args();c=tomllib.loads((ROOT/'p2_config.toml').read_text())
    if a.stage=='compare':
        out=ROOT/'outputs'/datetime.datetime.now(datetime.timezone.utc).strftime('p2-%Y%m%dT%H%M%S-%fZ');out.mkdir()
        original=ROOT/c['source']['p1_blend']
        assert hashlib.sha256(original.read_bytes()).hexdigest()==c['source']['p1_sha256']
        shutil.copy2(original,out/'snow-baseline.blend');shutil.copy2(ROOT/'p2_config.toml',out/'p2_config.toml')
        frozen={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in original.parent.rglob('*') if f.is_file()}
        (out/'p1-preservation-before.json').write_text(json.dumps(frozen,indent=2)+'\n')
    else:
        if not a.output:p.error('--output required')
        out=a.output.resolve()
    assert out.is_relative_to(ROOT/'outputs') and out.is_dir()
    if a.stage=='athlete':
        report=json.loads((out/'snow-comparison.json').read_text())
        assert report['identical_environment_geometry'] and report['identical_render_contract']
        if not (out/'snow-decision.json').exists():
            if not a.snow or not a.reason:p.error('--snow and --reason required for visual selection')
            (out/'snow-decision.json').write_text(json.dumps(dict(selected=a.snow,reason=a.reason,decision_by='Explicit visual selection'),indent=2)+'\n')
        chosen=json.loads((out/'snow-decision.json').read_text())['selected']
    script={'compare':'compare_snow.py','athlete':'build_p2.py','verify':'verify_p2.py'}[a.stage]
    blend=out/({'compare':'snow-baseline.blend','athlete':'snow-pbr-candidate.blend' if a.stage=='athlete' and chosen=='pbr' else 'snow-baseline.blend','verify':'snowpark-athlete.blend'}[a.stage])
    command=[BLENDER,'--background','--offline-mode','--disable-autoexec','--python-exit-code','1',str(blend),'--python',str(ROOT/'scripts'/script),'--','--output',str(out)]
    if a.stage!='verify':command+=['--config',str(out/'p2_config.toml')]
    source=out/'source';source.mkdir(exist_ok=True)
    for f in [ROOT/'run_p2.py',ROOT/'p2_config.toml',*[ROOT/'scripts'/n for n in ['p2_support.py','compare_snow.py','athlete_proxy.py','build_p2.py','verify_p2.py']]]:
        target=source/f.name
        if target.exists():assert target.read_bytes()==f.read_bytes(),f'SOURCE_CHANGED: {f}'
        else:shutil.copy2(f,target)
    log=out/(a.stage+'-execution.log')
    if log.exists():log=out/(a.stage+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S')+'-execution.log')
    tick=time.monotonic()
    with log.open('w') as stream:proc=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=1800,cwd=ROOT)
    with (out/'execution.jsonl').open('a') as stream:stream.write(json.dumps(dict(stage=a.stage,command=command,exit_code=proc.returncode,seconds=time.monotonic()-tick,log=log.name))+'\n')
    print('P2_STAGE',a.stage,'EXIT',proc.returncode,'OUTPUT',out,flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)


if __name__=='__main__':main()
