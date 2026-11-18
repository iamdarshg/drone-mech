# DM-G7 (partial): CG, mass and inertia closure from CAD positions — 2026-11-18

DM-G7 has four parts: CG/mass closure, the 7-actuators-vs-6-PWM conflict (F-05), power/thermal, and rotor containment. This report covers **CG/mass/inertia** only.
- F-05 and F-10 stay owner decisions (X-02/X-03). The CAD makes F-05 concrete: it contains **7 servo mounts** (vane A1, A2, B1, B2, elevon L, elevon R, rudder).
- Power/thermal and containment are not addressed here.

Inputs:
- Phase-15 assembly STEP, sha `9b83f3bf…`, 516 solids.
- Per-solid volume, centroid and unit-density inertia from OCC (`tools/dm_g2/dm_g7_solid_props.py`).
- Spec §16 nominal masses (`design/PHASE15_DESIGN_SPEC.md`), distributed over the CAD solids of each row by volume (`tools/dm_g2/dm_g7_mass_cg.py`).

Datum: X lateral (+right), Y vertical, Z aft+, origin at the fan plane. Raw: `reports/dm_g7_20261118/`.

## Method and assumptions (all stated, none hidden)
- Every one of the 516 solids is assigned to a §16 row by name (0 unassigned).
- Within a row, mass is spread by volume. This is exact for identical parts such as the 6 motors and approximate elsewhere.
- Three rows have **no CAD solid**, so they are placed at proxy locations:
  - harness/connectors/fuses (0.25 kg) and avionics (0.20 kg): at the ESC/FC electronics centroid (z = +262 mm);
  - payload (1.00 kg): at the battery-bay centroid (z = −207.5 mm).
- The 15 % growth reserve is excluded (it does not move the CG if spread proportionally).

## Results

| quantity | CAD-position result | spec | verdict |
|---|---:|---|---|
| total (spec nominal rows) | 5.84 kg | 5.84 | by construction |
| CG x (lateral) | +0.13 mm | 0 ± 3 | in window |
| CG y (vertical) | +5.68 mm | −5 … +10 | in window |
| CG z (longitudinal) | **+16.0 mm** | −5 … +15 | **1 mm aft of the window** |
| I pitch (about X) | 0.182 kg·m² | 0.15–0.25 | in range |
| I yaw (about Y) | 0.194 kg·m² | 0.20–0.35 | just below range |
| I roll (about Z) | 0.0236 kg·m² | 0.025–0.08 | just below range |
| product Iyz | −0.011 kg·m² | not given | non-zero yaw–roll coupling (the tail/fin and electronics sit above the body axis) |

These replace the spec's "uniform-body estimate" with CAD mass properties, within the stated mass-distribution assumption. The swing test the spec calls for is still needed.

**The CG result is not robust.** The 0.45 kg of harness and avionics has no CAD location, and placing it is enough to sweep CG z across the window:

| harness + avionics placed at | CG z |
|---|---:|
| ESC/FC centroid (+262 mm), as modelled | +16.0 mm |
| fan plane (0 mm) | −4.2 mm |
| battery bay (−207.5 mm) | −20.2 mm |

**The trim mechanism has no travel.** The spec trims CG with a "battery slide", but in CAD:
- the rails run z −300 … −115 mm, with end stops at −295 and −120;
- the two 185 mm Bonka packs occupy exactly z −300 … −115.

So the slide range is **0 mm**. With payload at the bay, hitting CG z = +5 mm would need the battery moved about 115 mm forward, or the payload placed at z ≈ −272 mm.

## Mass closure: the structure rows look 2–5× too light
The spec books **0.27 kg** for the lifting-body shell plus **0.28 kg** for duct/inlet composites, 0.55 kg in total. From CAD:
- **Composite skin over the wrapped outer surface (0.892 m², DM-G2 wrap)** at ρ = 1.5 g/cm³ and the spec's own §17 shell thickness of 0.8 / 1.2 / 2.0 mm: **1.07 / 1.61 / 2.68 kg**.
- **The lifting-body solids as drawn (3,132 cm³)** printed in PLA (§17 "PLA core", ρ 1.24): 0.39 kg at 10 % infill, 0.78 kg at 20 %, 3.88 kg solid. This comes on top of any skin.

Even the thinnest documented skin is about 2× the booked composite mass. At the nominal 1.2 mm skin, the subtotal rises by about 1.05 kg (5.84 → about 6.9 kg), and with the 15 % reserve the all-up mass is about 7.9 kg against the 8.5 kg maximum. The thrust-to-weight margin should be re-checked against this.

## Verdict for the CG/mass part of DM-G7: FAIL (not closed)
- CG z lands 1 mm outside the window under the modelled placement.
- It swings −20 … +16 mm on an unmodelled 0.45 kg.
- The documented trim mechanism has 0 mm travel.
- The structure mass rows are inconsistent with the documented shell thickness.

Closing it needs owner inputs:
1. CAD locations for the harness, avionics and payload.
2. Battery rails with real travel, or a ballast plan.
3. A documented layup with mass, which is also what DM-G5 needs.

Then rerun `dm_g7_mass_cg.py` with the measured component masses.
