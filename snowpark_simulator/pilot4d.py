"""Neutral camera/time contract for the bounded synthetic 4DGS pilot.

This module imports neither Blender nor a GPU library. Training code must never
receive records assigned to the final spatial/temporal test groups.
"""

import hashlib
import json
import math
from pathlib import Path

BACKEND_COMMIT = "843d5ac636c37e4b611242287754f3d4ed150144"
SOURCE = "outputs/boardslide-synced-20261017T182924-532391Z/snowpark-motion.blend"
SOURCE_SHA256 = "a8d42cad61740dc8e963b3f0d3bcb241149effe9db80a1014b742bf5dd32cccb"
VALIDATION_CAMERAS = frozenset((7, 10))
TEST_CAMERAS = frozenset((3, 14))
WITHHELD_TIMES = frozenset((3, 7, 11, 15, 19, 23))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: object) -> None:
    """New evidence only: reruns must use a new directory."""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def group(camera_index: int, sample_index: int) -> str:
    if not 0 <= camera_index < 16 or not 0 <= sample_index < 31:
        raise ValueError("Pilot requires camera 0..15 and time sample 0..30")
    if camera_index in VALIDATION_CAMERAS:
        return "validation"
    if camera_index in TEST_CAMERAS:
        return "test_spatial"
    return "test_temporal" if sample_index in WITHHELD_TIMES else "train"


def source_frame(sample_index: int) -> int:
    if not 0 <= sample_index < 31:
        raise ValueError("Time sample outside the approved one-second clip")
    return 109 + 4 * sample_index


def validate_plan(plan: dict) -> None:
    if plan["source"] != SOURCE or plan["source_sha256"] != SOURCE_SHA256:
        raise ValueError("Unexpected approved scene")
    if plan["backend_commit"] != BACKEND_COMMIT:
        raise ValueError("Backend revision changed")
    if plan["resolution"] != [640, 480] or len(plan["cameras"]) != 16:
        raise ValueError("Pilot resolution/camera count changed")
    if len(plan["time_samples"]) != 31:
        raise ValueError("Pilot time coverage changed")
    if len({c["id"] for c in plan["cameras"]}) != 16:
        raise ValueError("Duplicate camera ID")
    for i, item in enumerate(plan["time_samples"]):
        if item["source_frame"] != source_frame(i):
            raise ValueError("Source-frame/time correspondence changed")
        if not math.isclose(item["normalized_time"], i / 30, abs_tol=1e-12):
            raise ValueError("Clip time must be normalized to [0,1]")


def validate_records(records: list[dict], *, complete: bool = True) -> dict[str, int]:
    keys = {(r["camera_index"], r["sample_index"]) for r in records}
    if len(keys) != len(records) or len(records) > 496 or not records:
        raise ValueError("Expected unique camera/time records within the pilot")
    if complete and len(records) != 496:
        raise ValueError("Expected exactly 496 unique camera/time records")
    counts: dict[str, int] = {}
    for record in records:
        expected = group(record["camera_index"], record["sample_index"])
        if record["group"] != expected:
            raise ValueError("Image assigned to the wrong split")
        if record["source_frame"] != source_frame(record["sample_index"]):
            raise ValueError("Invalid source-frame mapping")
        if not math.isclose(record["time"], record["sample_index"] / 30, abs_tol=1e-12):
            raise ValueError("Invalid normalized time")
        if not math.isclose(
            record["source_time_s"], (record["source_frame"] - 1) / 120, abs_tol=1e-12
        ):
            raise ValueError("Invalid scene time")
        counts[expected] = counts.get(expected, 0) + 1
    if complete and counts != {
        "train": 300,
        "validation": 62,
        "test_spatial": 62,
        "test_temporal": 72,
    }:
        raise ValueError(f"Unexpected image counts: {counts}")
    return counts
