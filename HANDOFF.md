# HANDOFF — high-speed twin-EDF drone-mech

**Repo:** https://github.com/iamdarshg/drone-mech (private)
**Last updated:** 2026-09-30
**Read this first, then `highspeed_edf/AGENTS.md` (binding rules).**

---

## 1. Standing user requirements

1. **Do not stop until the work is actually done.** Keep going through the real
   engineering motions; do not hand back a half-finished analysis.
2. **Reports are not validation.** The user does not read reports. Any geometry
   that is *promoted* (called validated / flight-ready / a design winner) must
   have had the applicable native analyses actually **run and inspected** by the
   agent — mesh quality, solver convergence, structural/aeroelastic results,
   mass/CG, manufacturing. A CAD export, an analytical/surrogate screen, a
   "prepared" case, or a workbench report is **not** sufficient.
3. **Ask the user to validate only when a genuine user decision is required**,
   not for routine engineering checking.
4. **Cost discipline:** keep GCP spend bounded, poll to completion rather than
   guessing a wall time, and prefer a higher-spec (16 GB / 32 GB) runner when it
   makes the run finish faster and therefore cheaper. No VMs left running.
5. **Commit frequently** and keep this private repo up to date (use `gh`).
6. **Conserve disk/artifact quota** where reasonable (small boot disk, small
   retained artifacts).

The full promotion rules are in `highspeed_edf/AGENTS.md` — treat them as
binding for any future agent working in this repo.

---

## 2. What exists and is verified

### Phase-15 airframe + ESC geometry (COMPLETE, CAD-validated)

- Generator: `highspeed_edf/phase15/optimization/phase15_generate_geometry.py`
- Deliverables: `highspeed_edf/deliverables/phase15_geometry/`
  - `step/phase15_airframe_full_assembly.step`, per-part STEPs, duct/fan and
    ESC/flight-board subassemblies
  - `stock_nests/` (sheet A/B and the 300×50×16 hub bar)
  - `reports/`: `phase15_geometry_manufacturing_report.md`,
    `phase15_geometry_audit.json`, `mass_cg.csv`, `mass_cg_summary.json`,
    `projected_frontal_silhouette.svg`, `phase15_parameter_register.json`,
    `step_reimport_validation.csv`
- Verified facts: **81/81 STEP files reimport with positive volume**; projected
  frontal solid union **248.0 cm²** (inside the 242–296 cm² band); CAD mass
  **6.541 kg** incl. 1 kg payload, **7.522 kg** with the 15 % reserve; CG on the
  fan-plane datum.
- **Known, deliberately-unhidden conflicts** (keep them visible):
  - The 72 mm Surpass 3670 cans overlap adjacent rotor stations by **36 mm** at
    the 36 mm rotor pitch → the six-motor coaxial direct-drive stack is **not
    buildable as drawn**.
  - 4 vanes + 2 elevons + 1 rudder = **7 actuators**, but the flight-board
    contract provides **6 PWM channels** (F-05 open).
  - Body section is 88 mm (not 78) to enclose the duct pair; short nose is a
    packaging compromise, not a drag-qualified ogive.
- Geometry is **NOT promoted** — see §4.

### Aero Multiphysics Workbench candidate screen (screen only)

- `highspeed_edf/phase15/optimization/phase15_aero_multiphysics_screen.py`
- Output: `highspeed_edf/phase15/fsi/reports/phase15_aero_multiphysics_candidates.json/.csv`
- Uses the workbench `aeroworkbench_vehicle_systems.coupled_optimizer`
  (evaluate-only). Records `workbenchCommit`, input hash, honest
  `nativeSolverEvidence: false`, and the fact that the workbench's SLSQP
  optimizer did **not** converge in 600 s.
- Output is **analytical** fidelity only. It is a candidate feeder, not proof.

### OpenFOAM–preCICE–CalculiX FSI workflow (BUILT; coupled run NOT yet completed)

- Case generator: `phase15_fsi_casegen.py` → `highspeed_edf/phase15/fsi/cases/`
  (two candidates: `wing_t30mm`, `wing_t36mm`; outboard wing sector, 200 m/s,
  3 km ISA, AOA 0.5°, 20 coupling windows of 1e-5 s).
- Worker: `phase15_fsi_worker.py` + `phase15_fsi_worker_startup.sh`
- Runner: `phase15_fsi_gcp_runner.py` (Workbench remote-cost policy + one bounded
  GCE Spot VM).
- Evidence: `highspeed_edf/phase15/fsi/results/attempts/<stamp>/` (full logs,
  receipts, `gcp_attempt.log`) and `phase15_fsi_execution_receipt.json`.

**Progress proven on the VM:**
- OpenCFD **OpenFOAM v2606** installs; **`gmshToFoam` OK**; **`checkMesh` =
  "Mesh OK."** (max non-orthogonality 82.9°, 50 faces >70°, max skew 1.22).
- The **preCICE OpenFOAM adapter v1.4.0 compiles** against v2606 and loads;
  `ccx_preCICE` (CalculiX adapter v2.20.2) runs.
- Both participants now **connect over preCICE** (after fixing
  `exchange-directory`).

**Latest state (last run `20260930T135143Z`):** after fixing the `fvSchemes`/
`fvSolution` entries, the coupled solvers now **run to the bounded wall-time cap
instead of failing fast** — i.e. initialization is fully fixed and the simulation
advances, but 2 candidates × 20 coupling windows did not finish inside the
2160 s VM budget (`worker_finish_missing_at_deadline`; VM auto-deleted). The
dominant cost is CalculiX re-factoring the solid system on every coupling
iteration (single-threaded SPOOLES) plus the ~8 min per-VM OpenFOAM/adapter
install.

All fixes landed (in the committed scripts):
`gradSchemes` missing; `freestreamPressure` needs `freestreamValue`; mesh type
for `fsi`/`rootWall` must be `wall` (wall functions); dynamic-mesh keyword is
`motionSolver`; compressible `alphat` dimensions `[1 -1 -1 ...]`; CalculiX
`NSET` must be `N`-prefixed (`NIFACE`); `exchange-directory=".."`;
`fvSolution` solvers `cellDisplacement(Final)`, `pcorr(Final)`, `rho(Final)`,
`"(U|h|k|omega)Final"`; `divSchemes` now has a `default` scheme plus the
compressible `div((muEff*…))` / `div(((rho*nuEff)*…))` stress terms and
`div(phid,p)`.

**Recommended next step to actually finish:** run **one** candidate per VM with a
longer cap, or cut the solid cost — e.g. coarsen the structural tet mesh, move
the coupling interface to `faceCenters` with fewer interface nodes, or build a
reusable pre-baked VM image so the ~8 min install/build no longer eats the
window. Then inspect the real coupling outputs before any promotion claim.

---

## 3. Exact continuation steps (next agent)

1. **Finish the coupled FSI.**
   ```
   python highspeed_edf/phase15/optimization/phase15_fsi_casegen.py
   # then, with the workbench remote policy env set (see §5):
   python highspeed_edf/phase15/optimization/phase15_fsi_gcp_runner.py
   ```
   Watch the new `attempts/<stamp>/worker_output/<case>/rhoPimpleFoam.log`.
   If it aborts on another missing `fvSolution` sub-dictionary entry, add it to
   `foam_case()` in `phase15_fsi_casegen.py` (rhoPimpleFoam + dynamic mesh
   commonly also wants `pcorr`, now present; check the log for the exact name).
2. Once both candidates reach `coupled_solvers_completed`, **inspect the actual
   results**: preCICE convergence/iterations, `wing.dat` tip displacements,
   `postProcessing/wingForces/.../forces.dat`, checkpoints/rollbacks. Add a
   mesh/timestep sensitivity pair before any promotion claim.
3. **Structural strength/modal** on the real candidate (CalculiX static +
   frequency, documented laminate properties) — not yet done.
4. **Full-aircraft closure** (mass/CG with all parts, control authority,
   power/thermal, rotor containment) — not yet done.
5. Only then consider promotion; until then the geometry stays unpromoted.

---

## 4. Honest status / what is NOT proven

- Airframe + ESC **geometry** is internally consistent CAD, reimport-validated,
  with manufacturing-aware stock layout — but **not** structurally, thermally,
  acoustically or aeroelastically validated.
- The **coupled aeroelastic result does not exist yet.** The run reaches the
  coupling loop but has not completed a coupling window; every "status" line in
  the receipts is honest and must be read literally.
- The six-motor coaxial powertrain is **not buildable as the handoff describes**;
  this is a design conflict, not a modelling artefact.
- Running costs and progress are tracked in
  `phase15/fsi/results/phase15_fsi_cost_history.json`.

## 5. Run environment (for reproducibility)

- GCP project `project-ba289c9c-3c25-4e15-9dc`, zone `us-central1-b`,
  bucket `aero-governed-blockers-988177451335-20260919`, pinned boot image
  `ubuntu-2204-jammy-v20260923`.
- The runner enforces the Workbench `RemoteComputePolicy` and `CostLedger`.
  Set before launching (PowerShell):
  ```
  $env:AERO_ALLOW_REMOTE_COMPUTE='1'
  $env:AERO_REMOTE_MACHINE_TYPE='e2-standard-4'      # 16 GB; e2-standard-8 = 32 GB
  $env:AERO_REMOTE_ALLOWED_REGIONS='us-central1'
  $env:AERO_REMOTE_ALLOWED_PROJECTS='project-ba289c9c-3c25-4e15-9dc'
  $env:AERO_REMOTE_MAX_WALL_S='2160'                 # cost cap (~$0.15 at $0.20/h)
  $env:AERO_REMOTE_MAX_JOB_COST_USD='0.15'
  $env:AERO_REMOTE_MAX_SESSION_COST_USD='0.49'
  $env:AERO_REMOTE_MAX_DAILY_COST_USD='0.49'
  $env:AERO_REMOTE_MAX_PROJECT_COST_USD='0.49'
  $env:AERO_REMOTE_MAX_VCPU='4'
  $env:AERO_REMOTE_MAX_RAM_MIB='16384'
  ```
- `e2-standard-4`/`e2-standard-8` are registered in the runner's machine-shape
  map; a larger machine is only worth it if it shortens wall time.

## 6. Cloud spend so far

- Actual attributable compute ≈ **$0.434** (11,941 Spot-VM seconds across 19 FSI
  attempts + one ~7-minute VM reclaimed when a client-side `create` timed out;
  the runner now describes-then-deletes so it cannot leak). Plus cents of GCS.
- The runner's *conservative reserved* ledger is higher because it counts a
  $0.03/attempt ancillary ceiling — that is an allowance, not spend.
- **No VM is running.** Always confirm with
  `gcloud compute instances list --filter='name~hsedf-fsi'`.

## 7. Key files

| Path | Purpose |
|---|---|
| `highspeed_edf/AGENTS.md` | binding promotion/validation rules |
| `highspeed_edf/design/HANDOFF_GEOMETRY_AGENT.md` | original geometry brief |
| `highspeed_edf/phase15/optimization/phase15_generate_geometry.py` | airframe + ESC CAD |
| `highspeed_edf/deliverables/phase15_geometry/` | all CAD artifacts + reports |
| `phase15/optimization/phase15_aero_multiphysics_screen.py` | workbench candidate screen |
| `phase15/optimization/phase15_fsi_casegen.py` | builds FSI cases (OpenFOAM side) |
| `phase15/optimization/phase15_fsi_worker.py` | runs the coupled cases on the VM |
| `phase15/optimization/phase15_fsi_worker_startup.sh` | VM bootstrap (OpenFOAM+preCICE+adapters) |
| `phase15/optimization/phase15_fsi_gcp_runner.py` | bounded GCP launcher + cost policy |
| `phase15/fsi/results/attempts/` | every run's logs and receipts |
