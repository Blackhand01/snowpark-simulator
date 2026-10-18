"""Camera/time split safety without Blender, CUDA or optional Python packages."""

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from snowpark_simulator.pilot4d import group, source_frame, validate_records, write_json
from tools.colab_4dgs import initial_stamp_cameras


class PilotContractTests(unittest.TestCase):
    def records(self):
        return [
            dict(
                camera_index=camera,
                sample_index=sample,
                source_frame=source_frame(sample),
                source_time_s=(source_frame(sample) - 1) / 120,
                time=sample / 30,
                group=group(camera, sample),
            )
            for camera in range(16)
            for sample in range(31)
        ]

    def test_complete_capture_has_four_disjoint_groups(self):
        self.assertEqual(
            validate_records(self.records()),
            {"train": 300, "validation": 62, "test_spatial": 62, "test_temporal": 72},
        )

    def test_final_camera_never_enters_fit_at_any_time(self):
        for sample in range(31):
            self.assertEqual(group(3, sample), "test_spatial")
            self.assertEqual(group(14, sample), "test_spatial")

    def test_withheld_time_never_enters_training(self):
        for camera in range(16):
            for sample in (3, 7, 11, 15, 19, 23):
                self.assertNotEqual(group(camera, sample), "train")

    def test_moving_final_record_into_train_is_rejected(self):
        records = self.records()
        next(r for r in records if r["group"] == "test_spatial")["group"] = "train"
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_duplicate_record_cannot_hide_missing_view(self):
        records = self.records()
        records[-1] = copy.deepcopy(records[0])
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_recovery_accepts_partial_records_but_fit_requires_complete_capture(self):
        records = self.records()[:19]
        self.assertEqual(sum(validate_records(records, complete=False).values()), 19)
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_recovery_rejects_duplicate_and_mislabeled_records(self):
        records = self.records()[:19]
        with self.assertRaises(ValueError):
            validate_records(records + [copy.deepcopy(records[0])], complete=False)
        records[0]["group"] = "test_spatial"
        with self.assertRaises(ValueError):
            validate_records(records, complete=False)

    def test_frozen_time_metadata_is_rejected(self):
        records = self.records()
        for record in records:
            record["time"] = 0
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_wrong_frame_rate_is_rejected(self):
        records = self.records()
        records[0]["source_time_s"] = records[0]["source_frame"] / 30
        with self.assertRaises(ValueError):
            validate_records(records)

    def test_bounds_are_explicit(self):
        for camera, sample in ((16, 0), (-1, 0), (0, 31), (0, -1)):
            with self.assertRaises(ValueError):
                group(camera, sample)
        self.assertEqual((source_frame(0), source_frame(30)), (109, 229))

    def test_evidence_cannot_overwrite_a_previous_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.json"
            write_json(path, {"value": 1})
            with self.assertRaises(FileExistsError):
                write_json(path, {"value": 2})
            self.assertIn('"value": 1', path.read_text())


class InitialStampCameraTests(unittest.TestCase):
    def test_plain_camera_list_keeps_all_initial_views_in_order(self):
        cameras = [SimpleNamespace(time=t) for t in (0.5, 0.0, 1.0, 0.0)]
        selected = initial_stamp_cameras(cameras)
        self.assertEqual(selected, [cameras[1], cameras[3]])
        self.assertIs(selected[0], cameras[1])

    def test_small_timestamp_roundoff_is_accepted(self):
        cameras = [SimpleNamespace(time=t) for t in (1e-10, -1e-10, 1 / 30)]
        self.assertEqual(initial_stamp_cameras(cameras), cameras[:2])

    def test_missing_initial_time_stops_instead_of_changing_initialization(self):
        with self.assertRaises(ValueError):
            initial_stamp_cameras([SimpleNamespace(time=0.5)])


if __name__ == "__main__":
    unittest.main()
