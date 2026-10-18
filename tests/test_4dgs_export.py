"""Timestamp selection must not turn repeated camera views into repeated frames."""

import unittest

from tools.export_4dgs import unique_timestamps


class ExportTimestampTests(unittest.TestCase):
    def test_repeated_camera_views_produce_one_ordered_frame_per_timestamp(self):
        records = [dict(sample_index=i, time=i / 30) for i in reversed(range(31))] * 2
        indices = unique_timestamps(records)
        self.assertEqual([records[i]["sample_index"] for i in indices], list(range(31)))
        self.assertTrue(all(index < 31 for index in indices))

    def test_incomplete_time_grid_is_rejected(self):
        with self.assertRaises(ValueError):
            unique_timestamps([dict(sample_index=i, time=i / 30) for i in range(30)])

    def test_inconsistent_duplicate_timestamp_is_rejected(self):
        records = [dict(sample_index=i, time=i / 30) for i in range(31)]
        for invalid in (float("nan"), 0.5):
            with self.subTest(time=invalid), self.assertRaises(ValueError):
                unique_timestamps(records + [dict(sample_index=0, time=invalid)])


if __name__ == "__main__":
    unittest.main()
