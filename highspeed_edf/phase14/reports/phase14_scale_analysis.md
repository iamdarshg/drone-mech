# Phase 14 — coupled motor / EDF / battery scale analysis

## What is actually large in the current ledger

The Phase-13 loaded mass estimate is 8.149 kg, including its 2 kg payload
allowance. Its largest related packages are:

| Package | Estimated mass | Basis |
|---|---:|---|
| Six FA4119 motors | 1.680 kg | sourced 280 g each |
| Six gearboxes | 0.720 kg | analyst allowance, 120 g each; not CAD/sourced |
| Rotor hubs/blades + stators | 0.368 kg | Phase-13 solid-volume estimate |
| EDF cases + four inlet branches | 0.278 kg | Phase-13 composite-shell estimate |
| Lifting-body shell | 0.274 kg | Phase-13 composite-shell estimate |
| **Propulsion package (motors + gearboxes + rotors/stators + cases/inlets)** | **3.046 kg** | mixed sourced/estimated |
| 12S1P 5 Ah battery pair | 1.426 kg | two 713 g packs |
| ESC + flight board, population allowance, spreaders | 0.403 kg | bare PCBs 0.121 kg + allowances |

The EDF/propulsion group is indeed the largest subsystem, but the two boards
and two battery packages are fixed packaging constraints in a smaller-EDF
study: the ESC outline is 150×150 mm, the flight-control board 140×100 mm, and
each pack is modeled as 150×50×45 mm. Keeping the six-channel dorne-arm board
means **the fuselage and board bay cannot simply scale as D² with the fan**.
The battery-pair mass is also close to the entire non-motor EDF hardware mass.

## Scale model and scenario results

Run `../optimization/phase14_motor_edf_trade.py` to regenerate
`../results/phase14_motor_edf_battery_trade.csv`,
`../results/phase14_battery_trade.csv`, and `../results/phase14_cda_scale_trade.csv`. The comparison holds the boards,
payload, non-EDF equipment and board/battery package envelopes fixed. It
scales only explicit duct/inlet skin area, rotor blade span, and stator span;
it does not scale the main fuselage skin. A direct-drive row may subtract the
Phase-13 gearbox allowance (0.72 kg), but only as a clearly labeled
unsourced sensitivity.

All T/W figures are fixed-power ideal actuator-disk bounds at 3 km. Cruise
power is calibrated to the inherited 12.93 kW at 720 km/h and CdA=0.00090 m².
For CdA, I now scale the baseline by projected-area union at a constant
reference drag coefficient: once using the inherited 10 cm² structure reserve,
and once using the Phase-13 detailed union's non-fan area. The fixed ESC/flight
boards and battery package are not scaled. These are geometry estimates, not
smaller-EDF CFD or wind-tunnel results.

| Concept | Duct OD | Max bus input | Estimated AUW | Ideal T/W at 200 | Estimated CdA, 10 cm² reserve | Power limit at fixed CdA | Power limit with area-scaled CdA | R3 speed for same tip speed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Current reference | 90 mm | 13.17 kW | 8.149 kg | 1.127 | 0.000900 m² | 724 km/h | 724 km/h | 36.4 krpm |
| Smaller geared | 90 mm | 10.8 kW | 7.549 kg | 1.045 | 0.000900 m² | 678 km/h | 678 km/h | 36.4 krpm |
| Smaller direct-drive screen | 90 mm | 10.8 kW | 6.921 kg | 1.117 | 0.000900 m² | 678 km/h | 678 km/h | 36.4 krpm |
| Compact fan sensitivity | 80 mm | 10.8 kW | 6.849 kg | 1.047 | 0.000737 m² | 678 km/h | 725 km/h* | 41.1 krpm |
| 80 mm / 4 Ah sensitivity | 80 mm | 12.0 kW | 6.859 kg | 1.109 | 0.000737 m² | 702 km/h | >720 km/h* | 41.1 krpm |
| Aggressive small fan | 70 mm | 10.8 kW | 6.780 kg | 0.958 | 0.000593 m² | 678 km/h | 779 km/h* | 47.2 krpm |

\*Area-scaled power limits above 720 km/h extrapolate beyond the calibrated
point and are not claims of attainable airspeed. They show projected-area
sensitivity before fan maps, inlet/nozzle losses, tip-Mach, motor RPM, and
structure impose additional limits.

### CdA and cruise-power sensitivity

| EDF OD | Projected area: 10 cm² reserve / detailed overlay | CdA: 10 cm² reserve / detailed overlay | Bus power at 650: reserve / detail | Bus power at 700: reserve / detail | Bus power at 720: reserve / detail |
|---:|---:|---:|---:|---:|---:|
| 90 mm | 73.62 / 69.14 cm² | 0.000900 / 0.000900 m² | 9.51 / 9.51 kW | 11.88 / 11.88 kW | 12.93 / 12.93 kW |
| 80 mm | 60.27 / 55.79 cm² | 0.000737 / 0.000726 m² | 7.79 / 7.68 kW | 9.73 / 9.59 kW | 10.59 / 10.43 kW |
| 70 mm | 48.49 / 44.01 cm² | 0.000593 / 0.000573 m² | 6.27 / 6.06 kW | 7.83 / 7.56 kW | 8.52 / 8.23 kW |

This is the favorable trend missing from the fixed-CdA comparison: with
constant reference Cd, reducing fan OD from 90 to 80 mm lowers the projected-
area-scaled CdA estimate by about 18–19%, enough for a 10.8 kW bus cap to cover
the modeled 720 km/h drag power (about 10.4–10.6 kW). However, the 80 mm / 40
mm-hub direct-drive candidate only has ideal T/W≈1.047 at 200 km/h on 5 Ah, so
it is marginal after real propulsive losses. The 4 Ah mass proxy raises that
ideal screen to about 1.09, at a cost in energy and pack C-rate. The 70 mm
geometry has lower modeled cruise power but still fails low-speed T/W at the
10.8 kW motor limit.

The best balanced compact sensitivity is **80 mm / 44 mm hub / 6×220 g direct-
drive motors at 2.0 kW each / 4 Ah packs**: estimated mass 6.859 kg, ideal
T/W≈1.109 at 200 km/h, and 12.0 kW available against roughly 10.59 kW modeled
at 720 km/h under the conservative CdA estimate. It reduces modeled peak bus
power by about 9% versus the 13.17 kW reference while retaining a nominal
power margin. The battery proxy is 67.6 C at the 12 kW motor cap and 82.5 C at
the ESC's 330 A soft-current ceiling; ideal 650 km/h energy time is 67 s. This
is the candidate I would take to motor/EDF packaging and bench mapping next,
not a validated design.

Smaller motors alone receive no separate CdA reduction: their projected
silhouette lies inside the fan-disk union in the current layout, and the
boards/batteries remain fixed. Any additional fairing/body reduction needs a
new dimensioned layout and recomputed projection. Constant-Cd scaling also
does not model Reynolds-dependent friction, smaller-EDF efficiency, inlet
recovery, or nozzle matching; those could consume the estimated gain.

The **90 mm direct-drive sensitivity** is the strongest smaller-motor option:
about 1.23 kg lighter than the Phase-13 loaded ledger, with ideal T/W≈1.117 at
200 km/h and a 678 km/h same-CdA power ceiling. Its 40 mm hub is enlarged from
the prior 32 mm proxy to make room for a smaller inrunner can. It depends on a
180 g motor continuously accepting 1.8 kW in EDF cooling and the six gearbox
allowances being both real and removable. At 80 mm, the rotor annulus loses
33.3% with a 40 mm hub and T/W falls to 1.047; that is too little ideal margin
for real inlet/nozzle/thermal losses. At 70 mm, the same candidate falls below
T/W=1 at 200 km/h.

### Motor speed, pole count, and gearbox trade

The current design gears 12,500 motor rpm to approximately 29.4/33.1/36.4 krpm
rotor rows. Removing the gearboxes requires a genuinely high-speed motor, not
just a smaller version of the 350 Kv FA4119. At unchanged 90 mm rotor diameter,
the R3 mechanical speed is 36.4 krpm; a four-pole-pair motor would present
about 145 keRPM to the ESC. At 80 mm, preserving the same rotor tip speed needs
about 41.1 krpm and 164 keRPM at four pole pairs. At 70 mm it needs about
47.2 krpm / 189 keRPM, leaving very little margin to the dorne-arm 200 keRPM
ESC contract. Lower pole count improves electrical-frequency margin but does
not solve rotor, bearing, shaft, windage, or containment qualification.

The smaller motor class to evaluate is therefore a **12S EDF-specific,
high-speed inrunner or compact low-pole-count outrunner**, roughly 35–40 mm
stator OD, ≤40 mm can/hub package, and 180–220 g. Screen at 1.8 kW/channel
continuous electrical input for a 650–680 km/h cap, 2.0 kW/channel for near-
700 km/h operation, and 2.2 kW/channel for the 720 km/h design point. These are
per-channel bus-input requirements, not shaft-power ratings. No qualifying
catalog motor has been established; do not treat a propeller burst rating as
an EDF continuous rating. If no motor meets the bench map and thermal limits,
keep FA4119/geared or relax the speed target.

The modeled 40 mm hub equals the assumed motor-can envelope and has no added
assembly clearance. A real motor can, bearings, shaft support, insulation,
and blade-root capture may require a larger hub; any such increase further
reduces the small-fan T/W values. Motor prices and gearbox replacement prices
are not available in the source ledger, so this is a mass/power trade, not a
validated cost saving.

## Battery sensitivity

The capacity-only mass proxy yields:

| 12S pack capacity | Pair mass proxy | Saving | C-rate at 330 A soft cap | Ideal 650 km/h energy time |
|---:|---:|---:|---:|---:|
| 5.0 Ah | 1.426 kg | — | 66 C | 84 s |
| 4.0 Ah | 1.141 kg | 0.285 kg | 82.5 C | 67 s |
| 3.5 Ah | 0.998 kg | 0.428 kg | 94.3 C | 59 s |

The 4 Ah pack is a plausible mass experiment only after pack DCIR and thermal
tests; 3.5 Ah runs too close to the advertised 100 C at the existing soft cap.
The size figures remain fixed in the trade table because no matching smaller
pack package or power qualification is sourced. Lower capacity improves mass,
not T/W from a motor/EDF change, and cuts endurance almost proportionally.
In the 80 mm / 180 g direct-drive sensitivity, the 4 Ah mass proxy raises the
ideal T/W-at-200 screen from 1.047 to about 1.09 while retaining the same
10.8 kW motor power cap; its 330 A hardware soft-limit case is 82.5 C and its
ideal 650 km/h energy time is 67 s. This is a paper trade, not a qualified pack
recommendation.

## The 198-part CNC issue

The 198 items are **72 rotor blades + 126 stator vanes**; 90 mm is the duct
diameter, not each part's diameter. Current nominal vane envelopes are about
29×8.2 mm. The rotor chord is 16 mm: the reinforced root reaches about 3.2 mm
profile thickness and the tip about 1.9 mm. The 8 mm stator chord has roughly
1 mm section thickness. In the proposed orientation, chord and span lie in the
sheet face and its 5 mm thickness contains the section thickness, so the stock
is not inherently too thin. But the parts need 3D airfoil/twist machining from
both sides or indexed setups;
the existing NC only cuts 2.5D blank outlines and does not machine the finished
airfoils or their safe hub retention.

The 96+108 blank-grid count for the two sheets is only a rectangular-envelope
nest with 1.5 mm spacing and 1 mm edges, leaving six spare positions. It is not
a fixture/tab/toolpath result. The 300×120 mm plate also consumes the full
nominal X travel of the cited 3018 machine, leaving no allowance for fixture,
edge approach, or travel tolerance. **Do not use the existing Phase-13 NC** for
these sheets; a machine with a larger verified work envelope and new
two-sided/indexed CAM is required. If that machining burden is unacceptable,
reducing motor size alone will not reduce the 198-part count; the turbine row
architecture or rotor/stator sourcing must change.

## Recommendation

1. Keep 90 mm fans for the first motor downsizing study. The 150×150 ESC,
   140×100 flight board, two battery packs and main lifting-body bay keep the
   airframe from shrinking with EDF diameter.
2. Study a low-pole-count direct-drive motor against those fixed envelopes.
   The modeled 0.72 kg gearbox removal is attractive but remains an unsourced
   allowance and needs physical motor/shaft/rotor CAD.
3. Treat the 80 mm / 180 g / 1.8 kW-channel case as an **area/mass sensitivity,
   not a preferred build**: once its inrunner can forces a 40 mm hub, ideal T/W
   at 200 km/h is only 1.047. Avoid 70 mm under current power/ESC targets.
4. Freeze no motor purchase until it has a 12S EDF dynamometer map, actual
   motor/can/shaft CAD, and thermal/rotor-speed evidence. Preserve the six
   motor-temperature inputs and six actuator interface requirements already
   filed in drone-arm issues #18 and #19.

## Variable bypass, auxiliary inlets, and the revised 180 km/h gate

The low-speed requirement is now **TWR≥1.0 up to 180 km/h** (previously
200 km/h). Run `../optimization/phase14_multivariable_trade.py` to regenerate
`../results/phase14_multivariable_trade.csv` (1,080 cases) and
`../results/phase14_multivariable_summary.json`.

The sweep folds in fan diameter, hub/motor package, motor power/mass/price,
battery capacity, a variable-bypass low-speed multiplier, an auxiliary-inlet
sensitivity, fan figure of merit, sea-level and 3 km atmosphere, tip Mach,
eRPM, CdA, and the INR cost gates. It still excludes measured fan/motor/ESC
maps, inlet recovery, spillage drag, nozzle matching, Reynolds drag rise,
structure, and control.

**Variable bypass model.** The Phase-2 reduced-order sweep found bypass
fraction β=0.5 best at 100 km/h (0.66 kW vs 0.99 kW for equal thrust) and
β=0 at ≥200 km/h. At equal power that is about 1.30× thrust. Phase 14 models
**1.30× up to 100 km/h tapering to 1.00× at 200 km/h**, so at 180 km/h the
bypass gain alone is only about **1.06×**.

**Auxiliary-inlet model.** An explicit, unverified sensitivity of 0%, 10%, or
20% additional low-speed thrust, tapering to zero at 200 km/h. No credit is
taken above 200 km/h, so no high-speed CdA penalty is applied. The two gains
are added as excesses rather than compounded.

**Finding 1 — bypass alone is not enough.** At a realistic fan figure of merit
of 0.72 and flush inlets, every swept candidate **fails** TWR≥1 at 180 km/h:
TWR_180 ranges 0.88–0.97 at sea level. Low-speed margin depends on the inlet,
not the bypass schedule alone.

**Finding 2 — auxiliary inlets are the enabling lever.** With a 20% modeled
aux-inlet gain and FOM 0.72, TWR at 180 km/h at sea level rises to 1.04–1.19,
and the 90 mm options also clear 1.0 at 3 km. A 10% gain is marginal (about
1.03 sea level for the 90 mm class).

**Finding 3 — smaller EDFs do raise modeled top speed (your intuition holds).**
Scaling CdA by projected area at constant reference Cd, an 80 mm fan reaches a
higher power-limited speed than a 90 mm fan at a similar power cap, because the
fixed board/battery packaging means the non-fan area is a large fraction of the
silhouette.

| Candidate (FOM 0.72, 20% aux, reserve CdA) | Mass | TWR_180 sea level | TWR_180 3 km | Modeled max speed | Cost |
|---|---:|---:|---:|---:|---|
| 90 mm, FA4119, 5 Ah | 8.199 kg | 1.125 | 1.046 | 724 km/h | Motor ₹4,500 — **over cap** |
| 90 mm, 220 g direct, 5 Ah | 7.267 kg | 1.142 | 1.061 | 702 km/h | Unpriced |
| 90 mm, 180 g direct, 4 Ah | 6.686 kg | 1.160 | 1.080 | 678 km/h | Unpriced |
| 80 mm, 220 g direct, 4 Ah | 6.910 kg | 1.105 | 1.024 | 751 km/h | Unpriced |
| 80 mm, 180 g direct, 4 Ah | 6.614 kg | 1.088 | 1.009 | 725 km/h | Unpriced |
| 80 mm, 150 g direct, 4 Ah | 6.385 kg | 1.047 | 0.973 | 697 km/h | Unpriced |

The 80 mm / 180 g direct-drive / 4 Ah row is the compact-mass option: about
6.61 kg, roughly 725 km/h modeled, and 10.8 kW bus. Its 3 km TWR_180 is only
1.009, so it is thin at altitude. The 90 mm / 180 g direct / 4 Ah row keeps
more low-speed margin (1.080 at 3 km) at 678 km/h.

**Finding 4 — minimum power.** With 20% aux, the least power that still meets
the 180 km/h gate and 650 km/h is about **1.6 kW per channel** (9.6 kW bus) on
the 80 mm / 150 g package, and it is marginal (TWR_180 = 1.047 sea level, 0.973
at 3 km). A **1.8–2.0 kW per channel** class gives real margin. The 2.2 kW
FA4119 remains the most robust but is over the motor price cap.

**Finding 5 — cost gates.** The confirmed FA4119 price is **₹4,500 each**,
which **fails** the ₹4,000 unit cap; six motors would be ₹27,000. The Turnigy
pair lists at **₹5,400 each / ₹10,800 pair**, which is **under** the ₹12,000
pair cap, but the listing is sold out and excludes shipping and tax. Every
smaller motor class is **unpriced**, so none is a cost pass yet. A dated quote
for a sub-₹4,000, 1.8–2.0 kW/channel, 12S EDF motor is now a hard gate.

**Recommended next step.** Prototype the **80 mm and 90 mm direct-drive,
1.8–2.0 kW/channel, 4–5 Ah** options with an instrumented inlet and a
variable-area exit, and measure: (1) static and 90/180 km/h thrust with the
auxiliary inlet open vs closed and with the bypass schedule swept, and
(2) 650/700 km/h drag power with the inlets closed. Those two measurements
decide whether the low-speed gate is real and whether the smaller fan actually
buys the modeled top-speed margin. Do not buy motors until that motor also has
a sub-₹4,000 quote and a 12S EDF dynamometer map.
