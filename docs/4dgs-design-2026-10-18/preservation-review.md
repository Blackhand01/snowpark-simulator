# Preservation and audit-execution boundary

Comparison timestamp: **2026-10-18 13:09:12 UTC**. Later workspace activity is outside this fixed snapshot. Full comparison data: [preservation-review.json](preservation-review.json).

## Actions performed by this audit

- Read repository source, configurations, historical reports and selected existing visual evidence.
- Read the library registry/notes, attempt bounded local PDF text extraction into `/tmp/4dgs-design-reading`, and consult primary online papers/repositories/documentation. Library content was not edited.
- Create design documents, prompts, source inventory and preservation evidence **only in `docs/4dgs-design-2026-10-18/`**. No implementation file was authored or edited.
- Check local document links/code fences and source/metadata preservation. These document checks are not application tests or experimental validation.

No agents, installs, scene rendering, data capture, optimizer steps, training, model inference, export, viewer interaction, commit or push were executed by this audit. Player installation/conversion/UI artifacts appearing concurrently belong to separate workspace activity, not this task.

## Initial inventory and comparison

Initial inventory: 8,456 files, 3,972,415,455 logical bytes; exclusions are recorded in [preservation-before.json](preservation-before.json). It includes metadata for historical artifacts and 81 byte hashes for resident source/configuration/documentation files. `.git`, `.tools`, `target`, `.ruff_cache`, `__pycache__` and this new design directory were excluded. It is not a full historical artifact content-hash snapshot.

At comparison:

- **0 original files missing**.
- **80/81 stored source hashes matched**. The sole content change was `docs/4dgs.md`, whose concurrent export/player documentation was read and preserved, not reverted.
- **47 original paths had mtime or size differences**; only `docs/4dgs.md` changed size, from 11,724 to 13,148 bytes. Other timestamp changes, including readable/hydrated artifacts and the export test, do not prove content changes. Their unchanged sizes are not full integrity proof either.
- **6,929 added paths** were observed, primarily the concurrent Chronosplat run's dependencies/data/cache, plus completed export reports. The machine-readable comparison retains their names; this audit did not create or modify them.
- Existing untracked `tools/export_4dgs.py` and `tests/test_4dgs_export.py` were preserved. No index changes were made.
- Free disk at this snapshot was 29,024,092,160 bytes (~27.03 GiB), a changing system observation, not a future allocation guarantee.

FileProvider `dataless` placeholders prevented a fresh full hash of the scene/checkpoints and many PDF reads within the bounded audit. Historical hashes are labelled as historical throughout. Hydration/read attempts may coincide with metadata changes; causality is not asserted. The new player records also changed during the audit, so their interpretation is explicitly timestamped in [the baseline addendum](01-baseline-audit.md#concurrent-player-addendum--bounded-snapshot-not-this-audits-execution).

The existing `.gitignore` intentionally ignores chronological documentation directories. The dossier exists locally but is not staged or tracked. No ignore rule was modified. A future publication/version-control decision is separate from this design task.

## Verification limits

No full Blender reopen, CUDA execution, local application test suite or new visual benchmark was performed. Prior 42-test success and prior training/export metrics remain historical. Markdown link/fence checks establish document consistency only; Mermaid diagrams were source-checked, not rendered with a newly installed renderer. This is a preservation-aware design delivery, not a claim that the entire concurrently changing workspace is unchanged.
