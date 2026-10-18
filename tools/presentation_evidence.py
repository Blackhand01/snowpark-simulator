"""Compose snow comparison from executed Blender renders; no image retouching."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat, __version__

    record = json.loads((out / "snow-visibility-comparison.json").read_text())
    assert record["identical_render_contract"]
    files = [out / "snow-before.png", out / "snow-after.png"]
    assert hashlib.sha256(files[0].read_bytes()).hexdigest() == record["before"]["sha256"]
    assert hashlib.sha256(files[1].read_bytes()).hexdigest() == record["after"]["sha256"]
    images = [Image.open(f).convert("RGB") for f in files]
    assert images[0].size == images[1].size == (1920, 1440)
    # Same foreground patch in both unmodified images, away from skier and rail.
    crop = (80, 980, 880, 1380)
    panel = Image.new("RGB", (1600, 1140), "#f4f6f8")
    draw = ImageDraw.Draw(panel)
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 17)
    for i, (im, label) in enumerate(
        zip(images, ["BEFORE / dominant PBR", "AFTER / restored grooming grooves"])
    ):
        x = i * 800
        draw.text((x + 16, 12), label, font=font, fill="#172432")
        draw.text(
            (x + 16, 44),
            "Identical camera, lighting and settings",
            font=small,
            fill="#43556a",
        )
        panel.paste(im.resize((800, 600), Image.Resampling.LANCZOS), (x, 70))
        draw.text(
            (x + 16, 686),
            "Same foreground crop / original pixels",
            font=small,
            fill="#43556a",
        )
        panel.paste(im.crop(crop), (x, 730))
    panel.save(out / "snow-comparison.png")
    rgb_mae = ImageStat.Stat(ImageChops.difference(images[0].crop(crop), images[1].crop(crop))).mean
    delta = record["after"]["seconds"] / record["before"]["seconds"] - 1
    stats = dict(
        crop_box=crop,
        rgb_mean_absolute_difference_8bit=rgb_mae,
        render_seconds_before=record["before"]["seconds"],
        render_seconds_after=record["after"]["seconds"],
        render_delta_percent=100 * delta,
        limitations="One pair, different wall-clock times; not a performance benchmark or realism score. Before render reused byte-for-byte.",
        processing="Layout, proportional resize, identical crop; no colour or detail adjustment.",
        pillow=__version__,
    )
    (out / "comparison-metrics.json").write_text(json.dumps(stats, indent=2) + "\n")
    archive = out / "source" / "evidence"
    archive.mkdir(exist_ok=False)
    shutil.copy2(__file__, archive / Path(__file__).name)
    print("SNOW_COMPARISON_WRITTEN", json.dumps(stats))


if __name__ == "__main__":
    main()
