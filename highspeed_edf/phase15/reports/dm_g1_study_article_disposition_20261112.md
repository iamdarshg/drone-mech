# DM-G1 disposition — Phase-15 is an unbuildable aerodynamic study article

**Decision (2026-11-12): the Phase-15 full assembly is labelled an _unbuildable
aerodynamic study article_.** It is not the aircraft, it is not promoted, and no
result computed on it may be described as buildable, flight-ready or validated.
This closes DM-G1 by the gate's second branch ("candidate explicitly labelled
unbuildable study article"). It does **not** resolve the motor overlap or the
actuator allocation; both stay open, visible blockers below.

## Controlling input

| Item | Value |
|---|---|
| Assembly STEP | `highspeed_edf/deliverables/phase15_geometry/step/phase15_airframe_full_assembly.step` |
| Size | 62,370,655 bytes |
| SHA-256 (recomputed 2026-11-12) | `9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772` |
| Repository commit at decision | `26f3903acaa2ae575c196c4acc6f475ea93a7451` |

Recompute: `shasum -a 256 highspeed_edf/deliverables/phase15_geometry/step/phase15_airframe_full_assembly.step`

## Why it is unbuildable (evidence already in this repository)

1. **Motor overlap (geometry blocker).** `phase15_motor_pitch_native_step_audit_20261101.md`
   re-imports the STEP (CadQuery 2.7.0 / OCC 7.8.1.1): 72 mm can bodies at a 36 mm
   rotor pitch overlap 36 mm between adjacent rows; the exported 80 mm motor BReps
   overlap 44 mm, with a 50,033.00 mm³ Boolean common volume for each adjacent pair
   in both ducts. Receipt `motor_pitch_bounds_20261101.json`
   (SHA-256 `1180827d4fee98c4e1a0bc1e347b0af2d4ea41acd49f1054a24520a521693358`),
   verifier `verify_motor_pitch_bounds.py`
   (SHA-256 `88dd358962378d00627a72f22c45e622fca273b085a844ab7260c143d4873d71`).
   The audit finds no non-redesign correction: a real motor/shaft package must be
   chosen first.
2. **Actuator allocation F-05 (closure blocker).** Four vector vanes + two elevons +
   one rudder = 7 actuator channels against 6 PWM channels on the frozen flight-board
   contract (`highspeed_edf/AGENTS.md`; `highspeed_edf/design/DESIGN_DECISIONS_FOR_VERDICT.md`,
   SHA-256 `ced592eae4e5567990f875e85bbc0cad286eade66cf0d5fa94024b84506c7c7d`).
   F-10 (single-rudder yaw failure) compounds it.
3. **Packaging.** The 200 mm battery bay constrains nose, inlet and payload; any change
   to those requires an assembly re-check.

## What the label permits

- External-aerodynamics studies (DM-G2 mesh, DM-G3 transonic, DM-G4 low-speed) on the
  outer mould line of this STEP, reported as **study-article results**: they describe
  this shape, not a buildable aircraft.
- Internal duct/rotor flow on this geometry only as a diagnostic, because the rotor
  stack it models cannot be built as drawn.

## What the label forbids

- Any buildability, flight-readiness, structural-adequacy or promotion claim.
- Using study-article loads for DM-G5/DM-G6 sign-off on a different (buildable)
  geometry without re-running on that geometry.
- Hiding the overlap or F-05 in renders, assembly graphics or summaries.

## Open owner decisions (not taken here)

| ID | Decision | Options on record | Blocks |
|---|---|---|---|
| Motor package | Real motor/shaft package vs. 36 mm rotor pitch | audit §"Minimum spacing sensitivity": ≥80 mm pitch moves R3 into the nozzle span; needs an authoritative motor drawing | DM-G1 (buildable branch), DM-G7, DM-G9 |
| F-05 | 7th actuator channel | (a) add PWM channel (board respin), (b) one CAN actuator, (c) 6 effectors (re-opens D3) | DM-G7, DM-G9 |
| F-10 | Rudder single point of failure | (a) two rudders (+1 channel), (b) accept degraded mode, (c) redundant servo | DM-G7 |

These carry cost and schedule consequences recorded in the decision file; they are the
owner's to make. Until they are made, DM-G9 keeps Phase-15 **unpromoted**.

## Gate status after this disposition

| Gate | Status |
|---|---|
| DM-G1 | PASS (labelled unbuildable study article; STEP hash recorded) — buildable branch still blocked on the motor package |
| DM-G7 | BLOCKED — F-05 / F-10 owner decisions; mass/CG closure needs a buildable layout |
| DM-G9 | Unpromoted |
