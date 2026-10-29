# AGENTS.md — drone-mech root

Authoritative airframe and physical engineering repository for the civilian, non-weaponized high-speed **twin-EDF** research aircraft. The user wants thrust vectoring retained as a current provision/future development, and possibly a future tailless/split drag surface layout. Do not change this to combustion turbojets without a separate explicit architectural decision. There is no pilot/cockpit, armament, missiles, guns or active tactical targeting. An optional camera and inert future radar-shaped payload block are allowed as physical integration placeholders only.

**First:** Read [program issue #1](https://github.com/iamdarshg/drone-mech/issues/1), [acceptance/CAD adapter issue #14](https://github.com/iamdarshg/drone-mech/issues/14), [drone-arm test platform #21](https://github.com/iamdarshg/drone-arm/issues/21), `HANDOFF.md`, `highspeed_edf/AGENTS.md`, `highspeed_edf/design/PHASE15_DESIGN_SPEC.md`, `highspeed_edf/design/PHASE15_CONTROL_SURFACES.md`, and `highspeed_edf/deliverables/phase15_geometry/reports/phase15_parameter_register.json`.

## Scope and ownership
- Here: airframe geometric source, duct/EDF solids, rotor mounts/shafts, wing/effector physical geometry, battery/ESC/flight PCB *envelope import*, thermal/mechanical analyses, OpenFOAM + preCICE + CalculiX, manufacturing, assembly and physical launch/recovery plans.
- `iamdarshg/drone-arm`: KiCad schematics/PCBs, ESC/flight hardware authority, flight-control firmware, actuator allocation and gain schedules, SIL, telemetry, fail-safe software, programmatic acceptance runner. Do **not** implement parallel flight controller code in this repo. Share versioned input geometry and test schema with exact repo SHA.

## Truth and no fake engineering
Current CAD has 81/81 STEP round-trip success and nominal mass/front silhouette calculations; it is not proven buildable, structurally validated or flight-ready. The most critical unresolved geometry conflict is six 72mm-long selected motor cans intersecting over 36mm in 36mm-pitch rotor rows. Native FSI workflow advanced initialization but never completed the coupled case. Isolated inlet RANS did not have trustworthy inlet boundary conditions. Do not relabel those as solved.
- Only native imported solids, kicad board outlines and corresponding human-readable source are fit evidence. A rendered image or CAD generator return code is not a collision audit.
- Geometry must be generated from one source-of-truth parameter schema. Avoid “fixing” CAD through arbitrary scaling, deleting real motor cans or moving control boards to impossible locations without collision/thermal/CG checks.
- Board envelopes currently hard-coded into CAD (ESC 150×150×1.6mm, flight PCB 140×100×1.6mm) are *placeholders*. The other repository has a 150×150 placement candidate and a 173.95×293.15mm live ESC audit; select and import actual PCB revision first. Do not assume either one is fabricated.
- Motor cans, fan/duct, battery pair, harness/busbar, servo gearboxes, connectors, antenna/radio, hardware cooling, mounting and maintenance clearance must all exist in the complete assembly test.
- Composite layups on printed structural shapes and 6061-T6 machined rotor/hub ideas are preliminary. Missing resin/ply/bond/temperature and proof-test data are BLOCKED, not guessed.
- All previous phase 1–13 results are historical/obsolete where so marked; do not re-promote without a new source-pinned verification.
- The 720km/h, pressure-recovery 0.99, 360A continuous, reserve mass and drag figures may be design assumptions or model outputs. Any claim of observed performance requires independent evidence.

## First engineering PR: executable verification adapters (issue #14)
Before CAD redesign, implement native source import/verification in `highspeed_edf/verification/` with cross-repo acceptance catalog #21:
1. Deterministic STEP import, units/datum, solid positive volume, grouped interference and measured min clearance; **must FAIL selected motor-can overlap**.
2. Board PCB `Edge.Cuts`, holes, maximum component height, connector/access envelope imported from selected pinned drone-arm SHA; must FAIL incompatible CAD placeholder.
3. Body/duct/battery/servo/harness/ESC mass, CG and assembly access calculations, verified against native solids; actual available battery data may be unavailable and must be BLOCKED.
4. Type-checked mechanical/thermal/material attributes and truly executable CalculiX static/modal and bounded FSI adapters where installed.
5. `checkMesh` and OpenFOAM native logs, physical inlet BCs and pressure recovery; timed-out preCICE/CalculiX and missing raw output **cannot pass**.
6. Test mutation fixtures: wrong units, motor-can length, wrong rotor pitch, stale CAD hash, absent board model, fabricated solver completion, skipped payload mass, impossible temperature property, missing actuator count.
7. Deterministic JSON/JUnit/HTML scorecard with PASS/FAIL/BLOCKED/NOT_RUN/NOT_APPLICABLE and actual run counts; no invented 12k successes. High-count SIL scenario tests belong in drone-arm with the correct 6DOF plant.

## Agent execution requirements
- Read actual sources, git HEAD and existing branch/PR before changes. Use independent subagents for CAD source, manufacturing, CFD and verification if available.
- Test first. When changing a geometric feature, run the exact affected CAD/BREP, mass, materials, collision, assembly, thermal and aero source-invalidation checks; rerun native solver only if justified and approved for spend.
- Read `HANDOFF.md` for governed GCP RemoteComputePolicy and cleanup; no unattended unbudgeted cloud work. A generated report or solver-input file is not completed native solver evidence.
- Create a separate small branch/PR for each issue #2–#13. Include source SHA of both repos, test IDs, commands+exit codes, actual/expected quantities/units, hash of raw native outputs, evidence quality/assumptions, negative test and independent reviewer result. Never relax/delete verification requirements in same implementation PR to claim a pass.
- If missing real hardware dimensions, material coupon data or physical test results, produce a blocked gate and precise instrumented measurement request, then work on another independent item. Do not claim validated by inventing inputs.
- Do not autonomously manufacture, run high-speed rotors, energize high-current packs, perform field flight or deploy a flight-controller configuration. Such gates require proper physical supervision and authorization.

For Codex Cloud plugin/tools and project master instructions see `iamdarshg/drone-arm/docs/CODEX_CLOUD_PLUGIN_MATRIX.md` and `docs/CODEX_CLOUD_MASTER_EXECUTION_PROMPT.md` on the corresponding agent-instructions PR; file paths exist only after that PR is merged.
