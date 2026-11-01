# maxCo 0.05 sensitivity retry

## Scope and fixed inputs

This is one narrowly changed startup retry on the same 822,395-cell Gmsh tetra mesh, same Mach 1.05 / +0.5 degree wall-compatible `0/` fields, same Kurganov `rhoCentralFoam` setup, and same pointwise 5% total-temperature-proxy guard (`344.281 K`). The only intended numerical change is `maxCo 0.1` to `maxCo 0.05`. Because this is a retry of the initial condition rather than a resume, `startFrom latestTime` was set to `startFrom startTime; startTime 0`. `endTime 0.004`, `maxDeltaT 1e-7`, field dictionaries, thermodynamics, turbulence setup, 10-step output interval, and four-write purge were retained. The exact initial fields match the archived initial state byte-for-byte after decompression. Mesh STEP/MSH and solver executable/library hashes are in the parent `source_pins.md`.

## Corrected syntax defect

The first co005 attempt exposed an existing transcription defect in the viscous-stress divergence key: OpenFOAM warned that `div(((muEff*dev2(T(grad(U)))))` was missing a closing parenthesis. Its partial log and malformed dictionary are preserved in `attempts/syntax_warning/`; it was stopped at `t=6.3876078e-8 s` before a checkpoint (status 143), with no solver-failure or physical interpretation. I made exactly one syntax correction by adding the closing `)` to that operator key. No scheme, numerical threshold, BC, or expected result was changed. `rhoCentral_co005.corrected.dryrun.log` shows one corrected step ending normally with no parser warning. The malformed and corrected dictionaries are both retained so the change is auditable.

## Monitoring and current disposition

`monitor_rhoCentral_co005.py` applies the same 344.281 K guard, 700 m/s speed guard, and 1.5 GB disk floor. Before the first writeInterval output, missing complete checkpoint data is recorded as an expected startup state; it is not treated as solver failure. The exact solver and monitor commands are retained. The attempt was stopped by the unchanged disk guard at 12:28:11.851844 UTC when free space reached 1,457,147,904 bytes (floor 1,500,000,000 bytes); the solver wrapper ended with status 143 at 12:28:34 UTC. This is a storage-safety stop, not a solver failure or aerodynamic limit. The log had advanced to `t=7.5359452e-7 s`, but the latest complete checkpoint was step 20 at `5.2086889e-7 s`; the partial later time was not treated as evidence. The maximum cell Mach near 1.05 is not evidence of a resolved shock or developed transonic field. Do not interpret any startup field as lift, drag, coefficient, convergence, or design performance evidence.

The first two corrected complete checkpoints (`checkpoint_2.294948e-07/` and `checkpoint_5.2086889e-07/`) are archived with all eight fields natively written by the solver. `verify_checkpoint.py` independently reads the compressed fields and reproduces the monitor values:

| time (s) | max Tt proxy (K) | max Mach | max speed (m/s) | p/rho/T valid |
|---:|---:|---:|---:|---|
| 2.294948e-7 | 331.515850 | 1.050149 | 345.027632 | yes |
| 5.2086889e-7 | 334.167962 | 1.050600 | 345.120779 | yes |

Both values remain below the unchanged 344.281 K guard. They show the early proxy trending upward; this is still startup data, not a developed flow. `h` was not natively written; if a later checkpoint requires energy review, any reconstructed `h` must be clearly labeled derived from T and Cp. The monitor's initial no-checkpoint and gzip-write-race samples are retained in `attempts/`; the retry-specific helper skips incomplete output directories and falls back to the last complete checkpoint.

No solver or watcher remains active. An old defunct PID from the first malformed-syntax run remains reaped by the container's init process, but there is no running solver instance for this case. Before removing temporary case output, I verified all 16 archived step-10/step-20 compressed native field files are byte-identical to the original solver outputs and pass gzip integrity checks; hashes and byte counts are in `checkpoint_copy_verification.json`. The exact stop record, status, full run log, monitor timeline, two native checkpoints, syntax correction, dry-run log, configuration dictionaries, and per-file hashes are retained here and in the experiment-level `evidence.sha256`.
