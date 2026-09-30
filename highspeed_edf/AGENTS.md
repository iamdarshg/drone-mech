# Aircraft geometry and promotion rules

These rules apply to every agent changing or promoting an aircraft, propulsor,
control surface, mount, or other flight-critical geometry in `highspeed_edf/`.

## Promotion requires executed engineering evidence

Do not call geometry **validated**, **promoted**, **flight-ready**, or a design
winner because a CAD export, analytical report, surrogate, mesh-generation exit,
or solver-preparation receipt exists. The user expects the agent to run the
relevant analyses and inspect the native outputs before requesting their review.

For each candidate that is proposed for promotion:

1. **Geometry and interfaces:** round-trip the STEP/BREP; verify units, axes,
   envelope, material assignments, positive-volume solids, interfaces and
   interference checks. Keep manufacturing stock, tolerances, fasteners,
   fixtures and assembly clearances explicit.
2. **Aerodynamics:** run the actual generated mesh through OpenFOAM; require
   successful `checkMesh`, solver completion, residual and mass/flux checks,
   physically correct boundary patches, and mesh- and timestep-sensitivity
   comparisons. For rotor/duct designs, model the applicable moving/rotating
   regions and inlet/outlet conditions rather than substituting an isolated
   static channel.
3. **Mechanical:** run native structural/modal analyses on the actual candidate
   geometry with documented material/layup properties, restraints, joints,
   actuator/pressure/centrifugal loads, and stress, strain, deflection, fatigue,
   resonance and safety-factor checks as applicable.
4. **Aeroelastic/multiphysics:** for flexible aerodynamic surfaces, run the real
   OpenFOAM–preCICE–structural-solver coupling. Record participants, interface
   mapping, force/displacement units, coupling residual/convergence, checkpoints
   and rollbacks, mesh/timestep sensitivity, peak loads/deflections and flutter
   or modal margin. A toy preCICE field exchange is only an adapter test, not
   aircraft FSI evidence.
5. **Aircraft closure:** recompute CG/mass with every physical part and payload,
   check control authority and range, and close power/thermal/electrical and
   rotor-speed/containment gates that the changed geometry affects.
6. **Workbench/provenance:** use the Aero Multiphysics Workbench for candidate
   state, solver policy and evidence where supported. Preserve input hashes,
   solver/version identity, native logs, mesh/check receipts, solver outputs,
   resource/budget accounting and an honest fidelity label. If a workbench
   capability is unavailable, do not relabel another result as a workbench or
   native result; document the blocker and continue through an explicitly
   authorized, bounded solver path when available.
7. **Promotion decision:** keep candidates unpromoted if any applicable gate is
   missing, failed, assumption-dominated or only analytically screened. Present
   the remaining design decision to the user only after the analysis is complete
   and a specific user choice is genuinely required.

Reports are evidence indexes, not substitutes for opening and checking the
solver logs, mesh metrics, coupling traces, force/displacement histories and
structural results. The agent owns this verification; do not shift routine
engineering validation onto the user.

## Known Phase-15 conflicts to preserve in future work

- The handoff's 72 mm motor cans overlap adjacent rotor stations by 36 mm at
  36 mm pitch. Do not hide this with assembly graphics or claim a buildable
  six-motor coaxial stack until a physically compatible motor/drive layout is
  analyzed.
- Four separate vector vanes, two elevons and one rudder require seven actuator
  channels; the flight-board contract has six. Preserve the F-05 allocation
  gate until hardware/firmware closes it.
- The 200 mm battery bay and nominal body/duct dimensions constrain the nose,
  inlet and payload space. Re-check the assembled geometry when any bay, inlet,
  duct or payload placement changes.
