# Literature, implementation audit and hardware-aware design

> Application update: the [sequential protocol](06-sequential-optimization.md) applies SOTA candidates to every resource-relevant stage, one treatment at a time. The existing backend is a control, not a permanent constraint. Compare each selected method against both B0 and the accepted parent, charging dependencies, preprocessing, integration and deployment. This documentation revision adds no new literature-performance claims or experimental evidence.


## Reading coverage and evidence rules

The search started with the actual local `Thesis/references/papers` registry and files. Its 105 registry records are not 105 readable PDFs: 42 PDF files map to 41 work identifiers. Bounded extraction succeeded for eight files; 34 timed out, mostly FileProvider placeholders. Selected missing content was read through primary arXiv versions and official repositories. The [inventory](local-paper-inventory.md) separates byte access, metadata, content reading and online substitutions. No paper was added to or changed in the library.

The mandatory HUGS, GauHuman, GART, SC-GS and EDGS works were investigated through primary external sources because their PDFs were not found in this library inventory. “HUGS” here means **Human Gaussian Splats** by Kocabas et al., not similarly named urban reconstruction projects. “4DGS” is also ambiguous: HUST's deformable canonical 3D Gaussians are different from native four-dimensional Gaussian primitives.

**NR** below means not established from the consulted source, not zero and not necessarily absent from all supplementary material. No candidate was installed or benchmarked here. Numerical rows retain the source's hardware, task and resolution when verified; no throughput is scaled to T4 or M1. Preprocessing time, training time, encoded size, decoded memory and playback speed are separate quantities.

## Core candidate cards

### HUST 4DGaussians — reusable baseline

[Paper v3, §4, §5 and Appendix A](https://arxiv.org/html/2310.08528v3); [official code](https://github.com/hustvl/4DGaussians).

Canonical 3D Gaussians plus HexPlane spatial/temporal features and a small multilayer perceptron predict deformation. It needs calibrated RGB over time and initialization; the local pilot replaces generic dataset assumptions. The paper's 82 fps at 800×800 on RTX 3090 is rendering evidence, not a free-Colab training guarantee. This is the only candidate with direct snowpark training/export evidence, and that evidence **fails quality**. Use it to identify whether fitting, generalization or data support is the limiting factor. Root Apache-2.0 does not erase retained Inria restrictions or licenses of dependencies. The existing adapter avoids simple-knn but still uses a CUDA rasterizer.

### HUGS — joint human and scene reconstruction

[Paper v1, §3–4](https://arxiv.org/pdf/2311.17910); [official repository](https://github.com/apple-aiml-research/ml-hugs); [license](https://github.com/apple/ml-hugs/blob/main/LICENSE).

Jointly models an articulated human and static scene from monocular video, using an SMPL body prior and learned skinning adjustments for clothing. Useful conceptually for separation and consistent body motion. It requires body initialization/poses and scene reconstruction; boots, skis and rail are not automatically covered by the human prior. Author headline: roughly 30 min optimization and 60 fps; the GPU/resolution and complete preprocessing cost corresponding to those headlines were not established in this audit. Official setup includes CUDA, SMPL assets and scene data preparation; AMASS is relevant to novel animation, not a mandatory input for our reconstruction. Apple source terms, SMPL, datasets and renderer require separate checks. Integration: high; no independent snowpark evidence.

### GauHuman — efficient articulated foreground

[Paper, §3, §4, Appendices A/D](https://arxiv.org/html/2312.02973v1); [code](https://github.com/skhu101/GauHuman); [S-Lab license](https://github.com/skhu101/GauHuman/blob/main/LICENSE.md).

SMPL-initialized Gaussians, pose/linear-blend-skinning refinement and body-aware density control yield compact humans. Inputs include RGB, calibration, masks and body pose/shape initialization; body estimation is not free. Authors report approximately 1–2 min optimization, ~13k Gaussians / ~3.5 MB and up to 189 fps; reported rendering is on RTX 3090. This does not include a verified total cost of fitting the synthetic skier's body. The official environment uses PyTorch/CUDA and custom alpha rasterization/KNN components. S-Lab terms are noncommercial; SMPL and rasterizer terms remain separate. Strong A3 candidate if articulated identity and pose fit are reliable. Unmodelled equipment and loose clothing remain risks; no local reproduction.

### GART — articulated template plus residual flexibility

[Paper, §3, §4.1, Table 1](https://arxiv.org/pdf/2311.16099); [code](https://github.com/JiahuiLei/GART).

Combines template articulation with learned latent bones to handle deviations such as clothing, using monocular observations and estimated pose tracks. Human SMPL and animal SMAL templates are external priors, not geometry recovered without assumptions. Table 1 includes ~2.5 min and 30 s variants; the paper also uses **test-time pose refinement**, which cannot consume final target RGB under our protocol. The repo timing setup is RTX 3080 laptop 16 GB, i9-11950H and 64 GB host memory; >150 fps is reported at 540×540. Root MIT does not cover the body assets or inherited rasterizer. Integration: high; fit quality and preprocessing costs remain unresolved.

### SC-GS — sparse motion controls

[Paper v2, §4 and experiments](https://arxiv.org/html/2312.14937v2); [official code/README](https://github.com/CVMI-Lab/SC-GS).

Learns sparse control nodes with time-dependent rigid transforms, blending their influence onto Gaussians and regularizing local rigidity. This can express articulated motion without requiring a human skeleton, but does not guarantee physical joints or rigid skis. Input is calibrated temporal RGB and initialization; optional alpha masks change the protocol. The README's example uses 512 controls and a 10k-step control pretraining stage; this stage must be charged. Complete train time, peak memory, final bytes and comparable fps were not established here. Custom depth/alpha CUDA rasterization and nearest-neighbor dependencies add maintenance. Root MIT is insufficient to clear submodules. Integration: medium/high, A2 fallback after diagnostic evidence, not the first port.

### EDGS — dense correspondence initialization

[Paper v2, §3, Appendix A and sparse-view Appendix B](https://arxiv.org/html/2504.13204v2); [code/README](https://github.com/CompVis/EDGS); [license](https://github.com/CompVis/EDGS/blob/main/LICENSE.txt).

Uses dense image correspondences, triangulation and attribute initialization to reduce subsequent Gaussian optimization/densification. Suitable for the static scene or **same-time** foreground views; treating a moving athlete across time as static violates triangulation assumptions. Requires calibrated image pairs and RoMa pretrained matching. Appendix A reports ~120 s initialization and ~15 GB peak on an A100 80 GB; this exceeds the proposed 12 GiB guard before considering a T4 port. Sparse-view tables do not show universal dominance. Repository and paper speed ratios refer to differing settings/versions; no ratio is adopted here. Noncommercial source terms and matcher/weights must be cleared separately. Consider bounded pair selection only after quality/cost profiling, not an assumed cheap initializer.

## Alternatives and component-level evidence

See the [focused DSD-GS/Swift4D assessment and phase matrix](07-use-case-literature-review.md) for the current applicability gate. DSD-GS official project still labels code TBA at this revision; full backend integration remains unverified.

| Work and primary locator | Pertinent content and conditions | Input / integration / disposition |
| --- | --- | --- |
| [DSD-GS, §4.1–4.4, Eq.18, Appendix C](https://arxiv.org/html/2605.30863v1) | Feed-forward initialization and flow-based static/dynamic separation; static geometry is frozen and cached. Author tests: RTX 5090, 1352×1014, ~10 min training / >700 fps headline | Pretrained encoder and flow are extra dependencies. Eq.18 composites the whole dynamic layer over a static image: that ordering is unsuitable as a general rail-occlusion assumption. Reuse separation principle; retain joint depth sorting. Official [project](https://young0tete.github.io/dsd-gs/); complete code/license/weights availability not verified |
| [MoDec-GS, §4, Appendix B/E](https://arxiv.org/html/2501.03714v3) | Global anchor + local Gaussian deformation with temporal interval adaptation; compact representation | [Code](https://github.com/skwak-kaist/MoDec-GS), HUST/Scaffold-based CUDA. Appendix E gives 1.2 h, 28 MB, 23.8 fps at 536×960 on RTX A6000; not a low-training-cost promise. Full license chain and peak memory NR. Defer backend replacement |
| [SpeeDe3DGS v4, method, Tables 3–4, Appendix A.2](https://arxiv.org/html/2506.07917v4) | Temporal sensitivity pruning, temporal sampling and motion grouping | [Code](https://github.com/tuallen/speede3dgs); training on A5000 or A6000 depending on dataset, rendering RTX 3090. Grouping can lose PSNR (D-NeRF 33.27→31.70 in the cited comparison). Peak/bytes/preprocessing for our use NR. Do not prune a foreground already missing detail |
| [4C4D, §3 and Appendix B](https://arxiv.org/html/2604.04063v1) | Sparse four-camera native 4D representation with visibility-driven neural opacity decay | [Code](https://github.com/yangzf-1023/4C4D); MASt3R initialization and 500-step warmup. Requires calibrated videos and pretrained geometry prior. Full timing/memory/fps NR in consulted passages. MIT root, retained Inria license and MASt3R terms are separate. Not a HUST configuration switch |
| [SparseGS v4, §3–4](https://arxiv.org/html/2312.00206v4) | Static sparse-view geometry regularization, depth correlation, nearby-view warping, diffusion supervision and floater pruning | Locally read PDF; calibrated images, COLMAP/MVS, Marigold depth and Stable Diffusion 2.1 priors. 10k/30k steps for 12/24 views; full resource envelope NR. No dynamic-body evidence. Diffusion-generated plausibility is not measured recovery; exclude from first pipeline |
| [MaskGaussian v3, §3–4, Tables 2–3](https://arxiv.org/html/2412.20522v3) | Probabilistic Gaussian existence and masked rasterization permit gradients to temporarily absent primitives; these are not semantic foreground masks | [Code](https://github.com/kaikai23/MaskGaussian); modified CUDA. RTX 4090, 30k steps. Table 2 Mip-NeRF360 Ours-γ: 17:52 / 274.2 MB; Table 3 Ours-γ peaks 3.53–6.45 GB across five scenes. Late static compression candidate; temporal transfer and component licenses unverified |
| [HAC++ v4, §III and Tables X–XI](https://arxiv.org/html/2501.12255v4) | Anchor-based entropy/context coding optimizes rate versus distortion; compressed bytes differ from decoded representation | [Code](https://github.com/YihangChen-ee/HAC-plus); Scaffold-based CUDA/codec dependencies, license chain unverified. L40s 48 GB: 2,278–2,384 s training, 10.87–11.66 GB peak in Table X. Codec is not a free post-export HUST compressor. Defer until storage is demonstrated limiting |
| [TC3DGS v2, §4 and §11](https://arxiv.org/html/2412.05700v2) | Temporally consistent pruning, gradient-aware quantization and trajectory keypoint interpolation compress Dynamic 3D Gaussians | [Official project](https://ahmad-jarrar.github.io/tc-3dgs/); code/license chain and full hardware/time/memory/fps envelope unverified here. Needs temporal Gaussian identity; sports experiments use foreground/background masks. It includes fitting changes, not just a generic PLY zip operation. Defer until fidelity is acceptable; compressed trajectories cannot preserve arbitrary occlusion changes without checking |
| [Faster-GS, §4.3–4.4 and Table 5](https://arxiv.org/html/2602.09999v1) | Per-Gaussian backward work, fused optimization and locality target redundant memory/compute; changing invisible-primitive updates can alter quality | [Code](https://github.com/nerficg-project/faster-gaussian-splatting); native 4D branch differs from HUST. Preload is excluded from reported training timing. CUDA integration and license chain need audit; use profiling principles, not copied headline speedups |
| [R5DGS, §III–IV](https://arxiv.org/abs/2605.25909v1) | Object identity plus rigid-centroid motion propagation targets extrapolation of rigid objects | Locally read five-page PDF. SAM2/DEVA masks, CLIP and TRACE physics dependencies; author +11 fps on RTX 4090 is extrapolation speed, not training reduction. Code/license/full costs unverified. Concept applies to equipment, not an entire articulated skier or moving shadow |
| [MotionScale, §3, §4.1/4.5](https://arxiv.org/html/2603.29296v1) | Cluster-based motion and separate transient shadow Gaussians address foreground/background interference | RTX 4090 experiments; estimated depth/cameras, SAM2 and CoTracker3 inputs. [Official project](https://hrzhou2.github.io/motion-scale-web/). Total preprocessing/train/peak/size/fps and license chain NR here. Its photometrically fitted moving shadow primitives differ from our proposed geometry-fixed appearance residual |
| [Instant4D, §3.2–3.3, Table 2](https://arxiv.org/html/2510.01119v1) | Depth-based initialization, motion separation and voxel filtering reduce an initially dense native-4D representation | MegaSAM plus depth priors add preprocessing/weights. Hardware and end-to-end cost corresponding to its timing claims were not verified, so no speed forecast is adopted. Code/license audit incomplete; partial alternative screen, not a selected module |
| [4DAnyone, August 2026, §3.2–3.3](https://arxiv.org/html/2608.20335v1) | Generates multiview human videos with a diffusion model conditioned on recovered skeletons, then reconstructs 4DGS | [Official project](https://4danyone.github.io). Pretrained generator, pose recovery and synthetic novel views are substantial priors; full resources/weights/license NR here. Excluded from I0 and first pipeline: plausible generated hidden appearance is not independent reconstruction evidence |

Additional screening: the locally read street-scene moving-object paper (`p0019`) suppresses moving objects; that objective conflicts with retaining the athlete. R3D3, OmniGS, HyperGaussians and RT-Splatting were abstract/introduction-screened, not treated as validated pipeline modules. Other recent registry entries remain partial reading leads; they are not recommendations. EdgeGaussians' name does not establish embedded-hardware applicability.

## Resource and reproducibility gaps

For **every candidate** above, a blank/NR field must become a recorded value or an explicit blocker before integration. Required candidate ledger: exact code commit and submodules; checkpoint/asset identity; dataset and image size; preprocessing wall time/peak host and device memory; fitting wall and GPU-active time; total CUDA device memory, allocated/reserved memory; optimizer checkpoints versus inference files versus encoded archive bytes; decode cold start; sustained fps and p95 frame latency at a declared resolution. Paper-reported values are useful to reject implausible budgets, not to fill this ledger.

Independent evidence is limited. GauHuman Appendix D re-runs GART **without test-time pose refinement**, showing that protocols materially affect apparent comparisons; this is external to GART's authors, but still not our domain or an independent audit of all methods. MoDec and SpeeDe compare other dynamic methods, but hardware and evaluation settings differ. EDGS compares SparseGS in sparse-view settings, not dynamic sports. No inspected independent reproduction establishes our snowpark quality or T4 end-to-end cost for HUGS, GauHuman, GART, SC-GS or EDGS. The current local HUST run is direct independent execution evidence with a negative quality result.

License screening is technical dependency accounting, not legal clearance. SMPL/SMAL registration and research terms, body-pose estimator weights, AMASS/NeuMan/ZJU data, RoMa/MASt3R weights, retained Gaussian rasterizer licenses and player codecs remain separate from top-level MIT/Apache labels. A Wingtra professional's private research does not automatically establish permitted commercial redistribution. No proprietary body asset or new weight was downloaded here.

## Benini and PULP: principles with traceable attribution

PULP means **Parallel Ultra-Low Power**, an ecosystem of programmable processors, accelerators and software. Its relevant lesson is to choose the algorithm, memory organization and execution schedule together; it is not a compatible M1/CUDA renderer package.

Primary sources read:

- [DORY, v3, memory hierarchy and tiling sections](https://arxiv.org/html/2008.07127v3), [official project](https://github.com/pulp-platform/dory): constraint-based tiling, explicit transfers, double buffering and layout-aware execution for embedded neural-network inference. The full paper's author list does **not** include Luca Benini; describe it as PULP ecosystem work, not a Benini-authored result.
- [TrainDeeploy, §II–IV](https://arxiv.org/html/2603.09511v1): **Luca Benini is a coauthor**. Full forward/backward graph planning, tiling, static memory allocation and parameter-efficient adaptation target heterogeneous low-power systems. Its low-rank adaptation reduces trainable state; it does not automatically remove backward activations or translate into a Gaussian deformation implementation.
- [PLiNIO, §II–IV](https://arxiv.org/html/2307.09488v1): combines task loss with explicit complexity costs for neural-network architecture, pruning and precision exploration. Transfer the constrained-search discipline; its operators and cost models are not validated for Gaussian sorting/rasterization.

| Documented principle | Proposed snowpark application (our inference) | Required measurement / guard |
| --- | --- | --- |
| Eliminate repeated work; jointly plan compute and memory | Fit static geometry once; deform foreground only; retain calibrated transforms | Measure static/foreground kernels separately; verify rail depth ordering |
| Locality and reuse; layout-aware tiles | Contiguous Gaussian arrays, small camera/image cache; batch export by unique time | Count decoded copies, transfer bytes and synchronization; no claim of cache speedup without a profile |
| Reduce expensive memory movement | Upload one verified archive, unpack on Colab local disk, download checkpoints in bounded bundles | Include compression, hashing, transfers and cold-load time, not just optimization loop |
| Respect memory hierarchy | GPU working set, bounded CPU staging, disk persistence; small viewer frame window | Total device use and host/browser resident memory; stop on pressure, not merely CUDA OOM |
| Parallel work within a bounded working set | One host decode worker initially; increase only if measured starvation and headroom | M1 unified memory competes with Blender/browser/OS; more workers can increase copies |
| Precision as an accuracy/cost choice | FP32 reference first; later quantize storage/SH or test mixed precision separately | Geometry/quaternion/opacity and thin-ski regressions; CUDA kernel support unverified |
| Explicit constrained optimization | Meet Q1–Q6, then compare total cold/warm cost; retain Pareto alternatives | No addition/multiplication of separately published speedups; remeasure combinations |

An energy claim requires integrated power over time with defined device/system boundaries and instrumentation. Neither GPU-seconds, allocated bytes, theoretical traffic nor elapsed time measures joules. Power and energy are **not measured** here; do not advertise energy savings. Embedded DMA schedules, integer kernels and accelerator-specific compilers are inspirations, not installable shortcuts for this Mac or Colab.

## Visualization and service constraints

[SuperSplat documentation](https://developer.playcanvas.com/user-manual/supersplat/editor/import-export/) supports numbered PLY sequences but describes full-scene loading per frame. It is the existing short-sequence reference. [Chronosplat](https://github.com/tcwilsonart/Chronosplat) provides a temporal frame-window player; its historical public-demo interaction is not validation on the skier. Start with existing players and parity checks, not a custom viewer. SOG/SPZ compression, a camera animation and a moving Gaussian sequence are distinct capabilities.

The [baseline addendum](01-baseline-audit.md#concurrent-player-addendum--bounded-snapshot-not-this-audits-execution) records a subsequently observed concurrent SOG conversion and skier playback snapshots with stalls. This is more current than the earlier public-demo-only report, but still not a complete quality/memory/fps acceptance result.

[Colab's official FAQ](https://research.google.com/colaboratory/faq.html) gives no guaranteed free GPU type or runtime. Plan an active notebook with restartable work, no keepalive, background-service workaround, purchases or assumed Drive mount. A historical T4 is a measured past resource; current availability is **UNVERIFIED**. [gsplat](https://github.com/nerfstudio-project/gsplat) is a CUDA renderer library and possible later engineering alternative, not proof of a working M1 training path.
