# Development and workflows

Run commands from the repository root. Python ≥ 3.11; host workflows require no additional Python dependencies. Blender remains an external executable.

## Configuration

| Directory | Contents |
| --- | --- |
| `configs/scene/` | `static` and `smoke` for a fresh clone; `athlete`, `terrain`, `appearance`, and `presentation` for subsequent stages |
| `configs/motion/` | Jump, rail slide, boardslide, video synchronization, and reference timestamps |
| `configs/capture/` | Frozen-pose acquisitions with 8 or 32 cameras; the 16-camera temporal 4DGS pilot |
| `configs/conditions/` | Matrix of visual variations |
| `configs/tricks/` | Catalog and experimental rotation profiles |

Distances are in meters and times in seconds; fields ending in `*_degrees` use degrees. In refined profiles, Z is vertical and downhill follows −Y. Complete settings depend on the profile: do not assume the initial configuration has the dimensions of later refinements.

Advanced profiles are historical examples linked to local files that are not distributed. Before building a variant, supply the `.blend`, set its repository-relative path and SHA-256 hash, and update any required manifests and video inputs. Do not remove the hash check to accept a different input.

## Commands

The sole entry point is `python3 -B -m snowpark_simulator`. The following commands replace the previous `run_*.py` files; parallel copies of the same implementation are not maintained.

```sh
python3 -B -m snowpark_simulator scene --without-reference
python3 -B -m snowpark_simulator motion build --config configs/motion/boardslide-synced.toml
python3 -B -m snowpark_simulator motion verify --output outputs/RUN_NAME
python3 -B -m snowpark_simulator capture capture --config configs/capture/boardslide-32.toml
python3 -B -m snowpark_simulator capture freeze --output outputs/RUN_NAME
python3 -B -m snowpark_simulator capture verify --output outputs/RUN_NAME
```

These are invocation examples: they do not automatically execute the entire pipeline. Consult `COMMAND --help` before each workflow. Snow comparison requires an explicit selection through `--snow` and `--reason`; completing a render does not select a material automatically.

Analysis tools remain standalone commands, for example:

```sh
python3 -B tools/check_catalog.py --output .local/catalog-check.json
python3 -B tools/encode_preview.py --help
python3 -B tools/prepare_brush_dataset.py --help
```

PNG compositions produced by `tools/*_evidence.py` use actual renders and disclose resizing or cropping. They must not retouch the evidence. Historical cork presets outside the catalog and superseded ad hoc checks are no longer part of the active code.

## Tests and style

```sh
python3 -B -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

Continuous integration (CI) is configured for host checks on Python 3.11 and 3.13, without Blender, private assets, or a reconstruction backend. Actions are pinned to official commits; defining a workflow does not establish that it passed on GitHub. Ruff is a development tool, not a scene dependency. For a real Blender check, use `smoke.toml`: four small renders followed by independent verification of the reopened `.blend`. Running `tests/blender_imports.py` explicitly through Blender also checks imports of the reorganized libraries without creating objects. These checks do not establish GUI navigation or visual quality.

Keep calculations in functions without filesystem access where possible. Add tests for observable invariants: continuity, downhill direction, output isolation, and error propagation. Avoid tests that merely repeat implementation formulas.

Do not import `bpy` in host workflows or start processes at import time. Use `blender_command`, `run_logged`, `within`, and `new_run` for new operations. Validate inputs with explicit exceptions rather than `assert`, which Python can disable with `-O`.

Legacy Blender generators retain some internal assertions, compatibility imports, and assignments with object-creation side effects. The refactor preserves their behavior; lint exceptions are limited to those files. Algorithm changes require scene-specific verification in addition to host tests.

## Local files and public images

`outputs/`, `.tools/`, personal references, and `.local/` are excluded from Git. Chronological reports, three historical presets, and two former README images are preserved locally under `.local/refactor-archive/`, with a migration map. Repository cleanup does not delete validated scenes.

The README displays two images: a scene overview and a motion preview. The results montage and static pose sequence are not duplicated in the project presentation. Deleting files does not rewrite Git history: reducing the size of previously published commits would require a separate operation.
