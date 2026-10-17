"""Explicit cinematic off-axis rotation; never an angular-momentum model."""

import math
from pathlib import PurePosixPath
from motion_profile import sample, smooth, validate as validate_motion


def validate(c):
    m = c["motion"]
    k = c["trick"]
    validate_motion(m)
    assert isinstance(c["source"]["blend"], str) and c["source"]["blend"]
    source = PurePosixPath(c["source"]["blend"])
    assert (
        not source.is_absolute()
        and ".." not in source.parts
        and source.parts[0] == "outputs"
        and source.suffix == ".blend"
    )
    digest = c["source"]["sha256"]
    assert (
        isinstance(digest, str)
        and len(digest) == 64
        and all(ch in "0123456789abcdef" for ch in digest)
    )
    for key in ["width", "height", "samples", "threads", "seed"]:
        assert type(c["render"][key]) is int and c["render"][key] >= 0
    assert 64 <= c["render"]["width"] <= 4096 and 64 <= c["render"]["height"] <= 4096
    assert 1 <= c["render"]["samples"] <= 256 and 1 <= c["render"]["threads"] <= 8
    families = {
        "single_cork": 1,
        "frontside_cork": 1,
        "backside_cork": 1,
        "rail_to_cork": 1,
        "double_cork_experimental": 2,
        "triple_cork_experimental": 3,
    }
    assert k["family"] in families
    for field in [
        "rotation_degrees",
        "direction",
        "axis_tilt_degrees",
        "axis_azimuth_degrees",
        "compact_crouch_m",
        "pivot_height_m",
    ]:
        assert type(k[field]) in [int, float] and math.isfinite(k[field]), field
    assert type(k["rotation_degrees"]) is int and k["rotation_degrees"] in (
        [1080]
        if k["family"] == "triple_cork_experimental"
        else [720]
        if k["family"] == "double_cork_experimental"
        else [360, 540, 720]
    )
    assert type(k["direction"]) is int and k["direction"] in [-1, 1]
    if k["family"] == "frontside_cork":
        assert k["direction"] == 1
    if k["family"] == "backside_cork":
        assert k["direction"] == -1
    assert 5 <= k["axis_tilt_degrees"] <= 65
    assert -180 <= k["axis_azimuth_degrees"] <= 180
    release = k.get("axis_release_start_fraction", 0.7)
    assert type(release) in [int, float] and math.isfinite(release) and 0.2 <= release <= 0.9
    assert 0.10 <= k["compact_crouch_m"] <= 0.24
    assert 0.7 <= k["pivot_height_m"] <= 1.1
    assert k["discipline"] == "ski" and k["entry_direction"] == "world -Y"
    for field in ["reference_orientation", "direction_convention", "exit_pose"]:
        assert isinstance(k[field], str) and k[field]
    assert m["height_m"] >= 2.0 and m["flight_s"] >= 2.0
    if k["family"] == "rail_to_cork":
        assert abs(m["x_m"] + 0.19) < 1e-6 and abs(m["start_y_m"] - 1) < 1e-6
        speed = (m["start_y_m"] - m["end_y_m"]) / m["duration_s"]
        assert abs(m["start_y_m"] - speed * m["takeoff_s"] + 2) < 1e-6
        assert (
            k["rail_contact"]
            == "left ski centered on tube; right ski unsupported; cinematic balance"
        )


def sample_trick(t, c):
    validate(c)
    m = c["motion"]
    k = c["trick"]
    s = sample(t, m)
    u = max(0, min(1, (t - m["takeoff_s"]) / m["flight_s"]))
    prep = k.get("axis_release_start_fraction", (m["prepare_s"] - m["takeoff_s"]) / m["flight_s"])
    # Gradually remove axis tilt before touchdown, including odd half rotations.
    tilt = math.radians(k["axis_tilt_degrees"]) * (1 - smooth((u - prep) / (1 - prep)))
    s.update(
        spin=math.radians(k["rotation_degrees"]) * k["direction"] * smooth(u),
        tilt=tilt,
        axis_azimuth=math.radians(k["axis_azimuth_degrees"]),
    )
    s["crouch"] += (k["compact_crouch_m"] - 0.13) * math.sin(math.pi * u) ** 2
    s["ski_pitch"] *= math.sin(math.pi * u) ** 2
    return s


def quaternion(s):
    from mathutils import Quaternion, Vector

    tilt = Quaternion(
        Vector((math.cos(s["axis_azimuth"]), math.sin(s["axis_azimuth"]), 0)), s["tilt"]
    )
    return tilt @ Quaternion((0, 0, 1), s["spin"]) @ tilt.conjugated()
