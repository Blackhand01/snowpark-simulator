"""Exercise workflow wiring and failure propagation with a fake process runner.

These tests do not render or train. They catch stale filenames, incomplete source
archives and incorrect stage selection after reorganizing the repository.
"""

import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from snowpark_simulator.artifacts import ROOT
from snowpark_simulator.execution import Execution


class WorkflowTests(unittest.TestCase):
    def test_scene_runs_build_then_reopen_and_records_both(self):
        from snowpark_simulator.workflows import scene

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with (
                patch.object(scene, "new_run", return_value=output),
                patch.object(scene, "resolve_blender", return_value="/test/blender"),
                patch.object(scene, "run_logged", return_value=Execution(0, 0.01)) as execute,
                redirect_stdout(io.StringIO()),
            ):
                scene.main(["--without-reference"])
            self.assertEqual(execute.call_count, 2)
            commands = [call.args[0] for call in execute.call_args_list]
            self.assertIn("--without-reference", commands[0])
            self.assertIn(str(output / "snowpark.blend"), commands[1])
            report = json.loads((output / "execution.json").read_text())
            self.assertEqual([s["name"] for s in report["steps"]], ["build", "reopen-verify"])
            self.assertFalse(report["gui_viewport_verified"])
            self.assertTrue((output / "source/snowpark_simulator/workflows/scene.py").is_file())

    def test_scene_stops_on_build_failure(self):
        from snowpark_simulator.workflows import scene

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with (
                patch.object(scene, "new_run", return_value=output),
                patch.object(scene, "resolve_blender", return_value="/test/blender"),
                patch.object(scene, "run_logged", return_value=Execution(7, 0.01)) as execute,
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    scene.main(["--without-reference"])
            self.assertEqual(execute.call_count, 1)
            self.assertNotIn("status", json.loads((output / "execution.json").read_text()))

    def test_all_reopen_workflows_use_existing_scripts_and_archive_runtime(self):
        for name in ("athlete", "terrain", "appearance", "presentation", "motion", "capture"):
            with self.subTest(workflow=name), tempfile.TemporaryDirectory() as directory:
                workflow = import_module("snowpark_simulator.workflows." + name)
                output = Path(directory)
                (output / "config.toml").write_text("")
                (output / "p2_config.toml").write_text("")
                with (
                    patch.object(workflow, "within", return_value=output),
                    patch.object(workflow, "resolve_blender", return_value="/test/blender"),
                    patch.object(
                        workflow, "run_logged", return_value=Execution(0, 0.01)
                    ) as execute,
                    redirect_stdout(io.StringIO()),
                ):
                    workflow.main(["verify", "--output", str(output)])
                command = execute.call_args.args[0]
                script = Path(command[command.index("--python") + 1])
                self.assertTrue(script.is_file(), script)
                self.assertEqual(script.parent, ROOT / "scripts")
                journals = (output / "execution.jsonl").read_text().splitlines()
                self.assertEqual(json.loads(journals[-1])["exit_code"], 0)
                manifests = list(output.rglob("runtime-manifest.json"))
                self.assertTrue(manifests, name)
                for manifest in manifests:
                    self.assertTrue(
                        (manifest.parent / "snowpark_simulator/workflows" / f"{name}.py").is_file()
                    )

    def test_appearance_geometry_flag_is_only_valid_for_verify(self):
        from snowpark_simulator.workflows import appearance

        with (
            patch.object(appearance, "resolve_blender", return_value="/test/blender"),
            self.assertRaises(SystemExit),
        ):
            appearance.main(["build", "--geometry-only"])

    def test_local_documentation_links_exist(self):
        for document in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]:
            # Private historical documents are explicitly outside the public docs.
            if document.name not in ("README.md", "architecture.md", "development.md"):
                continue
            links = re.findall(r"\]\(([^)]+)\)", document.read_text())
            for target in links:
                if "://" in target or target.startswith("#"):
                    continue
                path = target.split("#", 1)[0]
                with self.subTest(document=document.name, target=target):
                    self.assertTrue((document.parent / path).exists())

    def test_unaccepted_condition_inputs_do_not_create_a_run(self):
        from snowpark_simulator.workflows import conditions

        matrix = json.loads((ROOT / "configs/conditions/matrix.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "outputs/dataset"
            baseline = root / "outputs/baseline"
            dataset.mkdir(parents=True)
            baseline.mkdir()
            matrix.update(dataset="outputs/dataset", baseline="outputs/baseline")
            config = root / "matrix.json"
            config.write_text(json.dumps(matrix))
            (baseline / "artifact-verification.json").write_text('{"status":"FAIL"}')
            with (
                patch.object(conditions, "ROOT", root),
                patch.object(conditions, "resolve_blender", return_value="/test/blender"),
                patch.object(conditions, "new_run") as create,
                patch.object(conditions, "run_logged") as execute,
            ):
                with self.assertRaisesRegex(ValueError, "has not passed"):
                    conditions.main(["--config", str(config)])
            create.assert_not_called()
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
