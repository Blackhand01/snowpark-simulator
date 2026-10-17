"""Encode existing Workbench diagnostic frames using installed ffmpeg."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from reference_clock import pts_filter


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
    assert out.is_relative_to(Path(__file__).resolve().parents[1]/'outputs')
    meta=json.loads((out/'preview.json').read_text())
    binary=shutil.which('ffmpeg');assert binary
    target=out/'preview.mp4';assert not target.exists()
    command=[binary,'-n','-framerate',str(meta['fps']),'-pattern_type','glob','-i',str(out/'preview/*.png')]
    if 'pts_ticks' in meta:
        den=meta['time_base_den'];expression,step=pts_filter(meta['pts_ticks'])
        command += ['-vf',f"settb=1/{den},setpts='{expression}'"]
    command += ['-c:v','libx264','-threads','2','-pix_fmt','yuv420p']
    if 'pts_ticks' in meta:
        command += ['-bf','0','-fps_mode','passthrough','-enc_time_base',f'1:{den}','-video_track_timescale',str(den)]
    command += ['-movflags','+faststart',str(target)]
    t=time.monotonic()
    with (out/'encode-preview.log').open('x') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    result=dict(command=command,exit_code=r.returncode,seconds=time.monotonic()-t,diagnostic_only=True,engine=meta['engine'],input_frames=len(meta['frames']))
    if target.is_file():result.update(bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    if r.returncode == 0 and 'pts_ticks' in meta:
        probe=subprocess.run([shutil.which('ffprobe'),'-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=pts','-show_entries','stream=time_base','-show_entries','format=duration','-of','json',str(target)],check=True,capture_output=True,text=True)
        data=json.loads(probe.stdout)
        pts=[f['pts'] for f in data['frames']]
        passed=(data['streams'][0]['time_base']==f'1/{den}' and pts==meta['pts_ticks'] and abs(float(data['format']['duration'])-meta['duration_ticks']/den)<1e-6)
        result['timestamp_verification']=dict(status='PASS' if passed else 'FAIL',frame_count=len(pts),duration_s=float(data['format']['duration']),exact_pts_match=pts==meta['pts_ticks'])
        assert passed,result['timestamp_verification']
    (out/'encode-preview.json').write_text(json.dumps(result,indent=2)+'\n');assert r.returncode==0


if __name__=='__main__':main()
