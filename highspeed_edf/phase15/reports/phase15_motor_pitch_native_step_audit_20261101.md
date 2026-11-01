# Phase-15 motor pitch native STEP audit

**Disposition: current coaxial 36 mm rotor pitch is blocked by the exported motor-envelope BReps. No geometry change is made.** This is a source-pinned CAD placement and Boolean-intersection audit only. The motor objects are simplified envelopes, not imported manufacturer geometry; this result does not establish the dimensions of a purchased motor or a real drivetrain.

## Reproduce

From the repository root with CadQuery and OpenCascade Python bindings installed:

```sh
python3 highspeed_edf/phase15/reports/verify_motor_pitch_bounds.py
```

The executable imports the full native STEP, checks the six motor, six rotor and six stator nodes, recomputes each selected shape's bounds, tests pairwise motor BRep common volumes, and performs a no-edit 80 mm pitch sensitivity against the existing nozzle BRep. Its output receipt is `highspeed_edf/phase15/reports/motor_pitch_bounds_20261101.json`.

Inputs are pinned by SHA-256: full assembly STEP `9b83f3bfa5ea261c2055152c9fdd2147b9e16819634715c3c4ae23b45deae772`; geometry generator `53353da1c6f46d8cd9df7431209946869c0984908b269fb94d01f25a1cfabd47`. The render reviewed earlier is also pinned to the same STEP hash. The initial visual report was pinned at `5448366`; this follow-up was prepared on `main` after subsequent evidence commits, with the STEP and generator hashes above as the controlling inputs.

## Measured model bounds

CadQuery 2.7.0 / OpenCascade 7.8.1.1 reimported each motor envelope as one valid solid. Both ducts have the same axial placements; their motor centerlines are at X=−44 mm and X=+44 mm, respectively.

| Row | Rotor station origin | Principal 42 mm can body Z interval | Full exported motor BRep Z interval |
|---|---:|---:|---:|
| R1 | 12 mm | 20..92 mm | 12..92 mm |
| R2 | 48 mm | 56..128 mm | 48..128 mm |
| R3 | 84 mm | 92..164 mm | 84..164 mm |

The generator sets `MOTOR_CAN_LENGTH=72 mm`, then fuses an additional 8 mm long, 5 mm diameter coaxial pilot/stub beginning at the rotor station. The can body intervals therefore overlap 36 mm between adjacent rows. The actual exported motor components have 80 mm Z extents, so their bounding intervals overlap 44 mm between R1/R2 and R2/R3, and 8 mm between R1/R3. The STEP BRep common-volume calculation reports 50,033.00 mm³ for each adjacent motor pair and 157.08 mm³ for each R1/R3 pair in both ducts. Those positive intersections apply to the simplified exported solids; they are not a claim about a real motor's hollow housing or shaft configuration.

## Minimum spacing sensitivity and remaining blocker

To separate the principal 72 mm can-body intervals axially, centers would need at least 72 mm pitch. To separate the complete 80 mm exported component BRep intervals, they need at least 80 mm pitch: +44 mm per gap relative to the current 36 mm pitch. Holding R1 fixed would move R2 +44 mm and R3 +88 mm, placing rotor stations at Z=12/92/172 mm. The moved R3 rotor BRep would then span Z=164..180 mm, within the existing nozzle's axial span of Z=110..245 mm. The verifier records both axial interval overlap and BRep common volume for shifted rotor/stator stages against the nozzle; the BRep test does not validate flowpath quality, blade loading, thermal or assembly clearances. This is an unvalidated change to the current rotor/nozzle station arrangement, not a supported repair.

### Guarded nozzle Boolean receipt

The 80 mm pitch sensitivity checks the six duct-A stages (R1/R2/R3 rotors and S1/S2/S3 stators) against the existing nozzle. Bounding-box-disjoint pairs were screened without an expensive Boolean. Three candidate pairs had axial bounding-box overlap and were run as isolated fresh-interpreter OpenCascade Booleans. Each Boolean had a 600 second wall-clock limit and a 3072 MiB child RSS limit. All three completed under both limits with 0.0 mm³ common volume:

| Shifted stage vs nozzle | Axial bbox overlap | Boolean status | Time | Peak child RSS | Common volume |
|---|---:|---|---:|---:|---:|
| duct A stator S2, +44 mm | 4 mm | completed | 129.597 s | 1399.69 MiB | 0.0 mm³ |
| duct A rotor R3, +88 mm | 16 mm | completed | 106.156 s | 819.94 MiB | 0.0 mm³ |
| duct A stator S3, +88 mm | 8 mm | completed | 97.236 s | 1428.14 MiB | 0.0 mm³ |

The other three duct-A stages were bbox-disjoint from the nozzle and their exact common volume is recorded as `not_run_bbox_disjoint` in the JSON receipt. The deliberate first attempt used a forked Python process and stalled in `futex_wait` after the post-fork OCC state; it was terminated before 600 seconds and made no geometric claim. The completed results came from the fresh-interpreter rerun. The JSON receipt records the exact STEP SHA on every completed Boolean, process limits, elapsed times, peak RSS, exit status, and measured volume. The run log SHA-256 is `bbaa91759fef52d5d9557cec5425b54f9ecae1311286d1f5ebdd2f6b1a8777b1`; the output JSON SHA-256 is `1180827d4fee98c4e1a0bc1e347b0af2d4ea41acd49f1054a24520a521693358`; the verifier source SHA-256 is `88dd358962378d00627a72f22c45e622fca273b085a844ab7260c143d4873d71`. The fork-stall receipt is preserved at `highspeed_edf/phase15/reports/motor_pitch_bounds_fork_guard_attempt_20261101.log`.

These checks use only duct A for the counterfactual stage-vs-nozzle sensitivity. They are a CAD placement/solid-intersection screen for this model, not evidence that a revised pitch is aerodynamically suitable or mechanically buildable. Zero common volume does not prove running clearance, flow quality, thermal margin, or compatibility with a physical EDF/motor.

There is no non-redesign correction supported by the current repository: deleting the 8 mm pilot from the envelope would still leave 36 mm principal-can overlap, while moving only motor envelopes would require an unmodeled shaft or transmission arrangement. No authoritative motor drawing or shorter motor/drive candidate with a documented package is pinned here. The smallest credible next decision is therefore to obtain a real motor/shaft package and decide whether the 36 mm rotor pitch or the motor/drive requirement governs; until then, keep this geometry blocked. CFD startup diagnostics do not justify a pitch change and are not used as evidence in this audit.
