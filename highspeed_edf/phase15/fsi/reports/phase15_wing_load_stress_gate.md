# Phase-15 preliminary wing load-demand screen

**Status: BLOCKED.** This is an analytical load-demand calculation, not FEA, not a stress result, and not structural validation.

Provenance is fail-closed: report generation checks every listed SHA-256 against a fixed allowlist; changed or missing inputs stop generation until the reviewed pin is deliberately updated.

Candidate inputs: 6.541 kg, 0.190 m² wing area, 0.520 m span, 0.425/0.305 m root/tip chord, 200 m/s at 3 km ISA density 0.909 kg/m³. Dynamic pressure is 18.18 kPa; 1g lift requires CL=0.0186.

The model assigns half the symmetric aircraft lift to each half-wing and distributes it in proportion to linearly tapered chord. This places the half-wing lift centroid at 0.1229 m outboard of the root.

| Sensitivity load | Lift per half-wing | Root bending moment per side |
|---:|---:|---:|
| 1.0 g | 32.07 N | 3.941 N·m |
| 2.0 g | 64.15 N | 7.882 N·m |
| 3.0 g | 96.22 N | 11.823 N·m |

The load-factor cases 1g, 2g, and 3g are sensitivity points; the source files do not define an aircraft maneuver/gust envelope. The design specification lists wing structure safety-factor targets of 2.0/3.0/4.5. Applying those multipliers to the root moment and dividing by hypothetical 100/250/500 MPa allowables gives section-modulus demand sensitivities, but the allowables are intentionally not treated as carbon laminate properties. See the JSON output for values.

## Blocking evidence

The materials audit says the supplier/product identity, laminate layup, coupon allowables, temperature/adhesive qualification, measured masses, and manufacturing traveler are absent. The existing FSI case is an outboard wing-sector mesh with an equivalent isotropic 10 GPa / 150 kg/m³ seed. In the recorded 2026-09-30 attempt, OpenFOAM exited on missing `div(meshPhi,p)` in `fvSchemes`; preCICE/CalculiX then lost its peer, and the receipt contains no tip-displacement result. Native solver availability at report generation: gmsh=unavailable, ccx=unavailable, CalculiX=unavailable, rhoPimpleFoam=unavailable, gmshToFoam=unavailable. No stress result is available.

Unavailable inputs:

- as-built wing CAD including carbon skins, spar/web, core and joints.
- hand layup ply orientations, count, fiber volume fraction, cured thickness and resin system.
- coupon-derived tension/compression/shear allowables and hot/wet/environment knockdowns.
- validated 3D CFD pressure field or defined gust/maneuver design envelope.
- measured aircraft mass distribution and wing mass for inertia relief.

Source SHA-256 pins:

- `highspeed_edf/design/PHASE15_DESIGN_SPEC.md`: `d63eb7f3ae8b23476d8077ebb739165a50afba152972269690ccf834446aa5aa`
- `highspeed_edf/phase15/optimization/phase15_aero_multiphysics_screen.py`: `1bb1f7818bf348d1cd3c72c82f3a6644a85af7b709cf4921578b43a30bc20e00`
- `highspeed_edf/phase15/optimization/phase15_fsi_casegen.py`: `f2ea9705c2ea10d5a5ce5145df32944f0c80fbeba35fb4a70961dfea7c36acce`
- `highspeed_edf/phase15/fsi/cases/wing_t36mm/solid/wing.inp`: `ae81cd06d2a976b1a1c4d55ec3c8505a01c7a0ca0b588d041e98427a9f7dd390`
- `highspeed_edf/phase15/fsi/results/attempts/20260930T134329Z/worker_output/wing_t36mm_receipt.json`: `0a6f87e6c8a3ecef48f683d83e472162059d41c6f4f396453989a91f435c02d4`
- `highspeed_edf/phase15/fsi/results/attempts/20260930T134329Z/worker_output/wing_t36mm/rhoPimpleFoam.log`: `8123486174e8c3c11665850ca3cb7cbc32b873aa7b720337c719af996ef74fca`
- `highspeed_edf/phase15/reports/issue4_material_matrix_stockfix_ff670.md`: `7fe8cd706c308bce060e17d576bf69d46355e1ed61716155facfd269ff19db5c`
- `highspeed_edf/phase15/reports/issue4_material_matrix_stockfix_ff670.json`: `1ab93043326b013fcee32ed75b79de2018ea752ec9e230dce430b5c86db4c012`

This report provides no actual stress, reserve factor, deformation, failure mode, or structural acceptance decision.
