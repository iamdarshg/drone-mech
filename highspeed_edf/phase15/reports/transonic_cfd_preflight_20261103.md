# Transonic CFD preflight — 2026-11-03

This is a run-readiness note, not CFD evidence. No solver or cloud job was launched for this preflight; the requested compute machine is still pending. The existing aircraft geometry remains unpromoted, and no drag, lift, control-authority, structural-strength, fabrication, or flight-readiness conclusion is made.

## Speed conditions to carry into the next campaign

Use the existing servo-screen convention: indicated speed is treated as calibrated airspeed (CAS ≈ IAS), then converted to Mach and TAS with the subsonic compressible pitot relation at the specified ambient pressure. Do not use the incompressible density-ratio shortcut for these speeds. The checked Phase-15 screen gives these 3 km ISA anchors (p = 70,108 Pa, T = 268.65 K):

| IAS (km/h) | Intended case | Freestream Mach | TAS (m/s) | Dynamic pressure (Pa) |
|---:|---|---:|---:|---:|
| 50 | low-speed control | 0.0491 | 16.12 | 118 |
| 60 | low-speed control | 0.0589 | 19.34 | 170 |
| 700 | primary cruise target | 0.6760 | 222.13 | 22,429 |
| 800 | dive envelope | 0.7694 | 252.81 | 29,053 |
| 900 | dive envelope | 0.8618 | 283.17 | 36,450 |

These figures are boundary-condition anchors, not safe operating speeds. The transonic campaign must include Mach-space points around the local shock/drag-rise transition, because local acceleration over the wing can reach sonic conditions below Mach 1 freestream. Retain sea-level cases as a separately labeled secondary environment. A 900 km/h IAS case at sea level is not interchangeable with the primary 3 km condition.

## Existing solver evidence and its limits

The experiments under `phase15/fsi/results/local_openfoam_20261030/experiments/centerline_halfwing_ias/` on the detached `codex/transonic-solver-ias700-900` worktree are failure diagnostics only. The case is a rigid, simplified half-wing without fuselage, EDF/duct flow, moving rotor regions, inboard production geometry, or a root fillet. The 49,208-cell mesh has maximum non-orthogonality 83.46 degrees and skewness 2.77; a stricter follow-up found 411 cells below the determinant threshold and 14 faces below the interpolation-weight threshold. Fresh IAS700 and IAS900 `rhoPimpleFoam` attempts exited with floating-point exceptions before completion and showed nonphysical temperature/speed growth.

A later bounded IAS900 run used TAS 283.172 m/s, Mach 0.861815, +0.5 degrees, and maxCo 0.1 on the same mesh. `rhoPimpleFoam -dry-run` passed, but strict mesh-quality checks failed. The monitored case was stopped at t = 5.6100292e-6 s after a local total-temperature proxy reached 353.6 K against an approximately 309 K freestream total-temperature bound; there was no normal solver completion. These results do not identify physical shocks or establish transonic drag.

The detailed detached-worktree logs and fields remain in the local `drone-mech-transonic` worktree at commit `49dca8b5f36c8af1752634f34098616bf1e8b25f`; the short evidence summary above is retained here so main does not rely on an unmerged branch for its status. The existing phase-15 FSI case generator is a separate structural-coupling experiment and its 200 m/s outboard-wing cases are not substitutes for an aircraft transonic campaign.

## Ready-to-run campaign structure

1. Freeze one buildable, mass-consistent aircraft geometry and record its STEP/source hashes. The current phase-15 assembly STEP hashes to `9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772`, but its own handoff records 36 mm motor-can overlap at the 36 mm station pitch and seven required actuators against six PWM channels. Close these geometry/interfaces or explicitly model the resulting candidate as an unbuildable aerodynamic study article; do not present it as the aircraft.
2. Build a compressible, viscous external-flow case with a mesh that passes `checkMesh -allTopology -allGeometry` and the project’s stricter determinant/interpolation gates. Resolve leading-edge, trailing-edge, tip, junction, and control-gap cells before starting long runs. Demonstrate mesh and timestep sensitivity.
3. Run rigid-airframe attached-flow anchors at 700/800/900 IAS at 3 km and selected sea-level comparisons. Add Mach-space bracketing through the measured local drag-rise/shock onset. Record residuals, mass/energy flux, wall y+, pressure/skin-friction drag, CL/CD/CM, and surface Mach/pressure fields. A clean convergence log alone is insufficient.
4. Run low-speed 50/60 IAS angle-of-attack sweeps with the real control geometry. Use unsteady separation-capable cases around stall; do not impose a linear post-stall CL model. Evaluate elevator/elevon/rudder authority and hinge moments separately from CFD-integrated loads.
5. Only after the rigid external case is stable, add installed duct/EDF boundary conditions or rotating regions and quantify their effect. The isolated duct-loss study cannot stand in for installed external/internal flow.
6. Run structural and aeroelastic loads from the accepted pressure distributions using explicit hand-layup material properties, joints, restraints, actuator loads, and safety factors. Keep all candidates unpromoted until the applicable checks finish and are reviewed.

## Compute start gate

When the new machine is available, first record OS, CPU/RAM, disk free space, OpenFOAM distribution/version, Gmsh/mesh tools, and input hashes. Use the existing bounded runner policy only after confirming the requested resource/cost envelope; do not start paid remote execution under this note. Start with mesh/checkMesh and one short solver smoke case, inspect field bounds and conservation, then scale the validated setup across the envelope. Preserve failed attempts and stop on nonphysical state bounds rather than extending a broken run.
