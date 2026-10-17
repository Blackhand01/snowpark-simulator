"""Validate controlled rendering profiles without opening Blender or datasets."""

import math
import re


def validate_conditions(matrix: dict) -> list[str]:
    """Return unique names after checking the supported visual-effect ranges."""
    names = []
    for profile in matrix["conditions"]:
        name = profile["name"]
        if not re.fullmatch("[a-z_]+", name) or name in names:
            raise ValueError(f"Invalid or duplicate condition name: {name!r}")
        names.append(name)
        if profile["lighting"] not in {"baseline", "sun", "overcast", "backlight"}:
            raise ValueError(f"Unsupported lighting for {name}")
        bounds = {
            "exposure_ev": (-3, 3),
            "gain": (0.25, 4),
            "haze_density": (0, 0.1),
            "blur_exposure_s": (0, 1 / 30),
            "snow_texture_strength": (0, 0.25),
            "snow_relief_m": (0, 0.01),
        }
        for field, (low, high) in bounds.items():
            value = profile[field]
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"{name}.{field} must be between {low} and {high}")
        temperature = profile["white_balance_kelvin"]
        if temperature is not None and (
            type(temperature) not in (int, float) or not 2000 <= temperature <= 12000
        ):
            raise ValueError(f"Invalid white balance for {name}")
        if type(profile["snow_count"]) is not int or not 0 <= profile["snow_count"] <= 1000:
            raise ValueError(f"Invalid snow count for {name}")
        if not 0 < profile["snow_brightness"] <= 2:
            raise ValueError(f"Invalid snow brightness for {name}")
        if type(profile["occluder"]) is not bool or type(profile["seed"]) is not int:
            raise ValueError(f"Invalid occluder or seed for {name}")
    if not names:
        raise ValueError("At least one condition is required")
    return names
