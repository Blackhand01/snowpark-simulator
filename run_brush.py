"""Run the pinned native Brush backend in a fresh, measured local run directory."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parent
BINARY=ROOT/'.tools/brush-v0.3.0/binary/brush-app-aarch64-apple-darwin/brush_app'


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--parent',type=Path,required=True);p.add_argument('--steps',type=int,required=True);p.add_argument('--resolution',type=int,required=True);p.add_argument('--max-splats',type=int,default=100000);p.add_argument('--sh-degree',type=int,default=3);p.add_argument('--purpose',choices=['backend-development','baseline','view-count-development'],default='baseline');a=p.parse_args()
    source=a.dataset.resolve();parent=a.parent.resolve();assert source.is_relative_to(ROOT/'outputs') and parent.is_relative_to(ROOT/'outputs')
    assert 1<=a.steps<=30000 and 64<=a.resolution<=640 and 10000<=a.max_splats<=500000
    out=parent/datetime.datetime.now(datetime.timezone.utc).strftime('brush-%Y%m%dT%H%M%S-%fZ');out.mkdir(exist_ok=False)
    shutil.copy2(Path(__file__),out/'run_brush.py')
    command=[str(BINARY),str(source),'--total-steps',str(a.steps),'--max-resolution',str(a.resolution),'--max-splats',str(a.max_splats),'--sh-degree',str(a.sh_degree),'--seed','1729','--refine-every','100','--growth-stop-iter',str(round(a.steps*.7)),'--eval-every',str(a.steps),'--export-every',str(a.steps),'--eval-save-to-disk','--export-path',str(out),'--export-name','model_{iter}.ply']
    env=os.environ.copy();env['RUST_LOG']='info';env['XDG_CACHE_HOME']=str(out/'cache');env['TMPDIR']=str(out/'tmp');(out/'tmp').mkdir()
    train=json.loads((source/'transforms_train.json').read_text());test=json.loads((source/'transforms_test.json').read_text())
    config=dict(command=command,backend='Brush v0.3.0 native Apple Silicon WebGPU/Metal candidate; actual backend checked from log',binary_sha256=hashlib.sha256(BINARY.read_bytes()).hexdigest(),train_views=len(train['frames']),test_views=len(test['frames']),total_steps=a.steps,final_checkpoint_preselected=True,intermediate_test_based_selection=False,seed=1729,backend_dataloader_seed_in_pinned_source=42,env_overrides={k:env[k] for k in ['RUST_LOG','XDG_CACHE_HOME','TMPDIR']})
    config.update(cwd=str(out),cache_policy="Fresh per-run working directory isolates CubeCL target/autotune cache from iCloud placeholders",purpose=a.purpose,evaluation_role='development validation on toy object' if a.purpose=='backend-development' else 'held-out snowpark cameras used for view-count development after 8-view inspection; not an independent blind final test' if a.purpose=='view-count-development' else 'held-out snowpark cameras; fixed final step before this first scene training')
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n');print('BRUSH_OUTPUT',out,flush=True);start=time.monotonic()
    with (out/'train.log').open('x') as log:proc=subprocess.run(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=3600)
    elapsed=time.monotonic()-start;usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    result=dict(exit_code=proc.returncode,seconds=elapsed,peak_child_rss_bytes=usage.ru_maxrss,peak_memory_scope='macOS RUSAGE_CHILDREN RSS; not GPU allocation',outputs=[str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.suffix in ['.ply','.png']],status='PROCESS_EXITED_NOT_YET_ARTIFACT_VERIFIED')
    (out/'execution.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(output=str(out),**result)),flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)


if __name__=='__main__':main()
