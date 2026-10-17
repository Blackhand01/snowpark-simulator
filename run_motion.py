"""Run a single motion stage in a new directory, preserving the source scene."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import tomllib

ROOT = Path(__file__).resolve().parent
BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['build', 'verify', 'render', 'preview'])
    p.add_argument('--output', type=Path)
    p.add_argument('--config', type=Path, default=ROOT/'boardslide_synced.toml')
    a = p.parse_args()
    if a.stage == 'build':
        config = a.config.resolve()
        assert config.is_relative_to(ROOT)
        c = tomllib.loads(config.read_text())
        source = (ROOT/c['source']['blend']).resolve()
        assert source.is_relative_to(ROOT)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == c['source']['sha256']
        prefix='boardslide-synced' if 'retime' in c else 'boardslide' if c.get('rail_slide',{}).get('style')=='boardslide' else 'rail-double-cork' if 'air_trick' in c else 'rail-slide' if 'rail_slide' in c else 'cork' if 'trick' in c else 'motion'
        out = ROOT/'outputs'/datetime.datetime.now(datetime.timezone.utc).strftime(prefix+'-%Y%m%dT%H%M%S-%fZ')
        out.mkdir(exist_ok=False)
        shutil.copy2(config, out/'config.toml')
        if 'retime' in c:
            manifest = (ROOT/c['retime']['manifest']).resolve()
            assert manifest.is_relative_to(ROOT)
            shutil.copy2(manifest, out/'reference-timing.json')
        (out/'source').mkdir()
        for f in [Path(__file__), ROOT/'scripts/animate_scene.py', ROOT/'scripts/motion_profile.py', ROOT/'scripts/trick_profile.py', ROOT/'scripts/rail_slide_profile.py', ROOT/'scripts/rail_slide_scene.py', ROOT/'scripts/refine_profile.py', ROOT/'scripts/refine_geometry.py', ROOT/'scripts/p2_support.py', ROOT/'scripts/build_scene.py', ROOT/'refine_config.toml']:
            shutil.copy2(f, out/'source'/f.name)
        for name in ['retime_scene.py', 'reference_clock.py', 'encode_preview.py', 'compare_reference.py']:
            shutil.copy2(ROOT/'scripts'/name, out/'source'/name)
    else:
        assert a.output
        out = a.output.resolve()
        assert out.is_relative_to(ROOT/'outputs')
        c = tomllib.loads((out/'config.toml').read_text())
        source = out/'snowpark-motion.blend'
    command = [BLENDER, '--background', '--offline-mode', '--disable-autoexec', '--python-exit-code', '1', str(source), '--python', str(ROOT/'scripts/animate_scene.py'), '--', '--stage', a.stage, '--output', str(out)]
    snapshot=out/datetime.datetime.now(datetime.timezone.utc).strftime('stage-source-'+a.stage+'-%Y%m%dT%H%M%S-%fZ')
    snapshot.mkdir(exist_ok=False)
    for f in [Path(__file__),ROOT/'scripts/animate_scene.py',ROOT/'scripts/motion_profile.py',ROOT/'scripts/trick_profile.py',ROOT/'scripts/rail_slide_profile.py',ROOT/'scripts/rail_slide_scene.py']:
        shutil.copy2(f,snapshot/f.name)
    for name in ['retime_scene.py', 'reference_clock.py', 'encode_preview.py', 'compare_reference.py']:
        shutil.copy2(ROOT/'scripts'/name,snapshot/name)
    log = out/(a.stage+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S-%f')+'.log')
    start = time.monotonic()
    with log.open('w') as stream:
        proc = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1800, cwd=ROOT)
    with (out/'execution.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(stage=a.stage, command=command, seconds=time.monotonic()-start, exit_code=proc.returncode, log=log.name,stage_source=str(snapshot.relative_to(out))))+'\n')
    print(json.dumps(dict(output=str(out), stage=a.stage, exit_code=proc.returncode)), flush=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == '__main__':
    main()
