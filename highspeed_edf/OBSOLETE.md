# OBSOLETE INDEX — read this before trusting any older file

**Current authority:** `design/PHASE15_DESIGN_SPEC.md` and
`design/PHASE15_CONTROL_SURFACES.md`. If any older file contradicts those two,
**the design docs win and the older file is obsolete.**

The files below are kept only as a traceability trail (how we got here). They
describe **superseded** configurations and must not be used to size or build
anything. Several were authored against a 90 mm geared FA4119 concept, an
18 kg / 11.5 kg mass basis, a 75 cm² frontal-area gate, and a CdA of 0.0009 m² —
all of which have been superseded.

## Superseded configuration facts (do NOT reuse)

| Old assumption | Value in old files | Current value |
|---|---|---|
| Motors | 6× stock FA4119 350 Kv, geared 2.35–2.95:1 | 6× **rewound 4-pole inrunner, direct drive** |
| Fan diameter | 90 mm OD | **80 mm OD / 40 mm hub** |
| Duct layout | either | **two side-by-side ducts, NOT coaxial** |
| Mass basis | 18 kg (rev 2) → 11.5 kg → 10.5 kg | **4.3–6.72–8.5 kg incl. 1 kg payload (§16)** |
| Frontal-area gate | 75 cm² | **242–270–296 cm² (battery-dominated, fan is a passthrough)** |
| CdA | 0.0009 m² | **0.0008–0.0015–0.0030 m², unresolved (design spec §8)** |
| Cruise power | 12.93 kW at 720 km/h | **4–8 kW band (2.7 floor / 10.5 poor inlet)** |
| Result | — | superseded by Phase 14/15 |

## Obsolete files and folders

| Path | Status | Superseded by |
|---|---|---|
| `design_state.json` | **OBSOLETE** (rev 2, 18 kg, 80 mm) | `design/PHASE15_DESIGN_SPEC.md` |
| `designs/design_state_r4_geometry_candidate.json` | **OBSOLETE** (90 mm, 10.5 kg) | design spec §4–§9 |
| `requirements/requirements.yaml`, `requirements_r2.yaml`, `requirements_r3_candidate.yaml` | **OBSOLETE** | design spec §1–§2 |
| `configs/phase2_architecture.json` … `phase9_geometry_mass_screen.json` | **OBSOLETE** | design spec + `phase15/` |
| `reports/phase1-feasibility.md` … `phase9-geometry-mass-envelope.md` | **OBSOLETE** | `phase15/reports/` |
| `reports/project-closure.md` | **OBSOLETE** (states the old fixed powertrain) | design spec |
| `design_history/iteration_*.json` | **OBSOLETE** | design spec |
| `optimization/phase1…phase10` | **OBSOLETE** runners | `phase14/`, `phase15/` |
| `phase10/`, `phase11/`, `phase12/`, `phase13/` | **OBSOLETE** | `phase15/` |
| `deliverables/phase10/`, `deliverables/phase11/`, `deliverables/phase12/`, `deliverables/phase13/` | **OBSOLETE** (old 90 mm geared CAD/CAM and the 6× 300×50×16 billet nest) | design spec §18 (1 bar + 2 sheets) |
| `results/phase1_*` … `results/phase9_*`, `results/phase13_*` | **OBSOLETE** | `phase15/results/` |
| `__pycache__/` | **DELETED** (build cruft) | — |

## Partially current (use with care)

| Path | Status |
|---|---|
| `phase14/reports/phase14_coupled_design.md` | **partly current** — control-effector intent and layout are still valid; its CdA 0.0009, geared-FA4119 and frontal-area numbers are superseded. |
| `phase14/reports/phase14_scale_analysis.md` | **partly current** — the motor/EDF/battery scaling method is valid; its locked numbers are superseded. |
| `phase14/optimization/*.py` | **current** — the multivariable and frontal-area models are live. |

## Current (authoritative) set

| Path | Purpose |
|---|---|
| `design/PHASE15_DESIGN_SPEC.md` | master requirements/geometry/powertrain spec |
| `design/PHASE15_CONTROL_SURFACES.md` | control-surface and actuation spec |
| `phase15/configs/phase15_sourcing.json` | live robu.in / amazon.in parts dataset |
| `phase15/optimization/*.py` | benchmark, range, loss, frontal-area, compliance runners |
| `phase15/results/`, `phase15/reports/` | current outputs |
