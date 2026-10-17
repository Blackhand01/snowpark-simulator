"""Run only P1 in a fresh output directory. Python standard library only."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender",default="/Applications/Blender.app/Contents/MacOS/Blender")
    parser.add_argument("--config",type=Path,default=ROOT/"config.toml")
    parser.add_argument("--without-reference", action="store_true",
                        help="Build procedurally without a local reference photograph")
    args=parser.parse_args()
    config=args.config.resolve()
    if not config.is_relative_to(ROOT):raise ValueError("Config must be inside Simulator")
    reference=ROOT/"references/snowpark-rail.png"
    if not args.without_reference and not reference.is_file():raise FileNotFoundError(reference)
    out=ROOT/"outputs"/datetime.datetime.now(datetime.timezone.utc).strftime("p1-%Y%m%dT%H%M%S-%fZ")
    out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(config,out/"config.toml")
    source=out/"source"
    source.mkdir()
    for path in [ROOT/"run.py",ROOT/"scripts/build_scene.py",ROOT/"scripts/verify_scene.py"]:
        shutil.copy2(path,source/path.name)
    inputs=[ROOT/"run.py",ROOT/"scripts/build_scene.py",ROOT/"scripts/verify_scene.py",config]
    if not args.without_reference:inputs.append(reference)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    report=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),output=str(out),input_sha256=hashes,steps=[])
    report_path=out/"execution.json"
    report_path.write_text(json.dumps(report,indent=2)+"\n")
    base=[args.blender,"--background","--offline-mode","--disable-autoexec","--python-exit-code","1"]
    steps=[("build",base+["--python",str(ROOT/"scripts/build_scene.py"),"--","--config",str(out/"config.toml"),"--output",str(out)]),
           ("reopen-verify",base+[str(out/"snowpark.blend"),"--python",str(ROOT/"scripts/verify_scene.py"),"--","--output",str(out)])]
    if args.without_reference:steps[0][1].append("--without-reference")
    for name,command in steps:
        print(name,str(out),flush=True)
        tick=time.monotonic()
        with (out/(name+".log")).open("w") as log:
            proc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800,cwd=ROOT)
        report["steps"].append(dict(name=name,command=command,exit_code=proc.returncode,seconds=time.monotonic()-tick,log=name+".log"))
        report_path.write_text(json.dumps(report,indent=2)+"\n")
        if proc.returncode:raise SystemExit(f"{name} failed ({proc.returncode}); inspect {out}/{name}.log")
    report["status"]="BUILD_AND_REOPEN_VERIFIED"
    report["gui_viewport_verified"]=False
    report_path.write_text(json.dumps(report,indent=2)+"\n")
    print("P1_OUTPUT",str(out),flush=True)


if __name__=="__main__":main()
