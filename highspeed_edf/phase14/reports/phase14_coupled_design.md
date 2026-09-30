# Phase 14 — coupled airframe / ESC / actuator concept freeze

## Disposition

Phase 14 freezes a concept and a hardware-facing control contract against the
existing six-channel FA4119 / 12S baseline. It is an analytical design screen,
not a flight-release package. The accepted path uses the exact three aluminium
stocks requested: the 300×50×16 mm bar for six rotor hubs, and the 250×120×5 mm
plus 300×120×5 mm sheets for rotor blades and stator vanes. The carbon-fibre
wrapped PLA lifting body remains the primary airframe construction.

The coupled 650–720 km/h, static T/W, 0–700 km/h control-authority, and material
screens are summarized in `../results/phase14_closure_summary.json`; detailed
rows are in the accompanying CSV files. Re-run the local closure with:

```powershell
python highspeed_edf/phase14/optimization/phase14_close_design.py
```

No cloud job or GCP spend was used.

## Frozen reference interface requirements

The design uses six stock Flycci FA4119 KV350 motors (7 pole pairs), two 6S
5000 mAh packs in series (12S1P, 5 Ah, 50.4 V fully charged), and the drone-arm
Rev-B six-channel ESC/main-board topology. ESC battery current and phase RMS
current remain separate limits:

| Parameter | Requirement |
|---|---:|
| Motor speed soft rollback / hard shutdown | 12,500 / 13,500 mechanical rpm |
| Corresponding motor electrical speed | 87,500 / 94,500 eRPM |
| Battery-current soft / hard limits | 55 / 65 A per motor |
| Provisional battery-current short ceiling | 75 A per motor; no duration credit |
| ESC phase-current continuous / burst | 60 / 90 A RMS per channel; burst time unvalidated |
| Maximum pack voltage | 50.4 V |
| ESC communication | independent channel command and telemetry over CAN-FD |

The six motor channels remain independent. Per-channel commands must be
watchdog-protected; the final CAN-FD bitrate, command schedule, timeout and
telemetry protocol are firmware acceptance items, not schematic assumptions.

## Coupled propulsion and airframe

- Retain the two 90 mm / 88 mm-bore duct modules, 32 mm rotor hubs, and three
  driven rotor rows per module. Keep the projected duct outlines coincident to
  preserve the inherited compact frontal-area screen.
- Retain the R30 split-inlet packaging candidate pending an actual pressure-
  recovery result. The previous OpenFOAM cases did not iterate and therefore
  provide no pressure-recovery evidence.
- Route the common EDF discharge to four independently actuated exit vanes.
  Combine those propwash vanes with left/right elevons on the carbon-wrapped
  lifting body. Propwash vanes supply a control path at zero airspeed; elevons
  take increasing authority as dynamic pressure rises. This is the selected
  control architecture, not yet a validated control-allocation result.
- Place the ESC and flight-control boards near the CG, edge-on in a sealed,
  forced-air side bay. Keep the six battery feeds and high-current loops local
  to the ESC cells. Give the MOSFET heat spreader a metal-to-air path and
  electrically isolate it from the TOLT packages and carbon skin.
- Keep PLA core temperature at or below 45 °C, providing margin below typical
  PLA glass-transition temperatures. Route hot motor/ESC exhaust away from the
  printed core. Coupon, adhesive, impact, and hot/wet tests are still required;
  carbon wrap does not make an unqualified PLA laminate flight-safe.

### Stock nest using only the specified metal

There are 72 rotor blades (13/12/11 per module) and 126 stator vanes (23/21/19
per module). At the inherited 29×8.2 mm blank envelope, 1.5 mm part spacing,
and 1 mm sheet-edge margin, simple grid nests provide 96 positions in the
250×120 sheet and 108 in the 300×120 sheet. Allocate 63 stators plus 33 rotor
blades to sheet A, and 63 stators plus 39 rotor blades to sheet B. Six Ø32 mm
hub blanks fit within the 250 mm usable length of the 300×50×16 mm bar while
retaining 25 mm end clamp zones. Integrate stator support rails into the
composite duct rather than consuming a separate aluminium plate.

The three raw 6061-T6 stocks weigh approximately 1.539 kg in total at
2,700 kg/m³. These are blank-envelope counts only: tool clearance, tabs,
workholding, detailed blade surfaces, retained hub geometry, fasteners, rotor
root capture, fatigue, burst containment, and CNC simulation are not closed.
The old Phase-13 CAM outputs use six bars and two 250×100 plates; they are not
valid CAM for this one-bar/two-sheet revision. A separate 3D indexed machining
and rotor-retention drawing is required before cutting. The 198 blanks are
72 rotor blades plus 126 stator vanes—not 198 parts with 90 mm diameter. The
300×120 sheet exactly consumes the cited 3018 machine's nominal X travel, so
that machine has no fixture/approach margin. The detailed CNC feasibility and
motor/EDF scaling comparison are in `phase14_scale_analysis.md`.

## Performance screen and limits

For a 3 km ISA, CdA = 0.00090 m² model, the inherited 12.93 kW bus-power
estimate at 720 km/h is used to calibrate an aggregate propulsive-efficiency
factor. It predicts about 9.5 kW at 650 km/h, 11.9 kW at 700 km/h, and 12.93 kW
at 720 km/h. These points sit below the inherited 13.17 kW six-channel soft
power screen, with only about 0.24 kW (1.9%) analytical margin at 720 km/h.
This calibration is not a measured fan, motor, gearbox, battery, or ESC map.
The 650+ km/h cruise requirement is therefore a candidate, with 720 km/h as
the design point—not a demonstrated operating envelope.

The inherited 11.5 kg static T/W=1.03955 point implies 117.24 N static thrust.
Using the physical 88 mm bore / 32 mm hub annulus and fixed ideal actuator-disk
power gives an upper-bound thrust of 90.1 N at 200 km/h at 3 km. Thus the old
10.5 kg target **fails** the user's 0–200 km/h T/W requirement in the forward
flight screen (T/W≈0.875 at 200 km/h). The ideal upper-bound maximum mass for
T/W≥1 throughout 0–200 km/h is only 9.187 kg. Phase 14 therefore lowers the
aircraft target to **≤8.5 kg all-up**, which screens at approximately 1.08 T/W
at 200 km/h before real inlet/nozzle/duct losses. The inherited Phase-13
planned ledger was 8.149 kg including a 2 kg payload allowance, so the target
leaves only about 0.35 kg for actuator additions and growth; payload or other
mass must be reduced if the actual build exceeds 8.5 kg. This remains an ideal
upper bound, not a demonstrated T/W pass. Measure an installed thrust curve at
0/50/100/150/200 km/h equivalent flow conditions; include the stated 30 mΩ
pack sensitivity and do not use the unvalidated 75 A short-current point to
claim margin.

At 8.5 kg, the ideal disk model needs about 8.28 kW of disk power (about
11.90 kW bus power after scaling to the inherited soft-power point) to make
T/W=1 at 200 km/h: roughly 1.98 kW bus input per motor. The 720 km/h cruise
screen is 2.16 kW per motor; therefore a 720-capable replacement should be
screened at **≥2.2 kW continuous electrical input per motor**. Capping maximum
speed at 650 km/h reduces cruise demand to 1.59 kW per motor, but leaves the
200 km/h low-speed thrust demand near 2.0 kW per motor. A lower-rated motor
does not remove the thrust requirement. A smaller-motor trade is worth testing
only in the 12S EDF-rated 35–40 mm stator / ≤250 g class, and only with a
continuous EDF cooling rating or guarded 12S dyno map at the required RPM,
current, and temperatures. The 2.2 kW value is bus input, not a shaft-power
rating; derive shaft output from measured efficiency. Until a candidate proves
that map, keep the 41×19 mm, 280 g FA4119 baseline.

The area-averaged dynamic pressure at 3 km is effectively zero at rest, about
1.40 kPa at 200 km/h, 8.77 kPa at 500 km/h, and 17.19 kPa at 700 km/h. This is
why the concept carries exit vanes as well as aerodynamic surfaces. Quantify
control reserve as available moment divided by trim-plus-disturbance demanded
moment: **strong ≥1.5× from 0–500 km/h; medium ≥1.1× from 500–700 km/h**. The
airframe mass/inertia tensor, vane/elevon derivatives, actuator slew/hinge
loads, and duct-exit flow map do not yet exist, so those authority bands are
requirements rather than results.

## Finalized control-hardware contract

Use six independently controlled effectors: left and right elevons plus four
exit vanes, each with position feedback. The reference flight-control board
already has six PWM outputs; drive the custom ESC over CAN-FD to leave those
six outputs available for effectors. The board-level interface must support:

- at least 400 Hz command updates and at most 10 ms command-to-actuator
  latency;
- at least 200 Hz position feedback, with a stale-feedback fault by 20 ms;
- a separately regulated, externally sourced high-current actuator rail,
  sized from measured actuator stall current (never from the ESC's 1 A flight
  board auxiliary output);
- fail-safe command behavior, actuator jam/stall detection, and a degraded
  control allocation after any one actuator fault;
- six ESC channels at 1 kHz minimum supervisory command/telemetry schedule,
  with channel identity, RPM, current, temperature, command age, and fault
  status carried in the protocol.

The motor reference requires winding-temperature rollback at 100–110 °C,
shutdown at 120 °C, bell/magnet warning at 70 °C, and shutdown at 80 °C. Rev-B
has one thermistor per ESC cell on the board; that measures local board
temperature, not motor winding and bell temperature. The finalized interface
therefore requires two motor-mounted temperature sensors per channel (12 total),
open/short detection, calibration data, and telemetry/rollback in firmware.

Two control-hardware gaps were filed against the reference repository:

- [Define six high-speed airframe actuator interfaces](https://github.com/iamdarshg/drone-arm/issues/18)
- [Add per-motor winding and bell temperature inputs](https://github.com/iamdarshg/drone-arm/issues/19)

They complement, and do not replace, the existing routing, physical
qualification, and route-level EM issues.

The four idealized tangential vane force directions have a rank-3 pitch/yaw/roll
moment allocation with the exit behind the CG. This verifies geometric
controllability only; vane force magnitude, flow distortion, hinge loads,
elevon authority, actuator response, and faulted allocation remain unmodeled.
See the [concept sketch](phase14_control_airframe_concept.svg).

## Required closure before flight claims

1. Generate new exact-stock nests and 3D blade/hub retaining features, reimport
   STEP, simulate every toolpath, and weigh the built rotor assemblies.
2. Obtain motor shaft/gearbox CAD and measured FA4119 torque-speed/current/loss
   maps; confirm the selected ratios and rotor speed limits on the guarded rig.
3. Reconcile the Rev-B PCB layer-count/stackup discrepancy and release the
   exact ESC/main-board routing and BOM before physical qualification.
4. Add motor winding/bell thermal inputs and the six-effector actuator
   electrical/feedback interface; close drone-arm issues #18 and #19.
5. Identify actuator and servo-rail ratings from measured hinge loads and stall
   current; implement the allocation, timeout, jam, single-fault, and safe-state
   behavior.
6. Run installed 0–200 km/h thrust tests, 0–700 km/h control-effectiveness
   tests, inlet/exit CFD correlated to a flow rig, flutter/structural analyses,
   laminate coupons, and a contained rotor overspeed program.
7. Weigh the complete aircraft and verify mass ≤8.5 kg, measured CdA ≤0.00090
   m² at the selected cruise condition, and all required reserves with margins.
