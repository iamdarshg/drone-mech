> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phase 9 — fixed-powertrain geometry, weight, T/W and speed envelope

## Locked hardware and mass basis

The six FA4119 motors and the series pair of Turnigy Rapid 6S 5000mAh packs remain unchanged. Motor mass is 280 g each from the drone-arm FA4119 decision record; battery mass is 713 g each from the [Turnigy Rapid product specification](https://speedyfpv.com/products/turnigy-rapid-6s-5000mah-22-2v-100c-lipo-battery-w-xt90-for-rc-cars). The flight-control and ESC PCB material masses below are calculated from their committed KiCad outlines, dielectric stackups, and actual copper-layer area exported by KiCad—not guessed from board dimensions alone.

| Item | PCB/bare mass calculated | Copper fill / stack notes |
|---|---:|---|
| Rev-B ESC main PCB bare | 70.2 g | 6 Cu layers; FR-4 42.5 g + copper 27.2 g + mask 0.5 g |
| Rev-B flight-control PCB bare | 50.4 g | 4 Cu layers; FR-4 37.3 g + copper 12.8 g + mask 0.3 g |

Sourced motors weigh 1.680 kg total; the two packs weigh 1.426 kg. Including bare board materials, the known lower bound is 3.227 kg. The 11.5 kg candidate therefore leaves 8.273 kg for populated electronics, motor heatsinks, power wiring, six rotors/gears, ducts, inlet structures, fuselage, landing gear, servos and payload. BOM assembly weights for the populated control boards, heatsinks, harness and frame are not stated in drone-arm, so this is a mass budget, not a scale reading.

**Source conflict:** the actual ESC `.kicad_pcb` is six copper layers (150×150 mm); `REV_B_ARCHITECTURE.md` describes four layers. The mass result follows the saved board stackup. Resolve that hardware revision inconsistency before fabrication/mass freeze.

## Geometry candidate (motor/battery unchanged)

- Two axially staggered **90 mm OD / 32 mm hub** fan ducts. Their front projections are coincident, giving a 63.62 cm² circle envelope; 10 cm² is reserved for all other projected structure/controls, total **73.62 cm²**, below 75 cm².
- Two side-facing flush inlet slots, each 50×120 mm from the allowed stock width, provide 120 cm² total opening against 111 cm² total fan annulus. Side openings do not add to the nose-on projected frontal silhouette; inlet recovery/local losses still need validation.
- Rotor radial span is 29.0 mm, within 50 mm stock; rotor chord remains 16 mm. Raise stator chord from 5 to 8 mm within the stock envelope to recover Reynolds margin, retaining the current blade counts as the initial build.
- Fuselage target: CdA≤0.00090 m² at 720 km/h (equivalent Cd≤0.122), with a 11.5 kg all-up mass target. A low-drag slender center fuselage and side inlet capture are needed; smooth areas/equivalent polar are assumed, not measured.

## Requirements screens

At 3 km, 11.5 kg with the 90 mm annulus and Phase-1 ηfan=0.8 sensitivity gives T/W=1.040 at 55 A/motor, using the worst 30 mΩ pack sensitivity. The provisional 75 A/motor point gives T/W=1.200; its duration remains unvalidated. Sea-level T/W is higher. The candidate clears T/W≥1 across the R0 sensitivity only if the 11.5 kg all-up mass is achieved.

For the 720 km/h, 3 km, CdA=0.00090 target, the single-stream ideal-gas model predicts 12.93 kW bus power after the unchanged 95% gearing assumption. At the worst screened R0=30 mΩ, the pack soft-current (330 A) initial power cap is 13.17 kW; equal six-channel current is about 53.7 A against 55 A. The speed sweep: 

| Speed | CdA | Bus power | Soft 330 A case | Hard 390 A case | Provisional 450 A case |
|---:|---:|---:|---|---|---|
| 701 | 0.00090 | 11.81 kW | pass | pass | pass |
| 710 | 0.00090 | 12.07 kW | pass | pass | pass |
| 720 | 0.00090 | 12.93 kW | pass | pass | pass |
| 730 | 0.00090 | 12.66 kW | pass | pass | pass |

A candidate six-row 720 km/h meanline solve is also recorded: 6/6 rows pass, continuity residual 5.87e-08, and equal-share motor current 43.3 A. Its ideal nozzle momentum thrust is 1.020× required drag. Motor RPM stays at/below 12,500; the ideal-Kv torque-current estimate peaks at 54.6 A versus the 60 A RMS ESC continuous contract. The current convention and fixed-blade off-design performance need hardware confirmation.

## Outputs and verification

- `results/phase9_control_board_mass.csv` — KiCad copper/fiberglass board material calculations.
- `results/phase9_mass_budget.csv` — fixed known masses and remaining airframe/propulsion allowance.
- `results/phase9_static_twr_screen.csv` — T/W by altitude/current cap.
- `results/phase9_speed_envelope.csv` — fixed-pack/motor power and CdA envelope.
- `results/phase9_geometry_mass_summary.json` — candidate dimensions, projected area, mass allowance and source notes.

No motor, battery, voltage, capacity, or per-channel current limit was changed. Blade/fuselage geometry and derived total mass are the only design levers in this screen. Powertrain efficiency and pack DCIR remain the Phase-1 analyst assumptions, not measured hardware data.

