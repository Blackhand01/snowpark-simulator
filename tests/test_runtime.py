"""Host invariants: paths, immutability, explicit execution and lazy imports."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib import import_module
from pathlib import Path
from unittest.mock import patch

from snowpark_simulator.artifacts import (
    new_run,
    require_hash,
    sha256,
    snapshot_runtime,
    within,
    write_json,
)
from snowpark_simulator.cli import WORKFLOWS, main
from snowpark_simulator.execution import BLENDER_FLAGS, blender_command, resolve_blender, run_logged


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_new_clone_and_repeated_runs_get_distinct_directories(self):
        first = new_run("scene", self.root)
        second = new_run("scene", self.root)
        self.assertNotEqual(first, second)
        self.assertTrue(first.is_dir() and second.is_dir())
        self.assertEqual(first.parent, self.root / "outputs")

    def test_output_prefix_cannot_escape_repository(self):
        for prefix in ("../escape", "/absolute", "", "with space"):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                new_run(prefix, self.root)
        self.assertFalse((self.root / "outputs").exists())

    def test_output_symlink_is_rejected(self):
        outside = self.root / "elsewhere"
        outside.mkdir()
        (self.root / "outputs").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            new_run("scene", self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_containment_resolves_parent_traversal_and_symlinks(self):
        allowed = self.root / "allowed"
        allowed.mkdir()
        outside = self.root / "source.blend"
        outside.write_bytes(b"original")
        (allowed / "link.blend").symlink_to(outside)
        for path in (allowed / "../source.blend", allowed / "link.blend"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                within(path, allowed)
        with self.assertRaises(FileNotFoundError):
            within(allowed / "missing", allowed)

    def test_hash_rejects_changed_input(self):
        source = self.root / "source.blend"
        source.write_bytes(b"original")
        digest = sha256(source)
        require_hash(source, digest)
        source.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            require_hash(source, digest)

    def test_json_does_not_write_nonfinite_metrics(self):
        with self.assertRaises(ValueError):
            write_json(self.root / "invalid.json", {"score": float("nan")})

    def test_runtime_archive_includes_workflows_and_rejects_drift(self):
        snapshot_runtime(self.root)
        manifest = json.loads((self.root / "runtime-manifest.json").read_text())
        self.assertIn("snowpark_simulator/workflows/scene.py", manifest)
        for relative, digest in manifest.items():
            self.assertEqual(sha256(self.root / relative), digest)
        snapshot_runtime(self.root)
        (self.root / "snowpark_simulator/execution.py").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Archived source changed"):
            snapshot_runtime(self.root)


class ExecutionTests(unittest.TestCase):
    def test_command_is_offline_and_preserves_arguments_with_spaces(self):
        args = blender_command(
            "/path with spaces/blender",
            Path("/scene script.py"),
            ["--output", "/output path"],
            scene=Path("/input scene.blend"),
        )
        self.assertEqual(args[1:6], list(BLENDER_FLAGS))
        self.assertEqual(args[6], "/input scene.blend")
        self.assertEqual(args[-2:], ["--output", "/output path"])

    def test_explicit_missing_blender_never_falls_back(self):
        with patch.dict(os.environ, {"SNOWPARK_BLENDER": sys.executable}):
            with self.assertRaises(FileNotFoundError):
                resolve_blender("/definitely/missing/blender")
            self.assertEqual(resolve_blender(), str(Path(sys.executable).resolve()))

    def test_process_failure_is_recordable_and_log_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "stage.log"
            result = run_logged(
                [sys.executable, "-c", 'print("failure evidence"); raise SystemExit(7)'],
                log,
                timeout=10,
                cwd=Path(directory),
            )
            self.assertEqual(result.returncode, 7)
            self.assertIn("failure evidence", log.read_text())
            before = log.read_bytes()
            with self.assertRaises(FileExistsError):
                run_logged([sys.executable, "-c", 'print("overwrite")'], log, timeout=10)
            self.assertEqual(log.read_bytes(), before)

    def test_timeout_is_an_error_with_a_retained_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "stage.log"
            with self.assertRaises(subprocess.TimeoutExpired):
                run_logged([sys.executable, "-c", "import time; time.sleep(5)"], log, timeout=0.05)
            self.assertIn("exceeded", log.read_text())

    def test_host_imports_do_not_execute_processes_or_import_blender(self):
        with patch("subprocess.run", side_effect=AssertionError("import executed a process")):
            for module, _ in WORKFLOWS.values():
                import_module(module)
        self.assertNotIn("bpy", sys.modules)

    def test_every_command_can_show_help_without_blender(self):
        with patch("subprocess.run", side_effect=AssertionError("help executed a process")):
            for command in WORKFLOWS:
                with self.subTest(command=command), redirect_stdout(io.StringIO()) as output:
                    with self.assertRaises(SystemExit) as result:
                        main([command, "--help"])
                    self.assertEqual(result.exception.code, 0)
                    self.assertIn("usage:", output.getvalue())

    def test_cli_reports_invalid_paths_without_a_traceback(self):
        from snowpark_simulator.workflows import scene

        with (
            patch.object(scene, "resolve_blender", return_value="/test/blender"),
            redirect_stderr(io.StringIO()) as error,
        ):
            with self.assertRaises(SystemExit) as result:
                main(["scene", "--without-reference", "--config", "/outside/config.toml"])
        self.assertEqual(result.exception.code, 2)
        self.assertIn("Path must be inside", error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
