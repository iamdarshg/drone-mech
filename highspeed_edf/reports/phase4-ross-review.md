> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phase 4 ROSS Campbell review

**Evidence:** governed `native_solver` envelopes; ROSS 2.3.0; workbench commit `e1dc31833c444ec1047200d32fb094c5a3aa3163`. Three stage cases completed on one Spot GCE worker.

| Stage | First critical | Steady rotor RPM range | Critical on startup ramp? | Closest ROSS sampled forcing | Margin |
|---|---:|---:|---|---|---:|
| R1 | 18433 rpm | 24250–31310 rpm | Yes | 1x rotation at 18786 rpm | 11.23 Hz |
| R2 | 18433 rpm | 27270–34340 rpm | Yes | R2 rotor blade passing at 4292 rpm | 6.57 Hz |
| R3 | 18433 rpm | 30300–36360 rpm | Yes | R3 rotor blade passing at 4545 rpm | 3.09 Hz |

## Engineering interpretation

All three assumed rotor assemblies produce a first critical near 18,433 rpm, below the Phase-3 steady rotor schedules but inside the 0-to-operating-speed acceleration ramp. Treat this as a startup resonance crossing that requires a controlled run-up/response check or a stiffness/mass/support redesign; do not interpret it as safe merely because the ROSS participant validity envelope passed.

The near-identical critical speeds are expected from the current input plan: all three rows use the same assumed shaft, support stiffness/damping, and equivalent annular disk. Blade mass/inertia differences were not modeled; this is not evidence that the physical R1/R2/R3 critical speeds will match.

ROSS's declared-forcing scan reports nearest sampled-line margins. It samples the Campbell speed sweep at 41 points; the 1× synchronous line necessarily intersects a critical speed, and that continuous crossing is not represented by the sampled minimum margin. R3's 3.09 Hz sampled margin is a watch item (the participant uses 5 Hz warning / 2 Hz critical thresholds).

The phase-4 review found a provenance artifact-hash name mismatch in the workbench output map: result.json, run_ross.py. The native envelope hashes match the independently observed case-file hashes, but the `native.result-recorded` event associates the run_ross.py/result.json hashes with the opposite filenames. Treat those provenance references as a workbench publication bug to fix before relying on artifact-to-provenance link resolution.

The beam plausibility check estimates a first critical near 204 krpm, over 11× higher than the ROSS bearing/disk model. Although inside the workbench's deliberately broad factor-50 plausibility band, this large spread makes the assumed shaft, bearing stiffness and equivalent disk mass dominant uncertainties. FA4119/output-bearing CAD and measured support stiffness are needed to refine the model.

The current ROSS result supplies critical speeds and forcing separation but no full Campbell-curve artifact or forced-response amplitude. Gear-mesh orders, rolling-bearing frequencies, blade modes/stress, containment and left/right structural coupling were not modeled. No forced-response job was included because measured unbalance amplitude is unavailable.

**Workbench provenance issue found:** `ResultEnvelope.artifacts` and independent case-file hashes agree, but the `native.result-recorded` provenance event swapped the SHA-256 references for `run_ross.py` and `result.json`. The apparent source is `solvers/participants/lifecycle.py` zipping manifest order against `_hash_artifacts()`' sorted output list. I left the shared repo unchanged; fix that mapping before relying on provenance artifact URI→hash lookup.

## GCP cost and cleanup

The single Spot VM ran from about 18:55:37 to 19:00:48 UTC (about 5.2 minutes). At the conservative $0.10/hour reference rate this is about **0.9¢ compute**, below the 10¢ target and 12¢ ceiling; this is an estimate, not the billing invoice. The VM was explicitly deleted after evidence retrieval; temporary plan/runner objects were removed. Evidence objects remain in the GCS bucket and local results.

## Artifacts

- `results/phase4_ross_evidence.json` — envelopes, hashes, provenance chains.
- `results/phase4_ross_cases.tar.gz` — case/result/run-script/solver-log artifacts.
- `results/phase4_ross_review.csv` — compact per-stage review table.
- `reports/phase4-prejob-brief.md` — pre-run purpose/cost/assumptions.

