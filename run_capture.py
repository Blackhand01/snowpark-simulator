"""Capture one frozen pose or independently validate an existing dataset."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import tomllib

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['capture','freeze','verify']);p.add_argument('--output',type=Path);p.add_argument('--config',type=Path,default=ROOT/'capture.toml');a=p.parse_args()
    if a.stage=='capture':
        config=a.config.resolve();assert config.is_relative_to(ROOT)
        c=tomllib.loads(config.read_text());source=(ROOT/c['source']['blend']).resolve();assert source.is_relative_to(ROOT)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==c['source']['sha256']
        out=ROOT/'outputs'/datetime.datetime.now(datetime.timezone.utc).strftime('capture-%Y%m%dT%H%M%S-%fZ');out.mkdir(exist_ok=False)
        shutil.copy2(config,out/'config.toml');(out/'source').mkdir()
        for f in [Path(__file__),ROOT/'scripts/capture_scene.py',ROOT/'scripts/p2_support.py',ROOT/'scripts/build_scene.py',ROOT/'scripts/animate_scene.py',ROOT/'scripts/motion_profile.py',ROOT/'scripts/trick_profile.py',ROOT/'scripts/refine_geometry.py',ROOT/'scripts/refine_profile.py']:
            shutil.copy2(f,out/'source'/f.name)
    else:
        assert a.output;out=a.output.resolve();assert out.is_relative_to(ROOT/'outputs');source=out/('frozen-pose.blend' if a.stage=='verify' else 'capture.blend')
    snap=out/datetime.datetime.now(datetime.timezone.utc).strftime('stage-source-'+a.stage+'-%Y%m%dT%H%M%S-%fZ');snap.mkdir(exist_ok=False)
    for file in [Path(__file__),ROOT/'scripts/capture_scene.py']:shutil.copy2(file,snap/file.name)
    command=['/Applications/Blender.app/Contents/MacOS/Blender','--background','--offline-mode','--disable-autoexec','--python-exit-code','1',str(source),'--python',str(ROOT/'scripts/capture_scene.py'),'--','--stage',a.stage,'--output',str(out)]
    log=out/(a.stage+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S-%f')+'.log');t=time.monotonic()
    with log.open('x') as stream:proc=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=1800,cwd=ROOT)
    with (out/'execution.jsonl').open('a') as stream:stream.write(json.dumps(dict(stage=a.stage,command=command,seconds=time.monotonic()-t,exit_code=proc.returncode,log=log.name))+'\n')
    print(json.dumps(dict(output=str(out),stage=a.stage,exit_code=proc.returncode)),flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)


if __name__=='__main__':main()
