"""Repository paths, immutable run inputs, and source provenance.

All generated artifacts belong to outputs/. Historical .blend files are inputs,
never destinations. Paths are resolved before containment checks, including symlinks.
"""

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def within(path: Path, parent: Path = ROOT, *, directory: bool = False) -> Path:
    """Resolve an existing input and reject paths outside its allowed tree."""
    resolved = path.resolve()
    if not resolved.is_relative_to(parent.resolve()):
        raise ValueError(f"Path must be inside {parent}: {path}")
    if directory:
        if not resolved.is_dir():
            raise NotADirectoryError(resolved)
    elif not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def new_run(prefix: str, root: Path = ROOT) -> Path:
    """Create a unique UTC run directory, including outputs/ on a fresh clone."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", prefix):
        raise ValueError(f"Invalid run prefix: {prefix!r}")
    outputs = root / "outputs"
    outputs.mkdir(exist_ok=True)
    if outputs.is_symlink():
        raise ValueError("outputs/ must be a real directory inside the repository")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    output = outputs / f"{prefix}-{stamp}"
    output.mkdir(exist_ok=False)
    return output


def sha256(path: Path) -> str:
    """Hash large scene files without loading them entirely into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> None:
    """Reject a changed source before executing Blender or an external backend."""
    if sha256(path) != expected:
        raise ValueError(f"Input SHA-256 mismatch: {path}")


def write_json(path: Path, data: object) -> None:
    """Write readable, interoperable JSON; reject NaN and infinity."""
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def snapshot_runtime(destination: Path) -> None:
    """Include the shared host code in each stage's source archive.

    Older workflows also archive their entry script and Blender helpers. A source
    archive would be incomplete if it only kept those now-shared entry points.
    Existing archives are immutable: a changed source requires a fresh attempt.
    """
    package = destination / "snowpark_simulator"
    package.mkdir(exist_ok=True)
    manifest = {}
    for source in sorted(Path(__file__).parent.rglob("*.py")):
        relative = source.relative_to(Path(__file__).parent)
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != source.read_bytes():
                raise ValueError(f"Archived source changed: {source}")
        else:
            shutil.copy2(source, target)
        manifest[f"snowpark_simulator/{relative}"] = sha256(source)
    write_json(destination / "runtime-manifest.json", manifest)
