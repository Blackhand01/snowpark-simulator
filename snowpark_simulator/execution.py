"""Blender discovery, offline command construction, and measured subprocesses."""

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .artifacts import ROOT

MACOS_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
BLENDER_FLAGS = (
    "--background",
    "--offline-mode",
    "--disable-autoexec",
    "--python-exit-code",
    "1",
)


def add_blender_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--blender",
        help="Blender executable; defaults to SNOWPARK_BLENDER, PATH, then the macOS app",
    )


def resolve_blender(explicit: str | None = None) -> str:
    """An explicit choice must work; never silently fall back to another binary."""
    chosen = explicit or os.environ.get("SNOWPARK_BLENDER")
    if chosen:
        candidate = shutil.which(chosen)
    else:
        candidate = shutil.which("blender")
        if not candidate and Path(MACOS_BLENDER).is_file():
            candidate = MACOS_BLENDER
    if not candidate or not os.access(candidate, os.X_OK):
        raise FileNotFoundError("Blender unavailable. Set --blender or SNOWPARK_BLENDER.")
    return str(Path(candidate).resolve())


def blender_command(
    executable: str,
    script: Path,
    arguments: Sequence[str],
    *,
    scene: Path | None = None,
) -> list[str]:
    """Build an argv list, without a shell or automatic script execution."""
    command = [executable, *BLENDER_FLAGS]
    if scene is not None:
        command.append(str(scene))
    return [*command, "--python", str(script), "--", *map(str, arguments)]


@dataclass(frozen=True)
class Execution:
    """Process completion is not scene verification or scientific acceptance."""

    returncode: int
    seconds: float


def run_logged(
    command: Sequence[str],
    log: Path,
    *,
    timeout: float,
    cwd: Path = ROOT,
    env: Mapping[str, str] | None = None,
) -> Execution:
    """Execute once, measuring wall time and refusing to overwrite an older log.

    A timeout remains an error and leaves the process output in the stage log.
    Non-zero return codes are returned so workflow-specific reports can record
    the failure before stopping subsequent stages.
    """
    started = time.monotonic()
    with log.open("x", encoding="utf-8") as stream:
        try:
            process = subprocess.run(
                list(command),
                cwd=cwd,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            stream.write(f"\nProcess exceeded {timeout} seconds.\n")
            raise
    return Execution(process.returncode, time.monotonic() - started)


def append_execution(path: Path, **record: object) -> None:
    """Keep every attempt in an append-only JSON Lines journal."""
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, allow_nan=False) + "\n")
