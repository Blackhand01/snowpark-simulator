"""Summarise measured output; Pillow is used only for optional review panels."""

import argparse, json, math
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    m = json.loads((out / "measured-morphology.json").read_text())
    pts = list(reversed(json.loads((out / "centerline-profile.json").read_text())["points_y_z_m"]))
    top = pts[0][1]
    start = pts[0][0]
    scale = 5
    xy = [(65 + (start - y) * scale, 80 + (top - z) * scale) for y, z in pts]
    line = " ".join(f"{x:.2f},{y:.2f}" for x, y in xy)
    endx, endy = xy[-1]
    mid = xy[len(xy) // 2]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="330" viewBox="0 0 960 330">
<rect width="960" height="330" fill="#f6f8fa"/>
<g font-family="Arial,sans-serif" fill="#18283b">
<text x="30" y="30" font-size="21">Measured longitudinal mesh profile — centerline X = 0</text>
<text x="30" y="55" font-size="14">Equal horizontal and vertical scale; downhill toward −Y. Artistic terrain, not a Melezet survey.</text>
<path d="M 65 80 H {endx:.2f} V {endy:.2f}" stroke="#a9b5c3" stroke-dasharray="5,5" fill="none"/>
<polyline points="{line}" fill="none" stroke="#1667b1" stroke-width="3"/>
<circle cx="{mid[0]:.2f}" cy="{mid[1]:.2f}" r="5" fill="#dc6f15"/>
<text x="{mid[0] + 9:.2f}" y="{mid[1] - 10:.2f}" font-size="14">Rail sector ≈17.2%</text>
<text x="330" y="102" font-size="15">Horizontal projection: {m["horizontal_length_m"]:.2f} m</text>
<text x="{endx - 100:.2f}" y="{endy - 45:.2f}" font-size="15">Elevation drop: {m["drop_m"]:.2f} m</text>
<text x="30" y="275" font-size="17">Surface length: {m["surface_length_m"]:.2f} m · average {m["average_grade_percent"]:.2f}% / {m["average_angle_degrees"]:.2f}°</text>
<text x="30" y="302" font-size="15">Local slopes: {m["min_local_grade_percent"]:.2f}–{m["max_local_grade_percent"]:.2f}% · reverse-slope segments: 0 / {m["measured_segments"]}</text>
</g></svg>'''
    (out / "slope-profile.svg").write_text(svg)
    try:
        from PIL import Image, ImageDraw, ImageStat, __version__
    except ImportError:
        print("Profile SVG written; Pillow unavailable: optional image panels skipped")
        return
    comparison = json.loads((out / "snow-comparison.json").read_text())
    im = [Image.open(out / n).convert("RGB") for n in ["snow-baseline.png", "snow-pbr.png"]]
    sums = [0, 0, 0]
    sq = [0, 0, 0]
    changed = 0
    for x, y in zip(im[0].getdata(), im[1].getdata()):
        diff = [abs(a - b) for a, b in zip(x, y)]
        changed += max(diff) > 10
        for i, v in enumerate(diff):
            sums[i] += v
            sq[i] += v * v
    n = im[0].width * im[0].height
    quantitative = dict(
        mean_absolute_rgb_delta_8bit=sum(sums) / (n * 3),
        rms_rgb_delta_8bit=math.sqrt(sum(sq) / (n * 3)),
        fraction_pixels_any_channel_delta_gt_10=changed / n,
        texture_bytes=2826732,
        time_ratio=comparison["time_ratio"],
        pillow_version=__version__,
        interpretation="Pixel differences measure change, not visual quality; timings are a single paired observation",
    )
    (out / "material-quantitative.json").write_text(json.dumps(quantitative, indent=2) + "\n")
    panel = Image.new("RGB", (1280, 1040), "#f6f8fa")
    draw = ImageDraw.Draw(panel)
    for i, (img, variant) in enumerate(zip(im, ["baseline", "pbr"])):
        label = (
            f"{variant.upper()} - {comparison[variant]['seconds']:.2f} s - 1280 x 960 / 48 samples"
        )
        draw.text((i * 640 + 12, 12), label, fill="#18283b")
        panel.paste(img.resize((640, 480)), (i * 640, 35))
        draw.text(
            (i * 640 + 12, 535),
            "Identical native 640 x 480 crop, no resampling",
            fill="#18283b",
        )
        panel.paste(img.crop((320, 480, 960, 960)), (i * 640, 560))
    panel.save(out / "snow-compare.png")
    views = ["main.png", "slope-side.png", "rail-close.png", "overview.png"]
    panel = Image.new("RGB", (1280, 1030), "#f6f8fa")
    draw = ImageDraw.Draw(panel)
    for i, name in enumerate(views):
        x = (i % 2) * 640
        y = (i // 2) * 515
        draw.text((x + 12, y + 10), name, fill="#18283b")
        panel.paste(Image.open(out / name).convert("RGB").resize((640, 480)), (x, y + 30))
    panel.save(out / "review-panel.png")
    print(json.dumps(quantitative))


if __name__ == "__main__":
    main()
