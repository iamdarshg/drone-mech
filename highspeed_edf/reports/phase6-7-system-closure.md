> **OBSOLETE — SUPERSEDED.** See `../OBSOLETE.md` and `../design/PHASE15_DESIGN_SPEC.md`.
> This file describes a superseded configuration (90 mm geared FA4119, old mass
> basis, 75 cm2 frontal-area gate, CdA 0.0009 m2). Do NOT use it to size or build.
# Phases 6–7: variable-area schedule and integrated system closure

**Scope:** application-specific analytical post-processing of Phase-3 meanline/area sensitivities, Phase-4 ROSS results, and Phase-5 electrical/thermal assumptions. No CFD, physical geometry, native solver job, or GCP job was run. All findings remain screening results.

Configuration SHA-256: `08e15cf9f7d49459a0cb4421a22108a77457f0355f47b0fddc396f53035d7871`. Cloud spend: **$0.00**.

## Phase 6 — core-annulus / bypass-area schedule

The 80 mm casing / 32 mm hub provides 4222 mm² of annulus area. Phase 3 sized the core area to meet the 50,000 stator-Reynolds floor in an ideal continuity model: 2628→3672 mm² from 500 to 700 km/h. This corresponds to a 66.1→75.5 mm core outer diameter, leaving progressively less annulus for bypass flow.

| Speed | Core OD | Core area / available annulus | Remaining geometric bypass annulus | Axial velocity at Re floor |
|---:|---:|---:|---:|---:|
| 500 km/h | 66.1 mm | 62.3% | 37.7% | 224.7 m/s |
| 550 km/h | 68.5 mm | 68.3% | 31.7% | 215.3 m/s |
| 600 km/h | 70.9 mm | 74.6% | 25.4% | 205.5 m/s |
| 650 km/h | 73.2 mm | 80.7% | 19.3% | 196.7 m/s |
| 700 km/h | 75.5 mm | 87.0% | 13.0% | 187.8 m/s |

A 10% core-area margin at 700 km/h requires 78.5 mm core OD and leaves only 4.3% of the casing annulus. A 15% margin exceeds available annulus area and cannot coexist with an open bypass path at this hub/casing size. These margins are sensitivity cases, not measured contraction-loss allowances.

The table describes core/bypass annulus area allocation only. It does not determine nozzle throat areas, pressure matching, bypass flow fraction, actuation forces, stability, or the passive cam/spring geometry. The area schedule is a candidate command curve for follow-on mechanism design, not a validated variable-bypass solution.

Detailed outputs: `results/phase6_core_bypass_schedule.csv` and `results/phase6_area_margin_sensitivity.csv`.

## Phase 7 — integrated electrical, speed, and readiness screen

| Speed | Bus power | Pack current (10 mΩ) | Max motor current/channel | Max ideal-Kv phase-current estimate | Max motor rpm | Ideal energy duration (70–90% of 222 Wh) |
|---:|---:|---:|---:|---:|---:|---:|
| 500 km/h | 10.10 kW | 212 A | 46.4 A | 62.7 A | 10319 rpm | 55–71 s |
| 550 km/h | 12.48 kW | 265 A | 57.4 A | 73.8 A | 10862 rpm | 45–58 s |
| 600 km/h | 15.25 kW | 328 A | 68.8 A | 84.5 A | 11604 rpm | 37–47 s |
| 650 km/h | 18.44 kW | 403 A | 82.3 A | 95.3 A | 12464 rpm | 30–39 s |
| 700 km/h | 22.07 kW | 492 A | 94.4 A | 106.2 A | 13323 rpm | 25–33 s |

The duration figures are ideal energy ceilings at constant Phase-3 power; they ignore voltage sag/cutoff, thermal derating, reserve, and any mass increase. The current Phase-3 bus demand reaches 22.07 kW. At the 600 km/h baseline the pack-current estimate is already near the 330 A six-channel soft threshold, while the highest channel exceeds its soft current and the ideal-Kv phase-current estimate exceeds the assumed 60 A RMS continuous ESC limit.

The ideal-Kv-derived phase-current values are convention-sensitive torque-current estimates, not measured ESC phase RMS currents. Their comparison with the 60 A RMS contract is an early warning screen only; it requires confirmation from the ESC/motor current convention and first-article telemetry.

Every sampled speed fails at least one conservative readiness gate. The lowest sampled point, 500 km/h, is the least demanding electrical case but still has a 62.7 A ideal-Kv phase-current estimate and an unresolved startup crossing of the approximately 18433 rpm ROSS first critical. At 700 km/h, requested bus power is 22.07 kW, pack current exceeds the provisional six-channel short-current cap in the 10 mΩ screen, and the Phase-5 cutoff cases terminate before requested burst duration.

The 75 cm² projected-frontal-area checkpoint remains unverified: it is an assumed requirement checkpoint, not a measured CAD projection. CdA remains a separate Phase-2 analogue input. No user-specified mission duration/range was available, so the table is not a range estimate.

### Readiness disposition

- **Not ready for hardware release or flight validation.** No sampled speed clears the combined soft-current, continuous phase-current, motor soft-RPM, startup-resonance, and geometry-verification gates.
- **Dominant closure items:** validate stator Reynolds assumptions and core/bypass split; provide actual CAD frontal area and duct/actuator mass; resolve rotor startup critical crossing; measure battery pack OCV/DCIR/pulse thermal response; dyno-test motor/ESC torque-speed and loss maps; define a mission profile.
- **Cost:** local post-processing only, no cloud spend.

Detailed speed gates and endurance ceilings: `results/phase7_integrated_speed_envelope.csv`.

