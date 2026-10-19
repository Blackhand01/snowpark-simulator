# Stage review — blank preparation template

Status: NOT ASSIGNED / NO EXECUTION. Use before each new factor selection; read [use-case screening](../07-use-case-literature-review.md) and [sequential protocol](../06-sequential-optimization.md).

- Stage, scope epoch, B0 and accepted parent: UNRESOLVED.
- Actual bottleneck/evidence; missing measurement and how to obtain it: UNRESOLVED.
- Snowpark constraints: static snow/rail, moving body/equipment, shadows, rail depth ordering, small target, fast motion, limited memory. State which matter here.
- Unchanged-parent control and simple alternative: UNRESOLVED.
- Literature candidates: compare at least two credible alternatives where available; otherwise document search/access gaps. Record exact version, section/table/code, content read versus metadata-only, official source and independent evidence.
- For each candidate: mechanism; assumptions; why transferable; contradictory evidence; images/calibration/masks/depth/poses/weights; I0/I1/assisted status; preprocessing/training/render costs separately; memory/storage/transfers; hardware; code/commit/submodules; licenses; integration effort; compatibility still unknown.
- Distinguish paper fact, local historical observation, engineering inference, proposed measurement and verified implementation. A title, abstract or fast-rendering headline cannot establish low total cost.
- Recommended factor with exact before/after values: UNRESOLVED. Explain why the other candidates are deferred/rejected, without assuming the baseline backend must remain.
- Dependencies and unavoidable coupled changes: UNRESOLVED. Label inseparable packages; no individual-effect claim for a bundled implementation.
- Minimum discriminating experiment: UNRESOLVED. Keep all other factors fixed; require B0 and parent comparisons, quality non-regression, total-cost boundaries, uncertainty, budgets and stop conditions from the experiment card.
- Human selection/authorization: PENDING. This review alone does not authorize implementation, downloads, inference, capture, training or agents.
