# Issue 2 motor-drive feasibility screen

This PR adds an executable, source-pinned feasibility screen for `drone-mech#2`. It reproduces the current native motor-envelope collisions and quantifies a few necessary geometry bounds. It does not select a drive, modify aircraft geometry, run an engineering solver, or claim fit, performance, manufacturing readiness, or flight readiness. The issue remains open.

## Evidence basis

This is a separate current-source revalidation against candidate revision `ff670b80b2b3ce925b03d14a91329bb7940e73d7` and historical main baseline `5246c90657071772e220b118967fa5f3e7c9ff7c`. It repins the generator SHA after the sheet-nest correction; the six native motor STEP inputs and motor parameter constants are unchanged. The earlier PR #16 evidence remains at `issue2_motor_drive_feasibility_screen.json` and is not overwritten. It verifies local input SHA-256 values and all six motor STEP hashes before computing. Motor dimensions are parsed from the pinned generator, a SHA-pinned issue #2 body snapshot, and the checked-in donor-research note. These remain separate evidence variants: generated CAD envelope 42×72 mm; issue text claim 36×72 mm; donor-note Surpass 3670 36×70 mm; donor-note 3660 36×60 mm. For conservative planning only, the analytical envelope uses the independent maxima, Ø42×72 mm. This combines the largest recorded diameter and length; it does not establish the selected SKU's actual dimensions. Donor dimensions and its 5 mm shaft statement are secondary sourcing claims, not independent measurements or manufacturer-native geometry. The generated `makeCylinder(2.5, 8.0, ...)` feature is recorded as a model stub primitive; the screen does not infer a physical shaft diameter from the fused STEP solid.

For each motor STEP, the existing PR16 CadQuery/OCC adapter measures native solid bounds, positive volume and exact Boolean intersection. Across all 15 motor pairs, it finds six positive-volume intersections and returns FAIL: four adjacent can pairs have 36 mm can overlap and 50,033.005 mm³ intersection each; two first/third shaft-stub-to-can pairs have 8 mm total-envelope overlap and 157.080 mm³ intersection each. The six part solids remain untouched.

Board geometry is re-read on every screen run from the arm source files at pinned Git revision `744994a096ca73e872b396a9b0636c58e7c1afe8`. The screen verifies the Git blob IDs and working-tree bytes, then calls the PR34 native adapter, which measures Edge.Cuts centerline coordinates. It measures the main board at 140×100 mm and the ESC board at 173.8×282.93 mm. The parsed generator placeholders are 140×100 and 150×150 mm respectively, so the ESC outline comparison fails. This uses the source bytes and centerline adapter directly; it does not consume the earlier PR36 stroke-inflated graphic bounds. Component heights, connector service volumes and full installed fit remain BLOCKED. The native mech audit lists seven servo positions, while the pinned arm MCU map exposes six distinct PWM nets; that interface gate fails. The pinned Rev-B architecture has six independent motor channels.

## Preliminary bounds

At the current 36 mm rotor pitch, zero-clearance can-overlap bounds are 36 mm for the 72 mm CAD/issue variants, 34 mm for the donor-note 70 mm can and 24 mm for the donor-note 60 mm can. A can-only zero-overlap pitch lower bound is therefore 72 mm for the modeled envelope, 36 mm above the present pitch. If both inter-row gaps increase by that amount while the existing flowpath end allowances stay fixed, the arithmetic module-length bound is 110 + 2×36 = 182 mm. This does not create a valid layout: the existing inline motor cans also cross downstream rotor/stator stations, and no revised native row stack exists. Axial spacing is therefore BLOCKED as a candidate pending complete solids and a native aero/performance comparison.

For two equal cans that must stay wholly inside one Ø78 mm bore while their axial spans overlap, the largest possible center separation is the bore diameter minus the can diameter. The Ø42 mm CAD can permits at most 36 mm separation against 42 mm required, a 6 mm shortfall. A Ø36 mm can has a necessary cross-section bound of 42 mm available against 36 mm required, but that does not provide a shaft, transmission, mounts, cooling, or service access. An external motor/shaft/belt/gear package remains BLOCKED because those dimensions and evidence do not exist in the source set.

The fewer-stage scenario is explicitly an assumption of two driven rows per duct. It would reduce the motor count from six to four and leave two of the six independent ESC motor channels unused, requiring a linked architecture change. Removing two donor-note 3670 motors gives only a motor-component mass sensitivity of −0.540 to −0.552 kg before supports, transmission, rotors, or thermal changes; all system mass and performance effects remain BLOCKED. The shorter-motor screen fails at current pitch for every documented can-length variant.

These scenarios are not ranked. The native evidence and preliminary outputs are recorded in [issue2_motor_drive_feasibility_screen_stockfix_ff670.json](issue2_motor_drive_feasibility_screen_stockfix_ff670.json); its SHA-256 is `f204c1775890229df303e09872a2c61eff5355a30b8b6c74efeed97e6d3302e6` for the executed run summarized here.

## Reproduction

Use the clean mech candidate checkout at `ff670b80b2b3ce925b03d14a91329bb7940e73d7` and a sibling arm checkout containing the pinned board source files. The arm checkout may be on another commit if the pinned input paths still match the declared Git blobs; any changed or missing bytes fail the screen.

```bash
python -m pytest -q highspeed_edf/verification/tests/test_motor_drive_screen.py
python -m highspeed_edf.verification.motor_drive_screen \
  --source-root . \
  --arm-source-root ../drone-arm \
  --inputs highspeed_edf/phase15/configs/motor_drive_screen_sources.json \
  --json highspeed_edf/phase15/reports/issue2_motor_drive_feasibility_screen_stockfix_ff670.json
```

The focused adversarial suite passes 10 tests, including a positive-volume baseline collision check, a native OCC case where AABBs overlap but solids do not, a zero-overlap boundary, bad units, source-byte tampering, a missing motor STEP, and a changed external PCB blob. The screen command exits 1 because it detects the current baseline and shared integration failures; it writes the JSON evidence before returning that status. No paid compute, physical testing, manufacturing, or flight was run.

## Remaining blockers

Issue #2 is not complete. Before a physical layout can be compared, resolve the motor identity conflict with a source drawing or actual measured package for the selected SKU, including the can, bearing/end-cap, shaft shoulder/protrusion, cooling and wire exit. Define the shaft/transmission architecture and complete mounting/service envelope from sourced dimensions. Then generate complete candidate solids and compare clearances, assembly access, mass/CG, material/manufacturing requirements and electrical/thermal effects. Native aero and rotor/containment qualification remain separate BLOCKED gates. No motor or propulsion geometry was edited in this revalidation. The stock-nest STEP changes are separate and do not alter the six pinned motor STEP files.
