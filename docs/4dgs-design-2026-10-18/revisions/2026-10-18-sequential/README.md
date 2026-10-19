# Sequential optimization revision — 18 October 2026

Scope: documentation and prepared prompts only. User request: optimize every phase one aspect at a time, comparing each candidate with the original baseline and the last accepted configuration. No experiments or agents.

## Changes

- Updated the entry document, architecture/contracts and experiment plan to use immutable B0, explicit accepted parent and single-factor candidate. Historical audit and bibliography gained contextual notices; original measured results were retained.
- Added the [sequential protocol](../../06-sequential-optimization.md) and [blank experiment/result card](../../templates/experiment-card.md), including all-stage costs, dual comparisons, scope changes, uncertainty, acceptance and bounded interaction tests.
- Updated the [assignment guide](../../05-agent-prompts.md) and all nine standalone prompts. Independent review now has distinct development and final modes; no intermediate success opens the sealed test or authorizes another phase.
- Preserved SOTA backend alternatives and declared input protocols. I1 is an option awaiting human approval; no weight/environment permission is implied.
- Updated operational repository paths after verifying relocation to `/Users/stefanoroybisignano/Desktop/GaussianSplatting/synthetic-scene-simulator`. Old paths in historical evidence remain provenance.
- Distinguished the original 0.9–1.9-s pilot from the full 0–5.02-s intent recorded in the current repository. A new scope needs its own controls and budgets, not invented B0 extrapolation.

## Preservation and checks

[before.json](before.json) records the initial HEAD/status, document hashes and 94 resident source/configuration/document hashes. [before.zip](before.zip) preserves the previous dossier files byte-for-byte, excluding `.DS_Store` and the new revision directory. [validation.json](validation.json) records this revision's checks; [document validation](../../design-validation.json) is the current entry report.

All 94 protected resident-file hashes matched at the post-edit check, and Git status was unchanged. Pre-existing root README, `docs/4dgs.md`, exporter and exporter-test changes were preserved. This is not a fresh full hash audit of all datasets/checkpoints or FileProvider placeholders. Existing preservation reports remain historical and unmodified.

Only Markdown/JSON/link/fence/required-field checks and source-preservation comparisons were performed. Mermaid source was reviewed, not rendered. No application tests, Blender, CUDA, inference, training, installations, new data, conversion/playback benchmark, agents, commit or push. `Thesis` and `OmniStance` were not written. No performance improvement has been demonstrated by this revision.

The dossier remains local and ignored by the existing repository policy; no ignore rules were changed. Stop for human validation.
