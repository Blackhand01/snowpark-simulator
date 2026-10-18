"""Decode RGB, validate partitions/assets, and draw the calibrated camera layout."""

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("output", type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    root = Path(__file__).resolve().parents[1]
    assert out.is_relative_to(root / "outputs")
    from PIL import Image

    data = json.loads((out / "dataset.json").read_text())
    cameras = json.loads((out / "cameras.json").read_text())["frames"]
    checks = {}
    for f in cameras:
        path = out / f["file_path"]
        assert path.resolve().is_relative_to(out)
        checks[f["camera_id"] + "_hash"] = (
            hashlib.sha256(path.read_bytes()).hexdigest() == f["sha256"]
        )
        with Image.open(path) as im:
            im.load()
            checks[f["camera_id"] + "_RGB_dimensions"] = (
                im.mode == "RGB" and list(im.size) == f["resolution"]
            )
        checks[f["camera_id"] + "_same_pose"] = (
            f["pose_sha256"] == data["pose_sha256"]
            and f["pose_id"] == data["pose_id"]
            and f["frame"] == data["frame"]
        )
    checks["unique_image_hashes"] = len({f["sha256"] for f in cameras}) == len(cameras)
    for split in ["train", "test"]:
        tf = json.loads((out / f"transforms_{split}.json").read_text())
        ids = {f["camera_id"] for f in tf["frames"]}
        checks[split + "_partition_consistent"] = (
            ids
            == set(data[split + "_camera_ids"])
            == {f["camera_id"] for f in cameras if f["split"] == split}
        )
        byid = {f["camera_id"]: f for f in cameras}
        checks[split + "_transforms_match"] = all(
            f["transform_matrix"] == byid[f["camera_id"]]["camera_to_world_blender"]
            and f["pose_id"] == data["pose_id"]
            and (out / f["file_path"]).is_file()
            for f in tf["frames"]
        )
    assets = json.loads((root / "assets/polyhaven/snow_01/1k/manifest.json").read_text())["files"]
    expected = {f["file"]: f["sha256"] for f in assets}
    checks["three_packed_texture_hashes_match_source_manifest"] = len(
        data["textures"]
    ) == 3 and all(expected.get(f["name"]) == f["packed_sha256"] for f in data["textures"])
    result = dict(
        status="PASS" if all(checks.values()) else "FAIL",
        checks=checks,
        limits="Format, hash and partition checks only; no reconstruction-quality guarantee",
    )
    target = out / "format-verification.json"
    assert not target.exists()
    target.write_text(json.dumps(result, indent=2) + "\n")
    assert result["status"] == "PASS", checks
    os.environ["MPLCONFIGDIR"] = str(
        root / "outputs/sequence-auto-20261017T155416-617400Z/mpl-cache"
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 7))
    for f in cameras:
        mat = f["camera_to_world_blender"]
        x, y = mat[0][3], mat[1][3]
        color = "#d97706" if f["split"] == "test" else "#2563eb"
        ax.scatter(x, y, c=color, s=70)
        ax.annotate(
            f["camera_id"] + " (" + f["split"] + ")",
            (x, y),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )
        ax.arrow(
            x,
            y,
            -mat[0][2] * 1.5,
            -mat[1][2] * 1.5,
            color=color,
            head_width=0.16,
            length_includes_head=True,
        )
    ax.plot([0, 0], [-3, 3], lw=5, color="#444444", label="Rail nominale 6 m")
    if "athlete_origin_world_m" in data:
        x, y, _ = data["athlete_origin_world_m"]
    else:
        timeline = (root / data["source"]["blend"]).parent / "timeline.csv"
        rows = list(csv.DictReader(timeline.open()))
        row = next(r for r in rows if int(r["frame"]) == data["frame"])
        x, y = float(row["x"]), float(row["y"])
    ax.scatter(
        x,
        y,
        marker="*",
        c="#16a34a",
        s=150,
        label="Athlete origin, pose " + data["pose_id"],
    )
    ax.set_aspect("equal")
    ax.set_xlim(-15, 15)
    ax.set_ylim(-15, 15)
    ax.grid(alpha=0.2)
    ax.legend(loc="lower right")
    ax.set_xlabel("World X [m]")
    ax.set_ylabel("World Y [m]")
    ax.set_title(
        f"{len(cameras)} camere — {len(data['train_camera_ids'])} training, {len(data['test_camera_ids'])} test; una sola posa statica"
    )
    fig.tight_layout()
    for ext in ["png", "svg"]:
        path = out / f"camera-layout.{ext}"
        assert not path.exists()
        fig.savefig(path, dpi=150)
    plt.close(fig)
    if len(cameras) > 8:
        for offset in range(0, len(cameras), 16):
            fig, axes = plt.subplots(4, 4, figsize=(12, 10))
            for ax in axes.flat:
                ax.axis("off")
            for ax, entry in zip(axes.flat, cameras[offset : offset + 16]):
                with Image.open(out / entry["file_path"]) as im:
                    ax.imshow(im)
                ax.set_title(entry["camera_id"] + " / " + entry["split"], fontsize=9)
            fig.tight_layout()
            target = out / f"contact-sheet-{offset // 16 + 1:02d}.png"
            assert not target.exists()
            fig.savefig(target, dpi=120)
            plt.close(fig)
    print("PASS", len(checks), "format checks; camera layout generated")


if __name__ == "__main__":
    main()
