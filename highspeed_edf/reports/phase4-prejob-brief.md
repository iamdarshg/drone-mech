> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phase 4 ROSS pre-job brief

## Proposed governed work

**Three ROSS Campbell cases**, one for each unique EDF rotor row (R1/R2/R3); left/right copies are represented by symmetry. Run sequentially in one time-limited GCE Spot VM. Each sweeps 0 rpm to that rotor's Phase-3 maximum (31,310 / 34,340 / 36,360 rpm), finds synchronous critical-speed crossings, and checks declared excitation-line separation. Each case still runs through `NativeJobManager` and publishes only evidence-gated results; the solver subprocess runs on the GCP worker.

### Why this work is justified

The Phase-3 RPM schedule drives the duct rotors above 30 krpm. The Campbell check can identify critical-speed crossings and proximity to 1× rotation, rotor blade-pass, stator-vane-pass, FA4119 7× electrical fundamental, 42× electrical sixth-harmonic/torque-ripple proxy, and fixed 20/40 kHz PWM lines. A crossing can change shaft support span, stiffness, bearing placement, rotor mass, or the operating RPM schedule before CAD/CFD and hardware work.

### Resource and spend estimate

| Resource | Planned cap |
|---|---:|
| Worker | One Spot `e2-standard-2`, 2 vCPU, 4 GiB memory; no GPU |
| Lifetime cap | **20 minutes total**; Spot instance, auto-delete; 20 GiB `pd-standard` boot disk auto-delete |
| Reference rate | $0.10/hour (conservative workbench planning rate; historical Spot run was lower) |
| Compute estimate | 20 min × $0.10/hour = **$0.034** (3.4¢) |
| Storage/I/O allowance | **$0.005** (0.5¢) estimated |
| Estimated total | **$0.04**; target **≤$0.10**, hard ceiling **$0.12** |

The workbench reference pricing is not a billing quote. The previous governed Spot worker evidence was under $0.02 for a 21-minute multi-solver worker session. This run is capped at 20 minutes on one reusable VM; actual GCP billing receipt remains authoritative. If staging/startup leaves less than the three analyses' wall budget, the worker must fail/stop inside the 20-minute cap rather than extend it.

## Assumed rotor model inputs (not measured)

- Steel shaft equivalent: 6 mm diameter × 60 mm support span, four beam segments.
- Equivalent annular rotor disk: 80 mm OD, 32 mm ID, 2 mm steel-equivalent width (~66 g by the ROSS disk geometry). This lumps hub/blade inertia; it does not resolve carbon blade anisotropy or blade mass distribution.
- Two end supports: 10 MN/m radial stiffness and 200 N·s/m damping, sensitivity range 1–100 MN/m. FA4119 decision data does not specify fan-shaft bearings or gearbox-output support properties; the older custom-motor bearing file is superseded and is not used.
- Gear mesh, bearing characteristic frequencies, and measured unbalance amplitude are omitted because tooth/bearing geometry and balance data are not available. Forced-response runs are not included in this first batch.

## Submission gate

Inputs are normalized and validated locally and stored in `results/phase4_ross_job_plan.json`; **no GCP worker has been launched yet**. The workbench's GCPBatchExecutor is an unprovisioned fail-closed skeleton, so the proposed route is the repository's documented short-lived GCE worker pattern: `NativeJobManager` executes locally inside one user-authenticated Spot VM. The active gcloud project/auth and existing US-CENTRAL1 evidence bucket are available. The VM will be capped at 20 minutes with auto-delete; input/result objects use a unique Phase-4 prefix. No source repository is modified.

## Fidelity limitation

ROSS Campbell results can provide critical speeds and forcing-separation margins, but the current participant publishes no full Campbell-curve artifact. This batch would not establish forced-response amplitudes, gear-mesh response, blade stress, containment safety, or coupled left/right aircraft modes.

## Execution update

The three Campbell cases completed on 2026-09-23 using the prebriefed single Spot VM. The VM was deleted after download, temporary GCS plan/runner objects were removed, and native evidence remains in the retained result objects and local `results/phase4_ross_evidence.json`. Estimated compute using the conservative reference rate was about 0.9¢; the actual billing invoice was not queried. See `phase4-ross-review.md` for the resonance interpretation and a provenance artifact-reference issue found in the workbench output.

