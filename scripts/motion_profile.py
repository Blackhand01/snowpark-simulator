"""Deterministic cinematic phase curve; no physics claims or Blender dependency."""

import math


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * x * (10 + x * (-15 + 6 * x))


def validate(m):
    for key in [
        "fps",
        "duration_s",
        "takeoff_s",
        "flight_s",
        "prepare_s",
        "recover_s",
        "x_m",
        "start_y_m",
        "end_y_m",
        "height_m",
        "clearance_m",
        "freeze_time_s",
    ]:
        assert type(m[key]) in [int, float] and math.isfinite(m[key]), key
    assert type(m["fps"]) is int and 1 <= m["fps"] <= 120
    assert (
        0
        < m["takeoff_s"]
        < m["prepare_s"]
        < m["takeoff_s"] + m["flight_s"]
        < m["recover_s"]
        < m["duration_s"]
        <= 12
    )
    assert 0 < m["height_m"] <= 8 and 0 < m["clearance_m"] <= 0.1
    assert m["discipline"] == "ski" and m["forward_axis"] == "-Y" and m["up_axis"] == "+Z"
    assert -15 < m["x_m"] < 15 and m["start_y_m"] > m["end_y_m"]
    assert abs(m["start_y_m"]) < 70 and abs(m["end_y_m"]) < 70
    assert 0 <= m["freeze_time_s"] <= m["duration_s"]


def sample(t, m):
    validate(m)
    t = max(0, min(m["duration_s"], t))
    a = m["takeoff_s"]
    b = a + m["flight_s"]
    prep = m["prepare_s"]
    u = max(0, min(1, (t - a) / m["flight_s"]))
    if t < a:
        phase = "entry"
        crouch = 0.025 + 0.065 * smooth(t / a)
    elif t < prep:
        phase = "flight"
        crouch = 0.09 + 0.04 * math.sin(math.pi * u) ** 2
    elif t < b:
        phase = "prepare"
        crouch = 0.09 - 0.06 * smooth((t - prep) / (b - prep))
    elif t < m["recover_s"]:
        phase = "landing"
        crouch = 0.03 + 0.065 * math.sin(math.pi * (t - b) / (m["recover_s"] - b)) ** 2
    else:
        phase = "exit"
        crouch = 0.03 - 0.005 * smooth((t - m["recover_s"]) / (m["duration_s"] - m["recover_s"]))
    # Continuous crouch blend across the preparation boundary.
    if a <= t < prep:
        peak = 0.13
        mid = a + m["flight_s"] * 0.5
        crouch = (
            0.09 + (peak - 0.09) * smooth((t - a) / (mid - a))
            if t <= mid
            else peak + (0.09 - peak) * smooth((t - mid) / (prep - mid))
        )
    return dict(
        t=t,
        phase=phase,
        x=m["x_m"],
        y=m["start_y_m"] + (m["end_y_m"] - m["start_y_m"]) * t / m["duration_s"],
        altitude=m["height_m"] * math.sin(math.pi * u) ** 2,
        crouch=crouch,
        torso_pitch=-0.10 * math.sin(math.pi * u) ** 2,
        ski_pitch=0.035 * math.sin(2 * math.pi * u),
        arm_swing=0.12 * math.sin(math.pi * u) ** 2,
        accessory_pitch=-0.60 - 0.08 * math.sin(math.pi * u) ** 2,
    )
