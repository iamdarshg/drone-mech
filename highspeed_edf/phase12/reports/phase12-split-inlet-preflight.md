# Phase 12 — four-slot split-turn OpenFOAM sweep preflight

## Candidate state

The Phase-9 powertrain remains fixed: six stock FA4119 KV350 motors, 12S1P 5Ah battery, six channels, unchanged 55 A/motor soft limit and 60 A ESC limit. The 720 km/h / 3 km freestream is Mach 0.60869 with total state 90.038 kPa and 288.557 K. Phase 9's 1.71748 kg/s meanline flow divides into two ducts and then two branches per duct: **0.429371 kg/s per branch**.

Each 25×120 mm slot has 30.0 cm² area. Each branch outlet is assigned half the nominal 90/32 mm annulus area: 27.7874 cm². The area ratio is 1.07963, matching the target shallow 7.4% contraction. At that flow the derived inlet Mach is 0.4315; an ideal branch outlet at the 0.98 recovery target is Mach 0.4904 / static pressure 74.858 kPa. The ideal choked mass-flow bound is 0.59525 kg/s per branch, above the 0.42937 kg/s target.

The branch outlet mesh is an **equivalent-area circular patch**, diameter 59.481 mm, equal in area to half an annulus. It does not resolve the two branches' splitter/merger mixing or rotor-face circumferential distribution. Four meshes were generated: R35 coarse/medium/fine and R45 medium.

## Local mesh and syntax preflight

Gmsh 4.x generated linear tetrahedral meshes locally:

| Case | Cells | Minimum SICN |
|---|---:|---:|
| R35 coarse | 7,201 | 0.133 |
| R35 medium | 13,780 | 0.164 |
| R35 fine | 20,840 | 0.222 |
| R45 medium | 14,215 | 0.180 |

The OpenFOAM dictionaries passed a local static required-file and brace-balance check. That is not a solver parser or mesh-quality validation. This workstation has no local `checkMesh`, `gmshToFoam`, or `rhoSimpleFoam` executable; Docker's Linux daemon is stopped, and the Ubuntu-24.04 WSL image failed to attach its VHDX. Therefore **neither candidate passed a real local `checkMesh`**, so the required launch gate is closed. No GCP VM, GCS object, or solver process was started for Phase 12.

## Installed-area screen

With a 90 mm fan-union area of 63.617 cm² and the 10 cm² structure/control reserve, the conservative front projection adds an outboard strip for each distinct slot turn. Even assuming the axially staggered ducts make each pair of branch silhouettes coincide, two opposite-side paths give:

| Centerline radius | Two-path overlap lower bound | Four distinct paths | <75 cm² |
|---:|---:|---:|---|
| 35 mm | 79.62 cm² | 85.62 cm² | fail |
| 45 mm | 103.62 cm² | 133.62 cm² | fail |

This conservative screen uses the 25 mm turn-plane height and 120 mm projected branch span. A final STEP silhouette union is still required for any future topology, but both sampled radii fail even under the two-path overlap assumption. The local result therefore does not identify a system-feasible geometry.

## Spend gate and disposition

The hard **new** Phase-12 run-envelope cap is $0.0271. The plan allows one `e2-standard-2` Spot worker for 420 seconds at a conservative $0.20/hour (compute ≤$0.02334), with ≤$0.003 ancillary allowance including temporary disk, network, artifacts and contingency; maximum estimate is $0.02634. Phase-10/11 prior envelope use is estimated at $0.17289, keeping the combined estimate ≤$0.20. The worker was **not launched** because local `checkMesh` was unavailable; actual Phase-12 cloud spend is $0.

Machine-readable preflight and cost/lifecycle receipts are in `../results/`. No pressure recovery, CFD convergence, candidate ranking, full-aircraft 720 km/h result, or CNC operation is claimed.
