"""A dense export must preserve the clip and every original timestamp."""

import unittest

from tools.resample_4dgs import time_grid


class DenseExportTimeTests(unittest.TestCase):
    def test_121_times_preserve_all_31_original_instants(self):
        rows = time_grid(120)
        self.assertEqual(len(rows), 121)
        self.assertAlmostEqual(rows[0]["source_time_s"], 0.9)
        self.assertAlmostEqual(rows[-1]["source_time_s"], 1.9)
        for index in range(31):
            self.assertAlmostEqual(rows[4 * index]["normalized_time"], index / 30)
        for left, right in zip(rows, rows[1:]):
            self.assertAlmostEqual(right["source_time_s"] - left["source_time_s"], 1 / 120)

    def test_decimation_and_incompatible_grids_are_rejected(self):
        for fps in (0, 15, 29, 31, 119, 120.0):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                time_grid(fps)


if __name__ == "__main__":
    unittest.main()
