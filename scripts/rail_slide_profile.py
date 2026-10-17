"""Reference rail slide timing, separate from the historical cork generator.

Angles and timing are artistic estimates, not measurements from monocular video.
Airborne height is solved in world space between measured scene support heights.
"""

import math
from motion_profile import smooth


def validate(c):
    m, r = c["motion"], c["rail_slide"]
    assert isinstance(m["fps"], int) and 24 <= m["fps"] <= 120
    times = [
        0,
        r["entry_takeoff_s"],
        r["rail_contact_s"],
        r["rail_release_s"],
        r["snow_contact_s"],
        r["compression_peak_s"],
        r["recovered_s"],
        m["duration_s"],
    ]
    assert all(math.isfinite(t) for t in times)
    assert all(a < b for a, b in zip(times, times[1:]))
    assert m["duration_s"] <= 12 and 0 < m["clearance_m"] < 0.03
    assert -70 < m["end_y_m"] < -6 < 6 < m["start_y_m"] < 70
    assert abs(r["slide_yaw_degrees"]) == 90
    assert 0 <= r["torso_counterrotation"] <= 0.8
    assert 9 <= r["gravity_m_s2"] <= 10
    assert 1 <= c["render"]["preview_stride"] <= m["fps"]
    assert all(abs(t * m["fps"] - round(t * m["fps"])) < 1e-6 for t in times)
    if r.get("style") == "boardslide":
        assert "air_trick" not in c and "trick" not in c, (
            "Boardslide cannot contain a cork rotation"
        )
        assert m["forward_axis"] == "-Y" and m["up_axis"] == "+Z"
        assert r["slide_yaw_degrees"] == 90
        assert 0 <= r["max_exit_rise_m"] <= 0.03
        assert 0 < r["snow_contact_s"] - r["rail_release_s"] <= r["max_exit_flight_s"] <= 0.65
    if "switch_start_s" in r:
        assert "air_trick" not in c and "trick" not in c
        assert (
            r["rail_contact_s"] + 0.16
            < r["switch_start_s"]
            < r["switch_end_s"]
            < r["rail_release_s"] - 0.1
        )
        assert 0.3 <= r["switch_end_s"] - r["switch_start_s"] <= 0.7
        assert r["switch_yaw_degrees"] == -r["slide_yaw_degrees"]
        assert 0 <= r["switch_lift_m"] <= 0.05
        assert all(
            abs(r[k] * m["fps"] - round(r[k] * m["fps"])) < 1e-6
            for k in ["switch_start_s", "switch_end_s"]
        )
    if "air_trick" in c:
        k = c["air_trick"]
        assert k["family"] == "double_cork" and type(k["rotations"]) is int and k["rotations"] == 2
        for value in k.values():
            if isinstance(value, (int, float)):
                assert math.isfinite(value)
        assert 50 <= k["axis_tilt_degrees"] <= 75
        assert -180 <= k["axis_azimuth_degrees"] <= 180
        assert 0.8 <= k["pivot_height_m"] <= 1.0
        assert 0.18 <= k["compact_crouch_m"] <= 0.24
        assert 0.15 <= k["start_delay_s"] <= 0.4
        assert 0.15 <= k["landing_prepare_s"] <= 0.4
        assert (
            r["snow_contact_s"] - r["rail_release_s"] - k["start_delay_s"] - k["landing_prepare_s"]
            >= 1.3
        )


def blend(t, a, b, va, vb):
    return va + (vb - va) * smooth((t - a) / (b - a))


def sample(t, c):
    m, r = c["motion"], c["rail_slide"]
    t = max(0.0, min(m["duration_s"], t))
    a, b, d, e, peak, recover = [
        r[k]
        for k in (
            "entry_takeoff_s",
            "rail_contact_s",
            "rail_release_s",
            "snow_contact_s",
            "compression_peak_s",
            "recovered_s",
        )
    ]
    yaw = math.radians(r["slide_yaw_degrees"])
    exit_yaw = math.radians(r.get("switch_yaw_degrees", r["slide_yaw_degrees"]))
    rail_lift = 0.0
    if t < a:
        phase = "approach"
        crouch = blend(t, max(0, a - 0.35), a, 0.09, 0.18)
        angle = 0.0
        pitch_mix = 0.0
        spread = 0.10
    elif t < b:
        phase = "entry_hop"
        u = (t - a) / (b - a)
        angle = yaw * smooth(u)
        pitch_mix = smooth(u)
        crouch = blend(t, a, b, 0.18, 0.13) + 0.025 * math.sin(math.pi * u) ** 2
        spread = blend(t, a, b, 0.10, 0.27)
    elif t < d:
        phase = "rail_slide"
        u = (t - b) / (d - b)
        angle = yaw
        pitch_mix = 1.0
        # Absorb entry, settle, then flex slightly to prepare the exit.
        crouch = (
            blend(t, b, b + 0.16, 0.13, 0.17)
            if t < b + 0.16
            else blend(t, b + 0.16, d - 0.18, 0.17, 0.12)
            if t < d - 0.18
            else blend(t, d - 0.18, d, 0.12, 0.16)
        )
        spread = 0.27 + 0.025 * math.sin(math.pi * u) ** 2
        if "switch_start_s" in r:
            start, end = r["switch_start_s"], r["switch_end_s"]
            if t < start:
                phase = "rail_slide_knees_left"
            elif t < end:
                phase = "rail_reorientation"
                v = (t - start) / (end - start)
                angle = blend(t, start, end, yaw, exit_yaw)
                # A small unweighting keeps the skis above the tube as their
                # orientation passes through longitudinal. No aerial inversion.
                rail_lift = r["switch_lift_m"] * math.sin(math.pi * v) ** 2
                crouch -= 0.07 * math.sin(math.pi * v) ** 2
                spread += 0.025 * math.sin(math.pi * v) ** 2
            else:
                phase = "rail_slide_knees_right"
                angle = exit_yaw
    elif t < e:
        phase = "exit_drop" if r.get("style") == "boardslide" else "exit_hop"
        angle = blend(t, d, e - 0.10, exit_yaw, 0.0)
        pitch_mix = blend(t, d, e, 1.0, 0.0)
        crouch = (
            blend(t, d, d + 0.14, 0.16, 0.065)
            if t < d + 0.14
            else blend(t, d + 0.14, e, 0.065, 0.09)
        )
        spread = blend(t, d, e, 0.27, 0.16)
    elif t < recover:
        phase = "landing_absorption"
        angle = 0.0
        pitch_mix = 0.0
        crouch = (
            blend(t, e, peak, 0.09, 0.225) if t < peak else blend(t, peak, recover, 0.225, 0.09)
        )
        spread = blend(t, e, recover, 0.16, 0.10)
    else:
        phase = "runout"
        angle = 0.0
        pitch_mix = 0.0
        crouch = 0.09
        spread = 0.10
    s = dict(
        t=t,
        phase=phase,
        x=0.0,
        y=m["start_y_m"] + (m["end_y_m"] - m["start_y_m"]) * t / m["duration_s"],
        yaw=angle,
        pitch_mix=pitch_mix,
        crouch=crouch,
        torso_pitch=0.12,
        torso_yaw=-angle * r["torso_counterrotation"],
        arm_spread=spread,
        arm_swing=0.05,
        ski_pitch=0.0,
        accessory_pitch=-0.85,
    )
    if "switch_start_s" in r:
        s["rail_lift"] = rail_lift
    if "air_trick" in c:
        k = c["air_trick"]
        start = d + k["start_delay_s"]
        finish = e - k["landing_prepare_s"]
        s["air_spin"] = 2 * math.pi * k["rotations"] * smooth((t - start) / (finish - start))
        if d < t < e:
            s["phase"] = (
                "double_cork"
                if start <= t <= finish
                else "exit_launch"
                if t < start
                else "landing_prepare"
            )
            s["crouch"] = (
                blend(t, d, start + 0.10, 0.16, k["compact_crouch_m"])
                if t < finish - 0.20
                else blend(t, finish - 0.20, e, k["compact_crouch_m"], 0.09)
            )
            s["arm_spread"] = (
                blend(t, d, start + 0.10, 0.27, 0.065)
                if t < finish - 0.20
                else blend(t, finish - 0.20, e, 0.065, 0.16)
            )
    return s


def ballistic(t, start, end, z0, z1, gravity):
    """Fixed world-space parabola, independent of the terrain under the flight."""
    duration = end - start
    velocity = (z1 - z0) / duration + 0.5 * gravity * duration
    dt = t - start
    return z0 + velocity * dt - 0.5 * gravity * dt * dt
