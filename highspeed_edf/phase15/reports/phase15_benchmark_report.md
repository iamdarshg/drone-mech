> **PARTLY SUPERSEDED.** This report's §5 "gearbox is mandatory" conclusion
> applies only to a **stock 350 Kv FA4119**. The current design decision is
> **direct drive with a rewound 4-pole inrunner** (see
> `../../design/PHASE15_DESIGN_SPEC.md`), which removes the gearbox. Its §1–§4
> sourcing/benchmark content remains valid. Also note the corrected frontal-area
> and power numbers in the design spec supersede the values here.

# Phase 15 — sourcing, low-cost and high-cost benchmarks

Two loops were run: a **low-time-cost** ranking over the purchasable
motor/battery list, and a **high-time-cost** strongly coupled generative design
through the aero-multiphysics workbench. Both are screening results; no native
CFD/FEA was run and no purchase was made.

## 1. Supplier crawl (amazon.in primary, robu.in backup)

Coverage: motors 71 queries / 115 search pages / ~2,113 unique ASINs reviewed;
batteries 54 queries / 279 search pages / ~836 unique ASINs; EDF units 15
queries. Dataset: `../configs/phase15_sourcing.json`.

Firm findings:

- **No amazon.in motor meets 12S + ~2 kW + ≤250 g + ≤₹4,000 at once.** Under
  ₹4,000 there is no motor above ~0.5 kW.
- **No 12S EDF unit and no 12S inrunner exists on amazon.in** at all.
- **No amazon.in 12S string under ₹12,000 reaches 4 Ah at ≥60C.** The only
  sub-₹12,000 12S strings are ~1.3–1.4 Ah Ovonic packs.

| Role | Best candidate | Spec | Price | Verdict |
|---|---|---|---|---|
| Motor (12S) | FLYCCI FA4119 350KV (robu.in) | 226 g, 2011 W, 12S, 12N14P | ₹4,499 | ₹499 over unit cap; 7 pole pairs → 287 keRPM at 80 mm direct drive |
| Motor (power/mass) | XFLY 70 mm inrunner 2680-2200 (amazon) | 170 g, 2400 W / 70 A | ₹9,541 | 6S only |
| Motor (low pole) | Spektrum 3670-1950 4-pole (amazon) | 227 g, ~1.9 kW, 4-pole | ₹13,315 | 6S only |
| Battery (spec) | OVONIC 6S 5000 120C 2-pack (amazon) | 12S 5 Ah 120C, 689 g/pack | ₹21,498 | no seller; 1.8× budget |
| Battery (in stock) | 2× Pro-Range 6S 4200 35C (robu) | 12S 4.2 Ah 35C = ~147 A | ₹11,958 | under budget but current-limited vs ~330 A |
| Battery (listed) | Turnigy Rapid 6S 5000 100C | 12S 5 Ah 100C | ₹10,800 | sold out; not on robu.in |

**Cost reality:** six FA4119 at ₹4,499 = ₹27,000, already 1.7× the whole
motor budget before the battery. A sub-₹4,000, ≥1.8 kW, ≤250 g, 12S EDF motor
does not presently exist on either site.

## 2. Low-time-cost benchmark

`../optimization/phase15_low_cost_benchmark.py` ranked 132 motor×battery combos
for cruise flight time at 650 km/h, max-endurance flight time, TWR, and top
speed, subject to the 12S, TWR-to-180 km/h, ≥650 km/h, eRPM, stock, and cost
gates.

- **0 of 132 combos pass every gate.** The union of failures is always some of:
  over-cost motor, unavailable or current-limited battery, TWR<1 at 180 km/h
  without auxiliary inlets, or 7-pole-pair eRPM overrun.
- **Cruise flight time at 650 km/h is only ~2.2 min** for the highest-energy
  available pack (energy-limited at ~8.2 kW cruise).
- **Max-endurance flight time is ~32–43 min, but at only 220–240 km/h.** At
  650 km/h the aircraft is inherently a very short-duration sprint.
- Two hard physics blockers: a 7-pole-pair motor at 80 mm direct drive needs
  ~41 krpm × 7 = **287 keRPM**, over the ESC's 200 keRPM target; and the ~330 A
  soft current needs ~66C at 5 Ah, which the affordable packs do not provide.

## 3. High-time-cost generative benchmark

`../optimization/phase15_high_cost_generative.py` drives the workbench
`aeroworkbench_vehicle_systems.coupled_optimizer` (adapter `ideal_edf`, body
role `lifting_body`, 16×50 bar + sheet stock profiles) around the fixed motor
(44.4 V, 65 A limit, 36 krpm, 0.92) and battery (44.4 V, 330 A), 1 kg payload,
720 km/h design / 650 km/h required, TWR≥1.0.

Result (`../results/phase15_high_cost_report.json`): **16,168 evaluations, no
feasible design promoted.** Blocking gates were `frontal_area`,
`low_speed_thrust_to_weight`, `target_speed`, and `manufacturing`. Fallback
evaluation of the seed design: frontal area 0.01255 m², TWR 0.334, tip Mach
0.445, target-speed thrust margin −86.9 N.

Two decisive findings:

1. **The 75 cm² frontal-area requirement is arithmetically incompatible with a
   battery-dominated body.** The workbench computes frontal area as body
   cross-section plus fan disk. The two 136×44×64 packs need ≈56 cm² of body
   cross-section, and an 80 mm fan adds ≈50 cm², giving ≈106 cm² — well over
   75 cm². This confirms the correction: the boards set internal volume, the
   batteries set frontal area, so the requirement itself must move to roughly
   100–110 cm² or the pack arrangement must change.
2. **The low-speed TWR gate is entirely dependent on unvalidated gains.** The
   conservative workbench low-speed model returns TWR 0.334 without
   variable-bypass or auxiliary-inlet credit, versus ≈1.1 in the Phase-14 model
   that includes the 1.30× bypass and 20% auxiliary-inlet assumptions. Until
   those are measured on a rig, the coupled design cannot be called feasible.

### Fabrication package (seed design, screening)

| Item | Estimate |
|---|---|
| Printed PLA core volume | ≈0.68 L |
| Outer shell area | ≈0.57 m² |
| Carbon-fibre fabric to buy (200 gsm, 1.25× cut allowance) | ≈0.71 m² |
| Glass fabric to buy (100 gsm) | ≈0.71 m² |
| Carbon-fibre laminate mass | ≈0.21 kg |
| Glass laminate mass | ≈0.10 kg |

Parts to print: lifting-body/fuselage shell master, 2× EDF duct casings, 4×
inlet transitions, auxiliary-inlet door frames, six effector brackets and servo
mounts, ESC/flight-board tray, battery cradles, landing-gear mounts.

Flight regime: 650 km/h cruise, 720 km/h design point, 3 km altitude, control
authority required to 180 km/h; endurance ≈2 min at cruise or ≈35 min at
220–240 km/h.

## 3b. Corrected frontal-area model (review corrections applied)

Three corrections were applied in
`../optimization/phase15_frontal_area_model.py`, which rasterizes the front
silhouette on a 1 mm grid so unions and overlaps are exact:

1. **The two ducts are side by side, not coaxial.** Both duct envelopes appear
   in the front view, so the body must be ~2× duct width across.
2. **The duct bore is a passthrough, not solid frontal area.** Only the duct
   wall (inside the body outline), the hub seen through a front inlet, and the
   surrounding structure count.
3. **Wings, tail, thin fins, landing gear and control surfaces contribute.**

Results (40 mm hub, side-by-side ducts, area in cm² and CdA at the same
reference Cd as the old 0.0009 m² baseline):

| Duct OD | Inlet | With wings | Frontal solid | Implied CdA |
|---:|---|---|---:|---:|
| 80 mm | front (passthrough) | yes | 242.2 cm² | 0.000654 m² |
| 80 mm | side | yes | 296.2 cm² | 0.000800 m² |
| 90 mm | front | yes | 257.4 cm² | 0.000695 m² |
| 90 mm | side | yes | 333.3 cm² | 0.000900 m² (reference) |
| 80 mm | front | no | 130.7 cm² | 0.000353 m² |
| 80 mm | side | no | 196.4 cm² | 0.000530 m² |

Two important conclusions:

- **The fan does not dominate the frontal area.** For an 80 mm side-inlet
  layout the entire front silhouette is body/battery/wing structure
  (~196 cm² without wings); the buried ducts add nothing. For a front-inlet
  layout the fan only acts through the bore as a subtracted hole (~−100 cm²
  for two 80 mm ducts) and the two hubs (~+25 cm²). Frontal area is set by the
  battery/body block and the wing, not the fan.
- **The corrected frontal areas are 3–4× the old 59–73 cm² estimate.** At a
  constant reference Cd that implies CdA is far above 0.0009 m². The 0.0009 m²
  CdA target is therefore optimistic for a side-by-side-duct lifting body with
  a 0.52 m wing; it needs a fresh VLM/CFD-derived polar rather than an assumed
  number. The old 75 cm² gate is not attainable with this configuration.

## 5. Locked configuration (robu.in only, drone-arm-compliant)

`../optimization/phase15_robu_final_config.py` screened 192 configs and applied
the drone-arm Rev-B / FA4119 contract as hard gates: 6 sensorless-FOC channels,
12S (50.4 V), ≤60 A continuous phase current per channel, motor rpm soft
12,500 / hard 13,500 (stock) or 17,000/18,000 (provisional), electrical rpm
≤200,000, battery current soft 55 A / hard 65 A / provisional 75 A per motor.

Result: **6 configs pass every gate except the ₹4,000 motor price cap; 0 pass
all gates.**

### The locked build

| Item | Selection | Note |
|---|---|---|
| Motor | 6× **FLYCCI FA4119 350KV**, stock winding | ₹4,499 each = ₹26,994; **₹499/unit over the ₹4,000 cap** |
| Speed reduction | **Geared 2.35 / 2.65 / 2.95 : 1** | mandatory — see below |
| Rotor rows | 3 per duct, 90 mm OD (80 mm with a taller 3.3–3.6 ratio) | |
| Battery | 2× **Bonka 6S 1600 mAh 150C** = **₹10,638** | 240 A capable vs ~212 A needed; **within the ₹12,000 cap** |
| ESC | drone-arm Rev-B, 6 channels | 12S, within every limit |
| Rewind | **not required** | stock winding already complies |

Verified margins (90 mm fan, 2.95 ratio, Bonka 1600, front-inlet CdA 0.000654):
motor **12,325 rpm ≤ 12,500 soft**; **86,278 eRPM ≤ 200,000**; battery
**~35 A per motor ≤ 55 A soft**; phase current within 60 A; **720 km/h passed**
(modeled 751 km/h power ceiling); **TWR at 180 km/h = 1.083 ≥ 1.0**; static TWR
≈ 1.4–2.0.

### Three decisive compliance findings

1. **The gearbox is mandatory.** At 12S the fan rows need ~36–41 krpm, but the
   drone-arm RPM limit caps the motor at 13.5 krpm (stock) or 18 krpm
   (provisional). Direct drive cannot comply, so the 2.35–2.95:1 reduction stays.
2. **The 550 Kv rewind is unnecessary and not cost-neutral.** A rewind raises
   the motor price by roughly ₹1,750/unit (~₹10,500 for six) and changes Kv
   only — not pole count — so it relaxes no eRPM or mechanical-speed limit. The
   stock 350 Kv winding already complies, so per your "same total cost" rule the
   build uses stock motors.
3. **Only the motor price fails.** The sole in-stock robu 12S-capable motor is
   ₹4,499, i.e. **₹2,994 over the six-motor ₹24,000 ceiling**. The battery is
   inside its ceiling. There is no 12S motor ≤₹4,000 in stock at robu.in.

### Honest limit

At 720 km/h with the ₹12,000-capped 1.6 Ah pack the sprint lasts only ~23 s
(energy-limited); the 4.2 Ah Pro-Range pack lasts longer but its 35C rating
supplies only ~147 A, below the ~212 A demand. Meeting both 720 km/h and a
useful endurance needs either a bigger battery budget or a lower cruise speed.

## 6. Sub-₹4,000 motor via rewind, and max range

### Motor: rewind a cheap stator, don't buy a "12S" motor
robu's cheapest stock 12S motor is ₹4,499. But the 12S label is irrelevant —
any motor can be rewound for 12S with Class-H wire for a few hundred rupees.
Screening robu's inventory for cheap stators big enough for ~1.6 kW per motor
gives:

| Motor | Price | Rewind | Total/unit | 6 motors | Note |
|---|---:|---:|---:|---:|---|
| **Tarot 3115/900KV TL1616** | ₹3,109 | ₹500 | **₹3,609** | ₹21,654 | in stock; 31×15 stator, QPT-3115 class (~1.5–1.7 kW) |
| **Rocket 3670 4-pole 1550KV** | ₹3,409 | ₹500 | **₹3,909** | ₹23,454 | in stock; larger 36×70 can, ~1.6 kW, only 2 pole pairs |

Both clear the **₹4,000 motor ceiling and the ₹24,000 six-motor total**. The
Rocket 3670 is the safer pick: more stator volume and 2 pole pairs (so eRPM is
trivial ~25,000), and it still leaves ₹546 of headroom. Rewind to roughly 280–450
Kv for 12S; the ESC rpm governor then holds 12,500 rpm and the 2.9:1 gearbox
produces the fan speed.

### Range: max range and the speed it occurs at
`../optimization/phase15_range_and_cost.py` computes range = speed × energy /
electrical power, using parasite + induced drag and the ideal-disk model
(CdA 0.000654, 80 mm fan).

| Battery (12S) | Price | Energy | Current cap | Max range | At speed |
|---|---:|---:|---:|---:|---:|
| Bonka 1600 mAh 150C LiPo | ₹10,638 | 60 Wh | 240 A | **38.8 km** | 290 km/h |
| Pro-Range 4200 mAh 35C LiPo | ₹11,958 | 159 Wh | 147 A | **98.5 km** | 295 km/h |
| **Li-ion Pro-Range P50B 5000 mAh 12C** | **₹11,658** | **189 Wh** | 60 A | **116.1 km** | **295 km/h** |
| Li-ion NMC 10000 mAh 3C (over budget) | ₹12,278 | 377 Wh | 30 A | 218.8 km | 305 km/h |
| Li-ion Samsung 10000 mAh 9C (over budget) | ₹16,478 | 377 Wh | 90 A | 218.8 km | 305 km/h |

**Under the ₹12,000 battery ceiling the best range is ≈116 km at ≈295 km/h**,
using the Li-ion 5000 mAh 12C pack. Range grows with usable energy, so the
sweet spot stays near 295–305 km/h regardless of pack.

### The unavoidable trade
A single 12S pack under ₹12,000 cannot do both. The 150C LiPo reaches 720 km/h
but only ~39 km of range; the Li-ion pack gives 116 km but its 60 A cap limits
top speed to ~295 km/h. Pick one, or split the budget across two packs.

## 4. What this means

- The concept is **not closeable with currently purchasable, in-budget parts.**
  The binding constraints are motor price/power at 12S, battery C-rate, the
  7-pole-pair eRPM at high fan speed, and the frontal-area requirement.
- Recommended path: (a) revise the frontal-area requirement to ~100–110 cm² or
  re-arrange the packs; (b) source a sub-₹4,000, ≤4-pole-pair, ≥1.8 kW 12S
  motor from a specialist importer rather than amazon.in; (c) accept a ≥60C
  ~4–5 Ah pack above ₹12,000 or under-run the current limit; (d) build an
  instrumented inlet/exit rig to measure the variable-bypass and auxiliary-inlet
  gains that the whole low-speed case rests on.
