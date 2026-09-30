# High-speed EDF study

## READ THIS FIRST — current state

- **Authoritative design docs:** `design/PHASE15_DESIGN_SPEC.md` (airframe, EDF,
  powertrain, mass, layout, cost) and `design/PHASE15_CONTROL_SURFACES.md`
  (effectors, actuation, balancing).
- **Obsolete index:** `OBSOLETE.md` lists every superseded file and fact. Phase
  1–13 reports, configs, and CAD/CAM deliverables are **obsolete** and are
  banner-marked; do not size or build from them.
- **Live data/analysis:** `phase15/` (sourcing, low-cost and generative
  benchmarks, range, losses, frontal-area model, Phase-9 reconciliation) and the
  still-current `phase14/optimization/` models.

Headline current configuration: **6× rewound 4-pole inrunner direct-drive**,
**80 mm side-by-side ducts (not coaxial)**, **12S**, **drone-arm Rev-B ESC**,
**1 kg payload**, target **720 km/h / TWR ≥1.0 from 0–180 km/h / ≤8.5 kg**. The
single most important unknown is **inlet pressure recovery** (see spec §2–§3).

---

Application-specific study workspace for the electrically driven, variable-bypass
axial propulsion concept. Reference solver repositories are consumed read-only;
this workspace owns its requirements, configs, drivers, results, and reports.

## Phase 0/1

Run the local analytical screening from PowerShell:

Requirements snapshots are immutable: `requirements.yaml` is revision 1 and
`requirements_r2.yaml` is the active revision, adding the 75 cm² projected
frontal-area checkpoint (lower preferred; kept distinct from CdA).

```powershell
uv run --no-sync --directory D:\CodeProjects\aero-multiphysics-workbench\services\api python `
  D:\CodeProjects\drone-mech\highspeed_edf\optimization\phase1_feasibility.py `
  --workbench-root D:\CodeProjects\aero-multiphysics-workbench `
  --requirements D:\CodeProjects\drone-mech\highspeed_edf\requirements\requirements_r2.yaml `
  --design D:\CodeProjects\drone-mech\highspeed_edf\designs\design_state.json `
  --output D:\CodeProjects\drone-mech\highspeed_edf\results

uv run --no-sync --directory D:\CodeProjects\aero-multiphysics-workbench\services\api python `
  D:\CodeProjects\drone-mech\highspeed_edf\optimization\phase2_architecture.py

uv run --no-sync --directory D:\CodeProjects\aero-multiphysics-workbench\services\api python `
  D:\CodeProjects\drone-mech\highspeed_edf\optimization\phase3_meanline.py

uv run --no-sync --directory D:\CodeProjects\aero-multiphysics-workbench\services\api python `
  D:\CodeProjects\drone-mech\highspeed_edf\optimization\phase4_prepare_ross.py

uv run --no-sync --directory D:\CodeProjects\aero-multiphysics-workbench\services\api python `
  D:\CodeProjects\drone-mech\highspeed_edf\optimization\phase6_7_system_closure.py

uv run --no-sync --directory D:\CodeProjects\aero-multiphysics-workbench\services\api python `
  D:\CodeProjects\drone-mech\highspeed_edf\optimization\final_project_closure.py

```

Phase 9 mass export (requires the workstation Python with PySide6/NumPy and `kicad-cli`):

```powershell
& "C:\Program Files\Python312\python.exe" `
  D:\CodeProjects\drone-mech\highspeed_edf\optimization\phase9_geometry_mass_envelope.py
```

The driver reuses the workbench's ideal-gas relations. Its outputs are
analytical screening only; they are not blade-row, CFD, measured motor, or
validated battery results. The 1-D forward-flight model uses a single-stream
equivalent duct and does not yet resolve the variable-bypass split. Static
thrust is an ideal actuator-disk bound with explicit assumed efficiencies.

See `reports/phase1-feasibility.md` for interpretation and model limitations.
Phase 4 ROSS inputs are prepared and validated by `phase4_prepare_ross.py`; it
does not submit GCP jobs. See `reports/phase4-prejob-brief.md` before governed
remote execution.

Phases 6–7 use `configs/phase6_7_system_closure.json` to build the candidate
core/bypass annulus schedule and combined electrical/rotordynamic readiness
screen. They are local analytical post-processing only; see
`reports/phase6-7-system-closure.md` for limitations and disposition.

`optimization/final_project_closure.py` regenerates the final evidence register
and fixed-powertrain closure report at `reports/project-closure.md`.

Phase 9 keeps the six FA4119 motors and 12S1P battery fixed, sizes a 90 mm duct
and side-inlet geometry, re-solves the 720 km/h rotor/stator rows, and calculates
PCB material masses from the drone-arm KiCad boards. See
`reports/phase9-geometry-mass-envelope.md`; the final hardware/BOM mass still
needs weighing and full CAD closure. The candidate requirement overlay is
`requirements/requirements_r3_candidate.yaml`; immutable r2 remains the historical
baseline.
The projected layout concept is `designs/phase9_geometry_layout.svg` and the
screened geometry/mass state is `designs/design_state_r4_geometry_candidate.json`.

## Phase 10 CAD/CAM package

The offline CadQuery generator `optimization/phase10_generate_deliverables.py`
creates the editable EDF A/B and full-assembly STEP files, per-stock STEP nests,
and GRBL rough/finish NC programs under `deliverables/phase10/`. See
`deliverables/phase10/reports/phase10_edf_fuselage_cam_release_notes.md` for the
stock purchase/nesting, machine setup, and requirement audit. In particular,
the Phase-9 projected-area screen excludes the R225 side-inlet transitions; the
full installed transition envelope exceeds the 75 cm² limit, while CdA and
all-up mass remain unverified targets.

## Phase 14 coupled airframe / ESC / controls

Phase 14 carries the exact one-bar / two-sheet aluminium stock, locks a six-
actuator airframe control contract against the drone-arm Rev-B board, and
screens 650–720 km/h power plus the 0–200 km/h forward-thrust requirement.
The stock uses six hubs from the 300×50×16 mm bar and nests 72 rotor blades
plus 126 stator vanes in the 250×120×5 and 300×120×5 mm sheets. The source
files are under `phase14/`; regenerate the stdlib-only analytical closure with:

```powershell
python highspeed_edf\phase14\optimization\phase14_close_design.py
```

This revision lowers the all-up target to 8.5 kg because the inherited 10.5 kg
target screens below T/W=1 at 200 km/h under an ideal fixed-power actuator-disk
model. The new 8.5 kg screen is still not installed thrust or flight evidence.
The report records the frozen control requirements and the two corresponding
drone-arm hardware issues (#18 actuator interfaces, #19 motor temperatures).
The follow-on size/power/battery/stock/CdA trade is
`phase14/reports/phase14_scale_analysis.md`; regenerate its CSV sensitivity
outputs with:

```powershell
python highspeed_edf\phase14\optimization\phase14_motor_edf_trade.py
```

The wider multivariable screen (fan diameter, hub/motor class, motor price,
battery capacity, variable bypass, auxiliary inlets, fan figure of merit,
sea-level vs 3 km, and the revised 1.0 TWR-to-180-km/h gate) is:

```powershell
python highspeed_edf\phase14\optimization\phase14_multivariable_trade.py
```

## Phase 15 sourcing and benchmarks

Phase 15 ranks presently purchasable amazon.in / robu.in motors and 12S LiPo
packs for flight time, efficiency, and performance, then feeds the winner into a
strongly coupled generative airframe + EDF design via the aero-multiphysics
workbench. See `phase15/reports/phase15_benchmark_report.md`.

```powershell
python highspeed_edf\phase15\optimization\phase15_low_cost_benchmark.py
```

The high-cost generative benchmark must run inside the workbench Python
environment (it imports `aeroworkbench_vehicle_systems`); set `PYTHONPATH` to
the workbench `packages/*` roots and run:

```powershell
& "D:\CodeProjects\aero-multiphysics-workbench\services\api\.venv\Scripts\python.exe" `
  D:\CodeProjects\drone-mech\highspeed_edf\phase15\optimization\phase15_high_cost_generative.py
```

Headline result: **no stock 12S motor is under the ₹4,000 cap on either site**,
but a **rewound 4-pole inrunner (Surpass Rocket 3660/3670 class) does fit**; the
75 cm² frontal-area gate is superseded by the corrected ~242–296 cm²
battery-dominated silhouette; and the two deciding unknowns are **inlet
pressure recovery** and **CdA**, both still unmeasured.

Superseded Phase 1–9/13 runners below are retained for traceability only; see
`OBSOLETE.md`. Run only the `phase14/optimization` and `phase15/optimization`
scripts.
