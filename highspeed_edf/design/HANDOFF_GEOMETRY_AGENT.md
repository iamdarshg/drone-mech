# HANDOFF — Geometry design brief

**To:** geometry / CAD agent.
**Goal:** produce the parametric CAD for the high-speed twin-EDF airframe to the
values below. Everything is a **range with a nominal**; model the nominal, keep
the parameters driven so a band can be swept. Do not invent numbers — every
figure here is either sourced hardware or an analyst screening target, and the
sources are named.

---

## 0. What you are building

A **twin 80 mm ducted-fan, tailless lifting-body aircraft** with a battery body,
a stubby low-aspect wing, two canted tail fins, four jet-vectoring vanes and two
elevons. Carbon-fibre-wrapped PLA shells, 6061-T6 aluminium rotors/stators/hubs.
**Direct drive** (no gearbox): six rewound 4-pole inrunners, one per rotor row.

---

## 1. Read these first (authoritative)

| Order | File | What it gives you |
|---|---|---|
| 1 | `highspeed_edf/design/PHASE15_DESIGN_SPEC.md` | **Master geometry/performance spec.** §3 inlet, §4 duct/fan, §5 blades, §6 nozzle, §8 airframe, §9 wing, §10 control, §11 motor, §14 thermal, §15 harness, §16 mass/CG, §18 manufacturing, §1b stretch targets |
| 2 | `highspeed_edf/design/PHASE15_CONTROL_SURFACES.md` | §1 effector architecture, §2 authority, §3 elevons, §4 vanes, §5/5c fins, §7 allocation, §9c servo count, §9b balancing jig |
| 3 | `highspeed_edf/design/DESIGN_DECISIONS_FOR_VERDICT.md` | The frozen choices (D1–D7) and the 2 open items (F-05 7th channel, F-10 rudder failure) |
| 4 | `highspeed_edf/phase15/results/phase15_motor_and_rewind_v2.md` | The **selected motor** and rewind spec |
| 5 | `highspeed_edf/phase15/configs/phase15_sourcing.json` | Live parts dataset (motors, batteries, prices, stock) |
| 6 | `highspeed_edf/OBSOLETE.md` | **Ignore anything listed here.** It is superseded (90 mm geared FA4119, 18/11.5/10.5 kg, 75 cm² gate, CdA 0.0009). |

**Reference CAD to reuse:** `highspeed_edf/deliverables/phase13/step/*.step` and
`highspeed_edf/deliverables/phase10/gcode/*` exist but are for the **superseded
90 mm** layout — use them only for construction technique, never for dimensions.

---

## 2. Coordinate system and datum

- **X = lateral, Y = vertical, Z = flight axis**, +Z **aft**.
- **Origin = the fan disk plane** (front rotor face), on the duct-pair centreline.
- Units **mm**. Model in the nominal; all values below are `min – nominal – max`.

---

## 3. Fixed / sourced components (drive the geometry)

| Component | Identity | Dimensions | Source |
|---|---|---|---|
| Motor ×6 | Surpass Rocket **3670 4-pole 1550 KV** | **Ø~42 × 72 mm can**, 5 mm shaft, ~270–276 g | `phase15_motor_and_rewind_v2.md`; robu.in |
| Battery (now) | 2× Bonka 6S 1600 mAh 150C | **185 × 65 × 55 mm** each | `phase15_sourcing.json` |
| Battery (future) | Li-ion 12S or hybrid | bay reserved **200 × 135 × 75 mm** | design spec §20b/§21 |
| ESC board | drone-arm Rev-B ESC | **150 × 150 × 1.6 mm** + spreader | design spec §12 |
| Flight board | drone-arm Rev-B main | **140 × 100 × 1.6 mm** | design spec §12 |
| Servos ×6–7 | digital metal-gear micro | **~23 × 12 × 29 mm** typ. | control §6 |
| Aluminium stock | 6061-T6 | **300×50×16 bar**; **250×120×5** + **300×120×5** sheets | design spec §18 |

---

## 4. Part-by-part geometry

### 4.1 Duct modules (×2, side-by-side)

| Dimension | min – nominal – max | Notes |
|---|---|---|
| Outer diameter | 72 – **80** – 90 mm | |
| Bore (inner) | 78 mm (OD − 2) | 2 mm wall nominal |
| Wall thickness | 1.5 – 2 – 3 mm | composite over PLA core |
| Module length | 95 – **110** – 130 mm | Z 0 … 110 |
| **Layout** | **two ducts side-by-side, centre-to-centre 84 – 88 – 96 mm** | centres at **X = ±43 mm** nominal. **NOT coaxial.** |
| Exit internal area | 0.9 – 1.0 – 1.15 × annulus | convergent lip |
| Duct centreline | parallel, ±0 – 0.2 – 0.5° | jig-built |

### 4.2 Rotor/stator stack (×2 ducts, 3 rows each)

| Element | Nominal | Notes |
|---|---|---|
| Hub diameter | **40 mm** (34 – 40 – 46) | must clear the Ø42 motor can |
| Rotor radial span | 20 mm (17 – 24) | (OD/2 − hub/2) |
| Rotor chord | **16 mm** (13 – 16 – 19) | |
| Stator chord | **8 mm** (6 – 8 – 10) | |
| Rotor blade counts | **13 / 12 / 11** (rows R1/R2/R3) | |
| Stator vane counts | **23 / 21 / 19** | interleaved |
| **Rotor Z (R1/R2/R3)** | **12 / 48 / 84 mm** | from the fan plane |
| **Stator Z** | **30 / 66 / 102 mm** | between rotors |
| Rotor root t/c | 0.20 (0.16 – 0.24) | thickened root |
| Rotor tip t/c | 0.12 (0.08 – 0.16) | |
| Root fillet | 1 – 2 – 3 mm | blended into hub |
| Tip clearance | 0.4 – 0.7 – 1.2 mm | to the bore |
| Rotor/stator axial gap | 1.5 – 2.5 – 4 mm | |
| Blade stagger | root −20° → tip −40° | twist loft |
| Design rotor RPM | 36,000 – 41,000 – 47,000 | R3 ≈ 41,070 at 80 mm |

**Construction:** blades and vanes are cut from the 5 mm sheets with **chord and
span in the plane of the sheet**; hub is turned from the 300×50×16 bar. Blank
envelope 29 × 8.2 mm, 1.5 mm spacing, 1 mm edge margin.

### 4.3 Fuselage / battery body

| Dimension | min – nominal – max | Notes |
|---|---|---|
| Body cross-section (outline) | 175×72 – **186×78** – 205×90 mm | must contain the duct pair **and** the packs |
| Outline area | 126 – 145 – 185 cm² | |
| Body length | 480 – **560** – 640 mm | Z −280 … +280 |
| Superellipse exponent | 2.2 – 2.6 – 3.2 | section shape |
| Nose fineness (L/half-width) | 2.5 – 3.5 – 5 | |
| Rear taper half-angle | 5 – 9 – 14° | |
| Shell thickness | 0.8 – 1.2 – 2.0 mm | PLA core + CF wrap |

### 4.4 Wing / lifting body

| Dimension | min – nominal – max | Notes |
|---|---|---|
| Planform area | 0.13 – **0.19** – 0.30 m² | |
| Span | 450 – **520** – 620 mm | |
| Aspect ratio | 1.30 – **1.42** – 1.80 | **jointly constrained:** AR = span²/area |
| Sweep (LE) | 25 – 40 – 55° | |
| Thickness ratio | 0.08 – 0.10 – 0.13 | → **22–30–36 mm** on the ~365 mm mean chord |
| Dihedral | −2 – 0 – 4° | |
| Twist root→tip | −2 – 0 – +2° | |
| Mean chord | 0.19/0.52 ≈ **365 mm** | |

### 4.5 Fins (×2, canted) — **not winglets, not tip-mounted**

| Dimension | min – nominal – max | Notes |
|---|---|---|
| Height | 50 – **70** – 100 mm | |
| Chord | 60 – **90** – 130 mm | |
| Cant | 15 – **30** – 45° outward | tunable roll coupling |
| Thickness ratio | 0.06 – 0.10 – 0.14 | |
| Position | on the aft body, **Z ≈ +300 … +400 mm**, X = ±(body half-width) | gives the yaw arm |

### 4.6 Effectors

| Element | Qty | Nominal size | Position |
|---|---|---|---|
| Elevons | 2 | span **150 mm** (100–200), chord **40 mm** (25–60), ±25° | wing trailing edge, **Z ≈ +150 mm** |
| Vector vanes | **4** (2/duct) | **30 × 40 mm** (25×30 → 40×55), ring radius **44 mm** (38–50), ±22° | duct exit, **Z ≈ +240 … +280 mm** |
| Rudder | **1** | on one fin, ~30% of fin chord, ±25° | fin TE |

Hinge line 25–30% chord; LE gap seal 0.2–0.5–1.0 mm; mass-balance the elevons and
vanes (control doc §9b).

### 4.7 Internal layout (positions & reserved volumes)

| Item | Envelope (X×Y×Z) | Centre | Notes |
|---|---|---|---|
| Duct A / B | Ø80×110 | X ∓43, Y 0, Z 0…110 | |
| Motor bays ×6 | Ø42×72 | on each rotor axis | 3670 can |
| **Battery bay (reserved)** | **200 × 135 × 75** | X 0, Y 0, Z −300…−100 | accepts future Li-ion/hybrid |
| ESC board | 150×150×~20 | Y ≈ +52, Z ≈ +220 | edge-on in a side cooling bay |
| Flight board | 140×100×~20 | Y ≈ +52, Z ≈ +345 | edge-on |
| Heat spreaders | 150×150×1 / 100×80×1 | at Y ≈ +54.2 | metal-to-air |
| Cooling bay | open-ended side tunnel | Z 145…395 | inlet forward, outlet aft |

---

## 5. Constraints that bind the geometry

1. **Frontal solid area target 242 – 270 – 296 cm²** (the fan bore is a
   **passthrough** — do not count it as solid). This is the D2 decision.
2. **CdA target 0.0007–0.0008 m²** (optimistic, D1) — keep the body slender.
3. **All-up mass ≤ 8.5 kg** incl. the 1 kg payload.
4. **Airframe core ≤ 45 °C**; duct + motor bay to be **metal or high-temp**
   (D6) — PLA only on the cold body.
5. **Manufacturing:** 1 bar + 2 sheets only, on a TwoTrees 3018-class CNC. The
   300 mm sheet consumes the full X travel → flag the fixture margin.
6. **Battery bay 200×135×75 reserved** even though the sprint packs are smaller
   (D5 future-proofing).

---

## 6. Tolerances (control doc §9b + spec Appendix)

Tip clearance 0.5–1.0 mm; rotor balance ≤2 mg·mm/g; shaft TIR ≤0.02 mm; duct
roundness ≤0.3 mm; inlet lip radius ≥1.5 mm; no rear-facing step >0.2 mm; duct
interior Ra ≤1.6 µm; composite ply overlap ≥10 mm; battery retention ≥6 g.

---

## 7. Deliverables

1. **Parametric CAD** (CadQuery preferred — the repo already uses it in
   `optimization/phase10_generate_deliverables.py` and `phase13/`) with the
   above as named parameters.
2. **STEP** per part + full assembly, reimport-validated.
3. **Stock nests** for the 300×50×16 bar (six hubs) and the two 5 mm sheets
   (72 rotor blanks + 126 stator vanes).
4. **Projected-frontal-silhouette** drawing proving the 242–296 cm² union with
   the fan bore shown as a hole.
5. **Mass/CG table** from the solid volumes, checked against ≤8.5 kg.
6. **Servo/horn mounts** for 6–7 effectors (F-05 pending the 7th channel).

---

## 8. What is NOT defined — you must derive it

- The **exact duct transition geometry** (inlet mouth → diffuser → fan face); the
  inlet recovery is an accepted risk set at 0.99 (D7) and must be shaped for it.
- The **inlet lip radius** and mouth area within the §3 band.
- The **wing planform shape** within span/area/AR/sweep.
- The **fin placement** on the aft body (arm vs packaging).
- The **internal mounting structure** (motor mounts, board tray, battery rails,
  landing gear) — allowances exist (spec §16) but no geometry.
- Rotor/stator **airfoil section coordinates** — loft from the NACA-like section
  in `optimization/phase10_generate_deliverables.py::foil_section`.

---

## 9. Validation checklist before you hand back

- [ ] All four `min–nom–max` bands either honoured or the deviation documented.
- [ ] Frontal silhouette union ≤296 cm² with the fan bore as a passthrough.
- [ ] Two ducts side-by-side, **not coaxial**.
- [ ] Hub clears the Ø42 motor can; rotor span matches (OD−hub)/2.
- [ ] Battery bay is 200×135×75 even with the small sprint packs fitted.
- [ ] Hot-side parts (duct, motor bay) are not PLA.
- [ ] Six hubs nest in 250 mm usable bar length; 198 parts nest in the two sheets.
- [ ] Mass/CG table sums to ≤8.5 kg and CG sits within −5…+15 mm of the fan plane.
- [ ] STEP round-trips valid; every solid has positive volume.
- [ ] Any dimension you had to guess is listed in a "derived/assumed" table with
      its basis.
