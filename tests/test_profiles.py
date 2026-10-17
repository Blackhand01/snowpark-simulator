"""Check the existing numerical contracts without Blender or rendering."""

import copy
import json
import math
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from motion_profile import sample
from reference_clock import anchors, approved_time
from terrain_profile import elevation, longitudinal_grade, solve
from trick_profile import sample_trick, validate

from snowpark_simulator.conditions import validate_conditions


class ProfileTests(unittest.TestCase):
    def test_piste_keeps_length_drop_and_downhill_direction(self):
        terrain = tomllib.loads((ROOT / "configs/scene/terrain.toml").read_text())["terrain"]
        profile = solve(terrain)
        length = profile["horizontal_length_m"]
        self.assertAlmostEqual(profile["surface_length_m"], terrain["surface_length_m"], places=6)
        self.assertAlmostEqual(
            elevation(length / 2, profile) - elevation(-length / 2, profile),
            terrain["drop_m"],
            places=6,
        )
        for x in (-terrain["width_m"] / 2, 0, terrain["width_m"] / 2):
            self.assertGreater(
                min(
                    longitudinal_grade(x, -length / 2 + length * i / 200, terrain, profile)
                    for i in range(201)
                ),
                0,
            )

    def test_motion_clamps_to_endpoints(self):
        motion = tomllib.loads((ROOT / "configs/motion/jump.toml").read_text())["motion"]
        self.assertEqual(sample(-1, motion), sample(0, motion))
        self.assertEqual(
            sample(motion["duration_s"] + 1, motion), sample(motion["duration_s"], motion)
        )

    def test_catalog_paths_and_kinematic_profiles_remain_consistent(self):
        catalog = json.loads((ROOT / "configs/tricks/catalog.json").read_text())
        for entry in catalog["entries"]:
            with self.subTest(profile=entry["id"]):
                config = tomllib.loads((ROOT / entry["config"]).read_text())
                validate(config)
                self.assertEqual(config["trick"]["rotation_degrees"], entry["rotation_degrees"])
                for time in (
                    0,
                    config["motion"]["takeoff_s"],
                    config["motion"]["prepare_s"],
                    config["motion"]["duration_s"],
                ):
                    pose = sample_trick(time, config)
                    self.assertTrue(
                        all(math.isfinite(v) for v in pose.values() if type(v) in (int, float))
                    )
                final = sample_trick(config["motion"]["duration_s"], config)
                self.assertAlmostEqual(
                    final["spin"], math.radians(entry["rotation_degrees"]) * entry["direction"]
                )
                self.assertAlmostEqual(final["tilt"], 0)

    def test_reference_clock_is_monotone_and_exact_at_anchors(self):
        timing = json.loads((ROOT / "configs/motion/reference-timing.json").read_text())
        pairs = anchors(timing)
        for time, expected in pairs:
            self.assertAlmostEqual(approved_time(time, timing), expected)
        values = [approved_time(pairs[-1][0] * i / 1000, timing) for i in range(1001)]
        self.assertTrue(all(a <= b for a, b in zip(values, values[1:])))

    def test_render_conditions_and_invalid_inputs(self):
        matrix = json.loads((ROOT / "configs/conditions/matrix.json").read_text())
        self.assertEqual(len(validate_conditions(matrix)), len(matrix["conditions"]))
        for key, value in [
            ("name", "../escape"),
            ("gain", float("nan")),
            ("snow_count", True),
            ("lighting", "unknown"),
        ]:
            invalid = copy.deepcopy(matrix)
            invalid["conditions"][0][key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_conditions(invalid)
        duplicate = copy.deepcopy(matrix)
        duplicate["conditions"].append(duplicate["conditions"][0])
        with self.assertRaises(ValueError):
            validate_conditions(duplicate)


if __name__ == "__main__":
    unittest.main()
