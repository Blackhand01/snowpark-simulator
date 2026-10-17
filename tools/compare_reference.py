"""Create an original-left / simulation-right comparison on the source clock."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    out = p.parse_args().output.resolve()
    assert out.is_relative_to(ROOT / "outputs")
    c = tomllib.loads((out / "config.toml").read_text())
    timing = json.loads((out / "reference-timing.json").read_text())
    source = ROOT / c["source"]["reference_video"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == c["source"]["reference_sha256"]
    target = out / "comparison.mp4"
    assert not target.exists()
    snapshot = out / "compare-reference-source.py"
    assert not snapshot.exists()
    shutil.copy2(__file__, snapshot)
    den = timing["time_base_den"]
    graph = (
        f"[0:v:0]scale=648:1080,setsar=1,settb=1/{den}[left];"
        f"[1:v:0]scale=1272:716,pad=1272:1080:0:182:color=0x202020,setsar=1,settb=1/{den}[right];"
        "[left][right]hstack=inputs=2:shortest=1[comparison]"
    )
    command = [
        shutil.which("ffmpeg"),
        "-v",
        "error",
        "-n",
        "-i",
        str(source),
        "-i",
        str(out / "preview.mp4"),
        "-filter_complex",
        graph,
        "-map",
        "[comparison]",
        "-an",
        "-frames:v",
        str(timing["reference_frame_count"]),
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-bf",
        "0",
        "-pix_fmt",
        "yuv420p",
        "-fps_mode",
        "passthrough",
        "-enc_time_base",
        f"1:{den}",
        "-video_track_timescale",
        str(den),
        "-movflags",
        "+faststart",
        str(target),
    ]
    with (out / "compare-reference.log").open("x") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    report = dict(
        command=command,
        exit_code=result.returncode,
        layout="original left, simulation right",
        scope="Original clip only; extended raised-arm runout is in preview.mp4",
    )
    if result.returncode == 0:
        raw = subprocess.check_output(
            [
                shutil.which("ffprobe"),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=pts",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(target),
            ],
            text=True,
        )
        probe = json.loads(raw)
        pts = [f["pts"] for f in probe["frames"]]
        passed = (
            pts == timing["reference_frame_pts"]
            and abs(float(probe["format"]["duration"]) - timing["reference_duration_ticks"] / den)
            < 1e-6
        )
        report.update(
            status="PASS" if passed else "FAIL",
            frames=len(pts),
            exact_pts_match=pts == timing["reference_frame_pts"],
            duration_s=float(probe["format"]["duration"]),
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        )
    (out / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    assert result.returncode == 0 and report["status"] == "PASS", report
    print(json.dumps({k: report[k] for k in ["status", "frames", "exact_pts_match", "duration_s"]}))


if __name__ == "__main__":
    main()
