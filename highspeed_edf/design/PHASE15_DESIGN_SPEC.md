# High-speed EDF aircraft — detailed design specification (Phase 15)

**Purpose.** A single hand-written, build-ready brief for the airframe and EDF
geometry team. It says **what** each item is, **why** it matters, **how** to
achieve it, **where** it sits, and the **acceptable range** for every value.
Nothing is a rigid set-point — each number is a band with a nominal and a
preferred direction. Where two bands conflict, the one with the higher
confidence (sourced/hardware) wins; everything else is a screening target.

**How to read a range.** `min – nominal – max`. `Want` is the direction that
buys margin. `Basis` is the source class: **[H]** hard hardware limit,
**[S]** sourced/manufactured fact, **[M]** measured (once we have it), **[A]**
analyst screening (expect movement).

Coordinate datum (matches Phase-12/13 CAD): **X lateral, Y vertical, Z flight
axis**, origin at the fan disk plane, +Z aft. Units mm unless stated.

---

## 1. Executive summary — the six things that decide this aircraft

1. **Inlet total-pressure recovery dominates everything.** At M≈0.6 the fan adds
   only ~1–3 % of the freestream total pressure; a 2 % inlet loss is the same
   order as the useful rise, so the required power and range swing ~3×.
   **Range to hit: 0.985 – 0.99 – 0.995+, want ↑.** Everything else is secondary.
2. **DECIDED — no gearbox.** Direct drive with a tuned-Kv rewind. A gearbox at
   500 km/h is an unmonitored single-point failure we will not carry (`DECISION`
   in §11b). This removes ~5 % loss and ~0.7 kg but **forces 2 pole pairs** — so
   the motor/rotor, bearings, containment and rewind become the critical path.
3. **Pole count must stay ≤4 pole pairs** for eRPM head-room at high fan rpm;
   **2 pole pairs is actually good** (same electrical frequency as a 7-pole
   geared unit, so no iron-loss penalty).
4. **Range and top speed cannot share one ₹12,000 pack.** A 150 C 1.6 Ah pack
   gives 720 km/h for ~3–11 km; a Li-ion pack gives ≥116 km at ~295 km/h.
   Reserve the bay for both.
5. **The frontal-area gate moved.** A battery-dominated body with side-by-side
   ducts plus wings is ~240–260 cm², not 75 cm². Re-derive CdA, don't inherit it.
6. **The sprint power is 4–8 kW at 720 km/h** (floor 2.7 kW, poor-inlet 10.5 kW).
   Size the battery, ESC and motor to that band, not to a point.

---

## 1b. STRETCH TARGETS — barely reachable, deliberately aggressive

The bands in §2–§23 are **acceptable**. The values below are the **stretch**
targets: they are near the edge of what this architecture can physically do, and
each one should be treated as "prove it or lose it". If a stretch number is met,
say so with evidence; if not, fall back to the acceptable band without shame.

| Parameter | Acceptable band | **Stretch target** | Why it is barely reachable | What it unlocks |
|---|---|---|---|---|
| Design speed (3 km) | 700–720–750 | **≥ 780 km/h** | Needs CdA at the very bottom of the band *and* recovery ≥0.99 simultaneously | Headline speed |
| Minimum cruise | 620–650–700 | **≥ 720 km/h sustained** | Requires the good inlet *and* a hot battery | Margin on the requirement |
| TWR 0–180 km/h, SL | 1.00–1.10–1.30 | **≥ 1.45** | Needs the full aux-inlet + VBR gain, not one of them | Vigorous low-speed control |
| Static TWR | 1.3–1.6–2.1 | **≥ 2.4** | Duct lip augmentation + everything open | Short-field / vertical-ish launch |
| All-up mass | 4.3–6.72–8.5 kg | **≤ 5.5 kg** incl. 1 kg payload | Forces a metal hot-side duct (D6) *and* minimal structure | TWR and range both improve |
| Frontal solid area | 242–270–296 cm² | **≤ 200 cm²** | Requires slimmer ducts or a tighter battery stack | CdA headroom |
| CdA at 720 | 0.0008–0.0030 m² | **≤ 0.0005 m²** | At the edge of a missile-class body; unproven | 780 km/h and range |
| Inlet total-pressure recovery | 0.985–0.995 | **≥ 0.997** | Near-ideal duct; every fitting and lip must be perfect | Cruise power ≈ 3.5 kW |
| Nozzle recovery | 0.985–0.995 | **≥ 0.997** | Matched expansion, no steps | Thrust closure |
| Fan installed FOM | 0.72–0.82 | **≥ 0.88** | State-of-the-art small-fan efficiency, not off-the-shelf | Power and thrust |
| Fan diameter | 72–80–90 mm | **90 mm at full annulus** | Re-opens the frontal-area tension | Thrust per power |
| Hub diameter | 34–40–46 mm | **≤ 34 mm** | Needs a very compact 2-pole can | Maximum annulus |
| Rotor tip Mach | 0.42–0.50–0.60 | **≤ 0.45 at 47 krpm** | Every extra knot of tip speed costs efficiency | Off-design efficiency |
| Rotor centrifugal FOS (1.25×) | 3.0–4.5–6.0 | **≥ 5.0 at 1.25× max rpm** | Needs root thickening and near-perfect material | Safe 47 krpm |
| eRPM margin | 82 k of 200 k | **≥ 3× margin (≤ 67 k)** | Only true with 2 pole pairs at ≤40 krpm | FOC headroom |
| Motor continuous input | 1.5–2.2 kW | **≥ 2.4 kW in the same 250 g can** | Thermal-density limit of a small inrunner | 780 km/h |
| Motor unit price | ≤ ₹4,000 | **≤ ₹3,200 incl. rewind share** | Needs a cheap donor *and* cheap wire | Motor budget |
| Battery pair price | ≤ ₹12,000 | **≤ ₹9,000 for 12S ≥100 C** | Below today's best in-stock price | Wallet |
| Battery C for 720 | 75–100–150 C | **≤ 90 C at 5 Ah** | Needs a pack that is both high-C and high-energy | One pack for both missions |
| Sprint range at 720 | 4.1–9.1–16.7 km | **≥ 25 km** | Needs better Wh/kg at ≥100 C | Sprint *and* dash |
| Max range | 116–150–219 km | **≥ 275 km** | Needs ~1.2 kWh usable under 8.5 kg | Real cruise capability |
| Airframe core temp | ≤ 45 °C | **≤ 35 °C** | Needs generous bleed cooling | PLA margin |
| ESC phase current | ≤ 60 A/ch | **≥ 75 A/ch continuous** | Would need a re-spun power stage | Burst capability |
| Manufacturing parts | 198 | **≤ 120 parts** | Fewer blades/vanes for the same duty | Build time and cost |

**Stretch-target rules.** (1) A stretch number is only claimed with a measurement,
never an estimate. (2) Stretch targets may not be used to relax any gate. (3) If a
stretch and an acceptable band conflict, the acceptable band wins for hardware
sizing until the stretch is proven.

---

## 2. Mission and performance envelope

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Design speed at 3 km | 700 – 720 – 750 km/h | ↑ margin | sets drive power | meanline + installed drag | whole aircraft |
| Minimum cruise | 620 – 650 – 700 km/h | hold | requirement floor | power margin ≥15 % | whole aircraft |
| TWR at 0–180 km/h, SL | 1.00 – 1.10 – 1.30 | ↑ | controllability | aux inlet + high bypass low speed | duct/inlet |
| Static TWR (sea level) | 1.3 – 1.6 – 2.1 | ↑ | takeoff/climb | duct lip + VBR + aux | duct/inlet |
| Payload | 0.8 – 1.0 – 1.2 kg | hold | user requirement | mass budget | CG bay |
| All-up mass | 4.5 – 6.7 – 8.5 kg | ↓ | TWR + induced drag | derived in §16 (rows + 15 % reserve); the 8.5 kg figure is the hard ceiling | whole aircraft |
| Sprint range at 720 | 4.1 – 9.1 – 16.7 km (matches the §3 power band) | ↑ | inlet quality | recovery + pack | inlet + pack |
| Max range | 116 – 150 – 219 km | ↑ | pack energy | Li-ion pack | bay |
| Max-range speed | 285 – 295 – 315 km/h | hold | parasite×induced balance | pack current cap | — |
| Control authority | strong 0–500, medium 500–700 km/h | hold | requirement | 2 elevons + 4 vanes + 1 rudder | tail |
| Cost — motors | ≤ ₹3,100 – 3,409 – 4,600 /unit | ↓ | hard cap raised to ₹4,600; selected Rocket 3670 4-pole is ₹3,409 in stock | rewind cheap stator | robu.in |
| Cost — battery | ₹8,500 – 10,600 – 12,000 /pair | ↓ | hard cap | robu 12S options | bay |

---

## 3. Inlet system — the #1 driver

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| **Total-pressure recovery at 720** | **0.985 – 0.990 – 0.995+** | ↑↑ | every −0.01 ≈ +1.5–2 kW | long gentle S-duct, no sharp lips, ≤7° diffusion | inlet → fan face |
| Recovery at 0–180 km/h | 0.95 – 0.97 – 0.99 | ↑ | low-speed thrust | area plenitude, no separation | inlet mouth |
| Capture-area fraction | 0.80 – 0.85 – 0.95 | ↑ | mass flow sets jet velocity | size mouth ≥ annulus | inlet mouth |
| Inlet mouth area | 90 – 110 – 140 cm² total | hold | capture vs spillage | two slots or a forward scoop | nose/duct flank |
| Inlet lip radius | 1.5 – 2.5 – 4 mm | ↑ low speed | lip thrust at static | rounded LE, glass-smooth | mouth edge |
| Inlet length (mouth→fan) | 80 – 110 – 160 mm | balance | diffusion vs loss | gradual area change | forward of fan |
| Diffusion half-angle | 3 – 5 – 7° | ↓ | separation margin | constant-pressure gradient | inlet walls |
| Surface finish in duct | Ra 0.8 – 1.6 – 3.2 µm | ↓ loss | skin friction | sand + seal + paint | duct interior |
| Spillage drag at 720 | 0 – 2 – 5 % | ↓ | excess capture = drag | match capture to demand | inlet mouth |
| Auxiliary inlet area added | 0 – 30 – 60 % of mouth | ↑ at low speed | low-speed thrust | doors/ports | duct flank |
| Aux inlet open envelope | static → 180 km/h | hold | requirement | spring or servo doors | duct flank |
| Aux inlet closed leakage | 0 – 1 – 3 % | ↓ | high-speed drag | flush fairing/seal | duct flank |

### 3a. How to validate the inlet BEFORE the aircraft exists

The intake is a **component**, so it can be proven standalone. Four ways, in
order of cost:

| Method | What you get | Cost / time | When |
|---|---|---|---|
| **Empirical correlation** (S-duct recovery vs L/D, diffusion angle, bend) | ±0.01 recovery | ₹0, hours | now, for sizing |
| **Isolated-duct RANS CFD** (parametric, ~1–3 M cells, steady) | recovery + distortion map | ₹0 local, hours | now, for optimising |
| **Bench duct rig** — 3D-print the duct, blow it with a cheap EDF or blower, total-pressure rake + static taps | **real recovery vs corrected flow** | ₹5–15 k, days | before freezing geometry |
| **Full installed** | the truth | ₹₹₹ | late |

You **do not need 720 km/h** on the bench. Inlet behaviour collapses onto
*corrected flow* and *Mach*; test at whatever Mach your blower makes, then use
the CFD (anchored to the rig) to extrapolate. Design of experiments over length,
bend radius, diffusion angle, lip radius and mouth area gives a response surface
you can then trade against mass and drag. **Accepted decision (D7): design to 0.99.** The 0.97 corner
is the fallback ONLY if a rig measurement disproves 0.99 — in which case the
power/battery budget must be reworked to the 9.5–10.5 kW row.

**Why it dominates (say it plainly).** At 720 km/h the freestream *total*
pressure is ~1.28× ambient, but the fan only needs ~1–3 % of that to make
thrust. A 2 % inlet loss plus a 2 % exit loss is therefore comparable to the
useful pressure rise, so the fan must work several times harder. Cruise
electrical power across the recovery band:

| Inlet / nozzle / fan η | Electrical at 720 | Propulsive η | Sprint range (60.4 Wh usable) | Sprint time |
|---|---:|---:|---:|---:|
| 0.97 / 0.97 / 0.80 | 9.5 – 10.5 kW | 22–25 % | 4.1 – 4.6 km | 21 – 23 s |
| 0.98 / 0.98 / 0.82 | 7.5 – 8.5 kW | 28–32 % | 5.1 – 5.8 km | 26 – 29 s |
| **0.99 / 0.99 / 0.86** | **4.8 – 5.8 kW** | **42–48 %** | **7.5 – 9.1 km** | **37 – 45 s** |
| 0.995 / 0.995 / 0.90 | 3.8 – 4.5 kW | 55–60 % | 9.7 – 11.4 km | 48 – 57 s |
| 1.0 / 1.0 / 1.0 | 2.6 – 2.9 kW | 85–90 % | 15.0 – 16.7 km | 75 – 84 s |

Range is `speed × usable_energy / electrical_power` with `usable_energy = 1.6 Ah
× 44.4 V × 0.85 = 60.4 Wh`, at 720 km/h and 3 km. Power and range columns are now
derived from the same row, so they agree by construction. The earlier table in
this document quoted range values that did not match its own power column; that
was a unit error and is corrected here.

---

## 4. Duct and fan system

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Fan outer diameter | 72 – 80 – 90 mm | hold 80 | CdA saturates ≈80 mm | stock envelope, packaging | duct centreline |
| Duct bore | D − 3 – D − 2 – D − 1.5 mm | hold | tip clearance | reamed/formed | fan face |
| Hub diameter | 34 – 40 – 46 mm | ↓ | annulus area | must fit motor can | fan centreline |
| Annulus area (both ducts) | 55 – 70 – 90 cm² | ↑ | thrust per power | (D²−hub²)·π/2 | fan face |
| Duct count | 2 (1 reserved dual-path option) | hold | 6 motors, 3/duct | Rev-B channels | airframe |
| Rotor rows per duct | 2 – 3 – 4 | hold 3 | work split | equal-work staging | duct lengthwise |
| Duct module length | 95 – 110 – 130 mm | hold | packaging + losses | modular shells | Z 0…110 |
| Duct wall thickness | 1.5 – 2 – 3 mm | balance | stiffness vs area | composite over PLA core | duct skin |
| Duct layout | side-by-side | hold | **NOT coaxial** | two parallel ducts | X ±43 mm |
| Duct centreline spacing | 84 – 88 – 96 mm | ↓ | frontal area | wall + 6 mm gap | X ±43–48 |
| Duct parallelism | 0 – 0.2 – 0.5° | ↓ | flow symmetry | jig-built | — |
| Internal exit area | 0.9 – 1.0 – 1.15 × annulus | tune | nozzle matching | convergent lip | duct exit |
| Structural safety factor on case | 2.0 – 2.5 – 3.5 | ↑ | containment | hoop layup | duct skin |

---

## 5. Rotor and stator blade system

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Rotor blade count/row | 10 – 12 – 14 (existing 13/12/11) | tune | solidity vs blockage | lofted airfoil, 2 mm min thickness | each rotor station |
| Stator vane count/row | 17 – 21 – 25 (existing 23/21/19) | tune | diffusion vs loss | lofted, 1 mm section | between rotors |
| Rotor chord | 13 – 16 – 19 mm | hold | Reynolds + stock | 5 mm sheet, chord in plane | blade |
| Stator chord | 6 – 8 – 10 mm | hold | Reynolds floor | 5 mm sheet | vane |
| Rotor radial span | 17 – 20 – 24 mm | hold | (D−hub)/2 | from D and hub | blade |
| Root thickness ratio | 0.16 – 0.20 – 0.24 | ↑ | root stress | thick root loft | blade root |
| Tip thickness ratio | 0.08 – 0.12 – 0.16 | balance | drag vs flutter | thin tip | blade tip |
| Camber | 0.015 – 0.025 – 0.04 | tune | turning | circular-arc/parabolic | blade |
| Root fillet | 1 – 2 – 3 mm | ↑ | stress | blended root | hub interface |
| Tip clearance | 0.4 – 0.7 – 1.2 mm | balance | efficiency vs rub | tolerance stack | tip↔bore |
| Rotor/stator axial gap | 1.5 – 2.5 – 4 mm | ↑ | rub margin | stage spacing | between rows |
| Blade stagger (root→tip) | −20° → −40° span | tune | work/metal angle | twist loft | blade |
| Rotor speed at 720 | 33 – 41 – 47 krpm | ↓ | tip Mach + stress | direct drive Kv | each row |
| Tip Mach at 3 km | 0.42 – 0.50 – 0.70 | ↓ | flutter onset | diameter × rpm | tip |
| Centrifugal FOS at 1.25× | 3.0 – 4.5 – 6.0 | ↑ | containment | root area, material | hub/blade |
| Min stator Reynolds | 50k – 70k – 100k | ↑ | separation | chord × speed | vane |
| Blade material | 6061-T6 | hold | stock | CNC from sheet | rotor/stator |
| Hub material / blank | 6061-T6, Ø40 from 300×50 bar | hold | stock | CNC | hub |

**Blade manufacturing note (how).** All 72 rotor blades + 126 stator vanes come
from the two 5 mm sheets, chord and span in the plane of the sheet, section
thickness within the 5 mm. The existing 2.5D CAM only cuts blanks; **finished
twisted airfoils and the root retention need two-sided/indexed machining.**

---

## 6. Nozzle and exit system

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Nozzle total-pressure recovery | 0.985 – 0.99 – 0.995 | ↑ | second-order power loss | smooth convergent exit, no steps | duct exit |
| Exit-to-annulus area ratio | 0.9 – 1.0 – 1.2 | tune | expansion match | variable or fixed lip | duct exit |
| Exit lip thickness | 0.5 – 1.0 – 2 mm | ↓ | base drag | thin, radiused | exit edge |
| Wake mixing (mixed vs separate) | separate → mixed | mixed | jet efficiency | mixer lobes optional | exit |
| Exit vector-vane blockage | 2 – 5 – 9 % area | balance | control vs loss | vane fairing | exit plane |
| Jet velocity at 720 | V0 + 8 – 20 m/s | hold | thrust match | from mass flow | exit plane |

---

## 7. Bypass and variable geometry

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Bypass mass fraction β at 100 km/h | 0.35 – 0.50 – 0.65 | tune | low-speed thrust | variable nozzle areas | fan/core split |
| β at 200 km/h | 0.0 – 0.15 – 0.3 | ↓ | high-speed thrust | schedule | — |
| β at 720 km/h | 0.0 – 0.05 – 0.1 | hold ~0 | ram ram rise gives flow | fixed or closed | — |
| Nozzle area actuator range | ±10 – 25 – 40 % area | hold | schedule authority | servo/passive cam | exit |
| Low-speed thrust gain from VBR | 1.15 – 1.30 – 1.45× | ↑ | TWR | schedule | exit |
| Aux-inlet thrust gain | 1.05 – 1.15 – 1.25× | ↑ | TWR low speed | doors | inlet |
| Combined low-speed multiplier | 1.2 – 1.5 – 1.7× | tune | TWR 0–180 | both | — |

---

## 8. Airframe outer mould line

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Frontal solid area (with wings) | 242 – 270 – 296 cm² | ↓ | CdA | raster union silhouette (single source) | front view |
| CdA at 720 (UNRESOLVED — #1 gate) | **0.0008 – 0.0015 – 0.0030 m²** | ↓ | drag → power → range | VLM/CFD polar + tunnel; the old 0.0009 was an assumption, not a measurement | whole aircraft |
| Implied Cd on the 270 cm² silhouette | 0.03 – 0.055 – 0.11 | ↓ | the unknown in CdA | = CdA ÷ 0.027 m² | whole aircraft |
| Wing thickness (drives the wing strip) | 22 – 30 – 36 mm | ↓ | frontal area | t/c 0.06–0.10 × 365 mm chord | wing |
| Body **outline** (X×Y) | 175×72 – 186×78 – 205×90 mm | ↓ | duct pair + packs | loft | Z −280…280 |
| Body outline **area** | 126 – 145 – 185 cm² | hold | battery-driven | the outline above | X0,Y0 |
| Body solid (outline − bores + hubs, front inlet) | 60 – 75 – 110 cm² | hold | passthrough correction | raster | X0,Y0 |
| Body length | 480 – 560 – 640 mm | tune | fineness ratio | loft | Z axis |
| Fineness ratio L/D | 5 – 7 – 9 | ↑ | wave + friction drag | loft | — |
| Nose fineness (length/half-width) | 2.5 – 3.5 – 5 | ↑ | drag rise | ogive | nose |
| Superellipse exponent | 2.2 – 2.6 – 3.2 | tune | volume vs drag | section shape | body |
| Rear taper half-angle | 5 – 9 – 14° | ↓ | base drag | boattail | tail |
| Base area (if blunt) | 0 – 15 – 40 cm² | ↓ | base drag | tapering | aft end |
| Skin roughness | Ra 0.8 – 1.6 – 3.2 µm | ↓ | friction drag | fill + paint | all surfaces |
| Wetted-area allowance | 0.45 – 0.57 – 0.70 m² | hold | laminate mass | CAD | all skins |

---

## 9. Wing / lifting body

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Planform area | 0.13 – 0.19 – 0.30 m² | hold | wing loading | loft | X ±span |
| Span | 450 – 520 – 620 mm | hold | AR + frontal area | loft | lateral |
| Aspect ratio | 1.30 – 1.42 – 1.80 | ↑ | induced drag | span²/S — **jointly constrained with span and area; nominal is 0.52²/0.19 = 1.42**, not an independent choice | — |
| Sweep | 25 – 40 – 55° | tune | wave drag | LE sweep | wing |
| Thickness ratio | 0.08 – 0.10 – 0.13 | ↓ | frontal area | section | wing |
| Dihedral | −2 – 0 – 4° | tune | stability | jig | wing |
| Twist (root→tip) | −2 – 0 – +2° wash | tune | tip stall | loft | wing |
| Oswald efficiency | 0.62 – 0.70 – 0.78 | ↑ | induced drag | planform | wing |
| CL at 180 km/h, 7 kg | 0.10 – 0.20 – 0.35 | hold | far from stall | S, mass | wing |
| Wing loading | 25 – 38 – 55 kg/m² | tune | stall + drag | S, mass | wing |
| Wing structure FOS | 2.0 – 3.0 – 4.5 | ↑ | gust/landing | spar layup | wing |

---

## 10. Control effectors

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Effector set | **2 elevons + (3 or 4) vector vanes + 1 rudder = 6–7 servos** | hold | matches `PHASE15_CONTROL_SURFACES.md` §1/§9c | 6–7 PWM channels | tail |
| Elevon chord × span | 30×120 – 40×150 – 55×190 mm | tune | pitch/roll | hinged flap | wing TE |
| Vector vane size | Ø25×30 – Ø30×40 – Ø40×50 | tune | yaw/pitch/roll | 4 independent | duct exit |
| Vane deflection | ±15 – 20 – 30° | hold | authority | servo | exit |
| Command update rate | 200 – 400 – 800 Hz | ↑ | control | CAN/servo bus | flight board |
| Command latency | 3 – 6 – 10 ms | ↓ | phase margin | direct PWM | servo |
| Position feedback rate | 100 – 200 – 500 Hz | ↑ | jam detection | encoder/pot | servo |
| Feedback stale limit | 10 – 20 – 35 ms | ↓ | fail-safe | firmware | servo |
| Control-moment reserve | 1.5 – 2.0 – 3.0× strong; 1.1 – 1.4 – 2.0× medium | ↑ | authority | sizing | whole |
| Actuator rail | 6.0 – 7.4 – 8.4 V, ≤ stall current | hold | torque | separate BEC | avionics bay |
| Actuator stall current (each) | 0.5 – 1.5 – 3 A | ↓ | rail/heat | servo choice | — |

---

## 11. Motor (the selection that binds)

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Count | 6 (2 ducts × 3 rows) | hold | Rev-B is 6-ch | — | duct rows |
| **SELECTED MOTOR** | **Surpass Hobby "Rocket" 3670 4-pole, 1550 KV** | hold | 2 pole pairs, 36×70 can, ~270–276 g, ~1600 W; **in stock today at robu.in** | rewind to ~925 KV (×1.68 turns, R ×2.81) | robu.in |
| Unit price | ≤ ₹3,100 – 3,400 – 4,600 | ↓ | hard cost cap raised to ₹4,600 (2026-09-29); selected motor is **₹3,409** | cheap stator + rewind | robu.in |
| Mass each | 120 – 220 – 280 g | ↓ | all-up mass | small can | duct row |
| Continuous electrical input | **re-derive after rewind; do not quote stock** | ↑ margin | the 1550→925 KV rewind is ×1.68 turns → **phase R ×2.81**, so I²R copper loss rises ~2.8× and the continuous rating may fall BELOW stock, not above it (F-03). At 720 only 0.7–1.3 kW is needed (4–8 kW over 6); the 2.2 kW upper figure is the poor-inlet case and is NOT yet substantiated for the rewound stator | stator volume + rewind fill factor | duct row |
| Peak (30 s) input | 2.0 – 2.6 – 3.4 kW | ↑ | climb | thermal soak | — |
| Pole pairs | **2 MANDATORY** (no gearbox → direct drive at 36–47 krpm) | ↓ | 4 pp gives 188 k eRPM = 6 % margin; 2 pp gives 94 k = trivial. 3 pp does not exist in practice | inherent to rotor; **not changed by a rewind** | motor |
| Kv (direct drive, 80 mm) | 850 – 925 – 1,000 | tune | fan rpm / 44.4 | rewind turns | motor |
| Kv tolerance (batch) | ±2 – ±5 – ±8 % | ↓ | matched channels | wind to target | motor |
| Winding temp rollback | 95 – 105 – 110 °C | hold | drone-arm limit | NTC (12 required) | motor |
| Winding temp shutdown | 115 – 120 – 130 °C | hold | limit | NTC | motor |
| Bell/magnet warn | 65 – 70 – 75 °C | hold | limit | NTC | motor |
| Bell/magnet shutdown | 75 – 80 – 90 °C | hold | limit | NTC | motor |
| Mechanical rpm | 36 – 41 – 47 krpm | hold | fan | direct | motor |
| eRPM @ 2 pole pairs (36/41/47 krpm) | 72k – 82k – 94k | ↓ | ≤200 k | 2 pp | motor+ESC |
| eRPM @ 4 pole pairs (36/41/47 krpm) | 144k – 164k – **188k** | ↓ | ≤200 k — only **6 % margin at the top** | 4 pp | motor+ESC |
| Rewind wire class | Class-H (≥180 °C) or better | hold | reliability | rewind | motor |
| Rewind materials | ₹300 – 500 – 800 /motor | ↓ | cost | CNC attachment | workshop |
| Two matched rewinds | ±3 – ±5 – ±10 % Rphase | ↓ | current sharing | procedure | workshop |

**Why direct drive / why low poles.** At 12S the drone-arm motor window tops out
at 13.5–18 krpm, but the fan needs 36–47 krpm — so either gear up or rewind to a
high Kv and drive direct. A rewind is cheap and makes **direct drive** possible,
which deletes the gearbox's ~5 % loss and ~0.7 kg. Pole count is fixed by the
rotor magnets and is *not* changed by a rewind. Fewer poles = lower electrical
frequency at a given rpm = lower iron loss, so **2 pole pairs is favourable**,
not detrimental. The only low-pole penalty is torque-per-amp and inductance.

---

## 12. ESC (drone-arm Rev-B — fixed hardware)

| Parameter | Range / limit | Want | Why | How | Where |
|---|---|---|---|---|---|
| Channels | 6 (hard) | hold | 6 motors | — | ESC bay |
| Battery voltage | 38 – 44.4 – 50.4 V (12S) | hold | hard | — | input |
| Phase current, continuous | ≤60 A RMS/channel (hard) | ↓ | thermals | current limit | per cell |
| Phase current, burst | 75 – 90 – 105 A, <50 s | hold | climb | firmware | per cell |
| Aggregate current | **≤360 A (hard, 6 × 60 A)** — one number, used everywhere | hold | busbar/fuse | 6 fused feeds | distribution |
| Practical per-motor ceiling | **60 A** (= 360 ÷ 6); the 75 A "provisional short" is a per-motor figure and therefore **exceeds the 360 A bus limit** — only usable if the bus/fuse is up-rated | hold | fuse coordination | firmware | per cell |
| Simultaneous burst | 6 × 60 A = 360 A (no channel may exceed 60 A while others burst) | hold | hardware | busbar | distribution |
| eRPM | ≤200,000 (hard); design 82,000 (2 pp) | ↓ | FOC bandwidth | firmware | — |
| **Mechanical rpm** | direct drive needs **36,000–47,000**; current drone-arm firmware limit is 12,500/13,500 (17,000/18,000 provisional) | ↓ to the fan need | **the gate that must be raised/qualified (F-09)**; target a qualified limit ≥47,000 with 1.25× margin | firmware + overspeed qualification | — |
| PWM | 15 – 20 – 30 kHz | tune | losses/acoustic | firmware | per cell |
| Dead time | 150 – 300 – 600 ns | tune | shoot-through | TIM1 | per cell |
| Control | sensorless FOC, TIM1 complementary | hold | architecture | firmware | per cell |
| Safe state | all gates off until armed | hold | safety | hardware AND | per cell |
| Command/telemetry | CAN-FD, 6 independent | hold | architecture | MCP2518FD | supervisor |
| Shunt scale | 10 mV/A, 0.5 mΩ Kelvin | hold | sensing | hardware | per cell |
| MOSFET | 100 V TOLT, 6 per cell | hold | 12S margin | hardware | per cell |

---

## 13. Battery, bus and energy

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| **Sprint pack (now)** | 2× Bonka 6S 1600 mAh 150C | hold | must supply **120–240 A** at 720 (5.3–10.5 kW ÷ 44.4 V); 150 C × 1.6 Ah = 240 A | robu.in ₹10,638 | bay |
| Capacities supported | 1.3 – 5 – 10 Ah per 12S string | tune | range vs mass | bay + connectors | bay |
| Continuous C required at 720 | 75 – 100 – **150 C** | ↑ | **240 A ÷ 1.6 Ah = 150 C** on the sprint pack | pack choice | bay |
| Pair price | ₹8,500 – 10,600 – 12,000 (hard) | ↓ | cost cap | robu options | — |
| Max voltage | 46 – 48 – 50.4 V | hold | hard | — | bus |
| Practical battery current per motor | 20 – 40 – **60 A** (360 A ÷ 6) | hold | fuse coordination; 75 A is a whole-vehicle figure | firmware | per channel |
| Pack R0 (assumed) | 10 – 20 – 30 mΩ | ↓ | sag + heat | measure | pack |
| Battery heat at 720 | **142 – 285 – 427 W at 5.3 kW; 559 – 1119 – 1678 W at 10.5 kW** (I²R₀, I = P ÷ 44.4) | ↓ | thermal | copper + airflow | bay |

*(The earlier 150–350 W band was inconsistent with 240 A through 10–30 mΩ and
has been replaced by the I²R₀ expression above.)*
| Connector | XT90 / AS150, ≥8 AWG | hold | current | — | bay |
| Discharge cut-off | 3.2 – 3.4 – 3.5 V/cell | hold | pack life | firmware | — |
| Reserve fraction | 15 – 20 – 25 % | ↑ | safety | mission | — |

---

## 14. Thermal and airflow

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Airframe core temp | 30 – 45 – 55 °C | ↓ | PLA Tg margin | shield + duct cooling | whole |
| ESC/MOSFET junction | 80 – 110 – 125 °C | ↓ | life | spreader + airflow | ESC bay |
| ESC heat spreader ΔT | 10 – 25 – 45 °C | ↓ | junction | metal-to-air path | ESC bay |
| Motor case temp | 60 – 90 – 110 °C | ↓ | magnets | duct air wash | motor |
| Battery temp | 20 – 40 – 55 °C | hold | C-rate/life | vent + airflow | bay |
| Cooling airflow fraction | 2 – 5 – 10 % of duct flow | tune | heat vs thrust loss | bleed ports | duct |
| Bay vent open area | 5 – 15 – 30 cm² | hold | ΔP | cut-outs | bay |

---

## 15. Electrical harness and routing

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Phase wire gauge | 12 – 10 – 8 AWG | ↓ | I²R | silicone, matched lengths | motor→ESC |
| Phase wire length | 60 – 100 – 180 mm | ↓ | loss + inductance | layout | cells |
| Battery feed gauge | 8 – 6 – 4 AWG | ↓ | 330 A aggregate | 6 fused feeds | pack→ESC |
| Feed fuse rating | **55 – 60 – 65 A each** (six fuses sum to 330–390 A, matching the 360 A bus) | hold | protection — the earlier 70–120 A would not protect a 360 A bus | 6 fuses | distribution |
| Star/busbar point | single star, 6 taps | hold | no shared trunk | external busbar | centre |
| CAN-FD pair | 120 Ω term, ≤ 1 m | hold | signal | twisted | ESC↔flight |
| EMI separation | ≥ 15 – 25 – 40 mm | ↑ | noise | layout | whole |
| Grounding scheme | single-point star | hold | noise | harness | whole |

---

## 16. Mass, CG and inertia

| Item | Range kg (min–nom–max) | Want | Why | Where |
|---|---|---|---|---|
| 6 motors (rewound, 120–280 g each) | 0.72 – 1.68 – 1.68 | ↓ | dominant | duct rows |
| Sprint battery pack | 0.45 – 0.56 – 0.75 | ↓ | energy vs mass | bay |
| ESC + flight PCBs (populated) | 0.30 – 0.40 – 0.55 | ↓ | electronics | bay |
| Rotors/hubs/stators (6061) | 0.30 – 0.37 – 0.45 | ↓ | structure | duct rows |
| Duct + inlet composites | 0.20 – 0.28 – 0.40 | ↓ | shells | forward |
| Lifting-body shell | 0.20 – 0.27 – 0.38 | ↓ | composite | body |
| 6 actuators (servos) | 0.10 – 0.18 – 0.30 | ↓ | control | tail |
| Mounts, clamps, fasteners | 0.15 – 0.25 – 0.40 | ↓ | structure | distributed |
| Harness, connectors, fuses | 0.15 – 0.25 – 0.40 | ↓ | wiring | whole |
| Landing gear / skids | 0.25 – 0.40 – 0.60 | ↓ | recovery | belly |
| Avionics (GNSS, RF, Rx, air-data) | 0.12 – 0.20 – 0.30 | ↓ | control | bay |
| Payload | 0.80 – 1.00 – 1.20 | hold | requirement | CG |
| **Subtotal** | **3.74 – 5.84 – 7.41** | ↓ | sum of the rows | — |
| Growth reserve (15 %) | 0.56 – 0.88 – 1.11 | ↓ | design growth | — |
| **All-up** | **4.3 – 6.72 – 8.5** | ↓ | TWR/mass | — |

The all-up figure is now the **sum of the rows plus reserve**, not an asserted
number. (Earlier the table did not sum to its own all-up row; that is fixed.)
| CG longitudinal | at −5 – 0 – +15 mm of fan plane | hold | stability | battery slide |
| CG lateral | 0 ± 3 mm | ↓ | trim | symmetry |
| CG vertical | −5 – 0 – +10 mm | hold | stability | layout |
| Inertia: pitch / yaw / roll | **0.15–0.20–0.25 / 0.20–0.25–0.35 / 0.025–0.03–0.08 kg·m²** | ↓ | control | uniform-body estimate; replace with CAD mass properties + swing test | mass layout |

---

## 17. Structural and materials

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| PLA core service temp | ≤ 45 – 50 – 55 °C | ↓ | softening | shield/thickness | body |
| CF fabric areal | 160 – 200 – 240 gsm | tune | stiffness/mass | hand layup | shells |
| Glass fabric areal | 60 – 100 – 150 gsm | tune | isolate/damage | layup | shells |
| Ply count per face | 1 – 2 – 3 | tune | strength | layup | shells |
| Resin:fibre ratio | 0.6 – 0.8 – 1.0 | ↓ | weight | vacuum bag | layup |
| Composite shell thickness | 0.8 – 1.2 – 2.0 mm | tune | stiffness | layup | shells |
| Duct hoop SF | 2.0 – 2.5 – 3.5 | ↑ | containment | hoop plies | duct |
| Fastener material | steel / titanium | hold | strength | — | mounts |
| Burst containment | rotor retained ≤ 1.25× rpm | hold | safety | ring + sheath | duct |

---

## 18. Manufacturing and stock

| Item | Range / spec | Want | Why | How | Where |
|---|---|---|---|---|---|
| Rotor hub bar | 300 × 50 × 16 mm 6061-T6 (×1) | hold | stock | CNC 6 hubs | CAM X25–275 |
| Stator/rotor sheet A | 250 × 120 × 5 mm (×1) | hold | stock | 96 blanks | CNC |
| Stator/rotor sheet B | 300 × 120 × 5 mm (×1) | hold | stock | 108 blanks | CNC |
| Blank envelope | 26×7 – 29×8.2 – 32×10 mm | tune | fit | nest | sheets |
| Blank spacing | 1.0 – 1.5 – 2.5 mm | ↓ | yield | nest | sheets |
| Sheet edge margin | 0.5 – 1 – 2 mm | ↓ | yield | nest | sheets |
| Clamp margin on bar ends | 15 – 25 – 40 mm | ↑ | workholding | fixture | bar |
| CNC work envelope needed | ≥ 320 × 140 × 45 mm | ↑ | fixture/tool | machine | — |
| Finish tool | Ø0.5 – 0.8 – 1.0 mm | hold | surface | CAM | — |
| Rough tool | Ø1.5 – 2.0 – 3.0 mm | hold | MRR | CAM | — |
| Rotor/stator machining | two-sided/indexed 3D | hold | airfoils | new CAM | — |
| Rewind tooling | CNC attachment, ₹400 – 600 – 900 | ↓ | cost | 3D print + hall | 3018 Pro |
| Print volume | 0.5 – 0.7 – 1.0 L | hold | shells | FDM | — |
| CF to buy | 0.6 – 0.71 – 0.9 m² | hold | cut allowance | layup | — |
| Glass to buy | 0.6 – 0.71 – 0.9 m² | hold | layup | — | — |

---

## 19. Cost targets

| Item | Range INR (min–nom–max) | Want | Why |
|---|---|---|---|
| Motor, each | 3,100 – 3,400 – 4,000 (hard) | ↓ | cap |
| Six motors + wire + rewind tooling | 22,000 – 24,000 – 26,500 | ↓ | six-motor cap ≈24,000 |
| Battery pair | 8,500 – 10,600 – 12,000 (hard) | ↓ | cap |
| Metal stock | 1,200 – 1,500 – 2,000 | ↓ | 1 bar + 2 sheets |
| Composites (CF+glass+resin) | 1,500 – 2,300 – 3,200 | ↓ | layup |
| PLA + print | 500 – 800 – 1,200 | ↓ | shells |
| Actuators | 3,000 – 4,800 – 7,000 | ↓ | 6 channels |
| **Motor + battery subtotal** | **29,900 – 34,000 – 39,600** | ↓ | 6 × ₹3,409 = ₹20,454 motors + ₹10,638 battery = ₹31,092 nominal; with rewind materials ₹2.7–10.7k the motor line runs ₹23,154–31,154 |
| Six-motor cap (revised) | **≤ ₹27,600** | ↓ | raised: 6 × ₹4,600 unit cap (was ₹24,000 at ₹4,000/unit). The selected build + *typical* rewind (₹6,700) = ₹27,154 → **fits only just**; the cheap-rewind path (₹2,700 → ₹23,154) has real margin (F-04) |
| **Full row sum (incl. metal, composites, PLA, actuators)** | **36,700 – 43,800 – 51,900** | ↓ | sum of every row above (the earlier "propulsion subtotal" did not sum its own rows) |

---

## 20. Instrumentation and test (what/why/how/where)

| Measurement | Range of interest | Why | How | Where |
|---|---|---|---|---|
| Inlet total-pressure rake | 6–12 probes, fan face | recovery is driver #1 | total+static of 6 ports | fan face |
| Static taps on duct | 6 ports | loss mapping | pressure ports | along duct |
| Thrust stand force | 0 – 60 – 180 N (static thrust is 82–176 N at TWR 1.3–2.1; the earlier 0–40 N range was below the static thrust) | TWR + drag | load cell | test stand |
| Motor phase current | 0 – 60 – 90 A | limits | shunt/LEM | ESC |
| Bus current/voltage | 0 – 360 A, 38–50 V | energy | shunt | pack |
| Motor rpm | 0 – 47 krpm | tip Mach/eRPM | ESC telemetry/hall | motor |
| Winding temp ×6 | 20 – 130 °C | protection | NTC | motor |
| Bell temp ×6 | 20 – 90 °C | magnets | NTC | motor |
| Vibration | 0 – 5 – 20 g rms | rotor health | accel | duct |
| CG / mass | 4.3 – 8.5 kg | TWR | scales | whole |
| Tunnel/CFD CdA | 0.0008 – 0.0030 m² | range | force balance/CFD | whole |

---

## 20b. Mission decision and the dual-capability path

**Now:** the aircraft is **either** a 720 km/h sprint **or** a ~116 km cruiser —
one mission per flight, chosen by the pack in the bay. It is not both at once.

**Later, with better materials, we keep both options open** by removing the
three bottlenecks that currently force the split:

| Bottleneck now | Today | Better material unlocks | Keeps open |
|---|---|---|---|
| PLA core (Tg 45–55 °C) | prints easily | PEI/ULTEM, PEEK, or CF/phenolic prepreg (150–250 °C), or an aluminium/CF duct | both (thermal) |
| Battery energy vs power | 1.6 Ah 150 C **or** 5–10 Ah 10–12 C | higher-power Li-ion 21700 (15–20 C) or semi-solid-state: high C **and** high Wh | both (energy) |
| Motor thermal at 2.2 kW | 0.22 kg inrunner | SH-grade magnets (120 °C+), Class-H+, better copper fill | both (power) |

**Design provisions that keep the option alive (do these now):** the 200×135×75 mm
bay, the two independent fused 12S feeds, the CG/mass reserve to 2.6 kg, modular
interchangeable ducts with common mounts, and the same six/seven effector and
motor interfaces. Then "sprint or endurance" is a pack and a duct swap, not a
new airframe.

---

## 21. Future expansion provisions (decided, with ranges)

| Provision | Range | Why | How | Where |
|---|---|---|---|---|
| Battery bay reserved | 190–200–215 × 128–135–145 × 70–75–85 mm | fit large Li-ion/hybrid | rails + straps | centre bay |
| Independent fused 12S feeds | 2 – 3 – 4 | parallel/switch packs | busbar + fuses | distribution |
| Mass reserve for future pack | up to 2.2 – 2.6 – 3.2 kg | CG/balance | ballast range | bay |
| Hybrid/range-extender tap | 1 isolated 12S interface | future range | connector panel | bay |
| Control channels reserved | 6 PWM + feedback | effectors | flight board | tail |
| Motor-temp channels required | 12 (2/motor) | protection | drone-arm #19 | motors |
| Actuator interface defined | 6 ch, ≥400 Hz, ≤10 ms | control | drone-arm #18 | tail |
| Pack swap | sprint ↔ range, same bay/connectors | dual mission | standardise | bay |

---

## 22. Open gates (close before flight; each must land inside a range above)

| Gate | Passing range | Evidence needed |
|---|---|---|
| Inlet recovery | 0.985 – 0.995+ | rake at 0–720 km/h |
| Fan installed FOM | 0.72 – 0.86 | standalone + installed |
| Motor map | 1.5 – 2.2 kW, 12S, 41 krpm | dyno with rewound Kv |
| Rotor containment | 1.25× 41 krpm | spin test |
| Direct-drive rotor rating | 36 – 47 krpm | balance/overspeed |
| ESC qualification | ≤60 A/ch, ≤200 k eRPM | Rev-B bench |
| Battery DCIR/thermal | 10 – 30 mΩ, ≤55 °C | pulse + soak |
| CdA | 0.0008 – 0.0030 m² (must match §8) | VLM/CFD + tunnel |
| TWR 0–180 | ≥1.0 | installed thrust curve |
| All-up mass | ≤8.5 kg | weigh |
| Rewind repeatability | ±5 % Rphase | two builds |

---

## 23. Master parameter register (quick reference — all ranges)

```
SPEED        design 700-720-750 km/h | cruise 620-650-700 | max-range 285-295-315
TWR          0-180 km/h >=1.0 (nominal 1.1-1.3) | static 1.3-1.6-2.1
MASS         AUW 4.5-6.7-8.5 kg (rows + 15% reserve, §16) | payload 0.8-1.0-1.2 kg | CG -5..+15 mm
INLET        recovery 0.985-0.990-0.995+ (WANT UP) | capture 0.80-0.85-0.95
             mouth 90-110-140 cm2 | lip 1.5-2.5-4 mm | length 80-110-160 mm
             diffusion 3-5-7 deg | aux inlet +0-30-60% (open to 180 km/h)
FAN          OD 72-80-90 mm | hub 34-40-46 | bore D-2 | 3 rows/duct | 2 ducts side-by-side
             rpm 36-41-47 krpm | tip Mach 0.42-0.50-0.60 | module 95-110-130 mm
             wall 1.5-2-3 mm | exit area 0.9-1.0-1.15x annulus | exit recovery 0.985-0.99-0.995
BLADES       rotor 10-12-14 (13/12/11) | stator 17-21-25 (23/21/19)
             rotor chord 13-16-19 | stator chord 6-8-10 | span 17-20-24 mm
             root t/c 0.16-0.20-0.24 | tip t/c 0.08-0.12-0.16 | tip clr 0.4-0.7-1.2 mm
             FOS 3.0-4.5-6.0 | stator Re 50k-70k-100k | 6061-T6
AIRFRAME     frontal 242-270-296 cm2 | CdA 0.0008-0.0015-0.0030 m2 (UNRESOLVED, gate #1)
             body outline 126-145-185 cm2 / 175x72-186x78-205x90 mm | solid 60-75-110 cm2 | length 480-560-640 mm
WING         area 0.13-0.19-0.30 m2 | span 450-520-620 mm | AR 1.30-1.50-1.80
             span, area and AR are JOINTLY constrained (AR = span^2 / area)
             sweep 25-40-55 deg | t/c 0.08-0.10-0.13 | Oswald 0.62-0.70-0.78
CONTROL      2 elevons + (3 or 4) vanes + 1 rudder = 6-7 servos | elevon 30x120-40x150-55x190 | vane D25-30-40
             command 200-400-800 Hz (board) | effective servo BW 2-5-10 Hz | latency 5-15-30 ms | feedback 100-200-500 Hz
             deflection limit high speed 0.01-0.05-0.10x
MOTOR        6x | <=3100-3400-4000 INR | 120-220-280 g | 1.5-1.8-2.2 kW cont (need only 0.7-1.3 at 720)
             2 OR 4 pole pairs (discrete) | Kv 850-925-1000 | 36-41-47 krpm
             eRPM 72k-82k-94k @2pp | 144k-164k-188k @4pp (6% margin)
             winding 95-105-110 rollback / 115-120-130 shutdown
ESC          Rev-B 6ch | 12S 38-44.4-50.4 V | <=60 A RMS/ch cont, 75-90-105 burst
             <=360 A agg | <=200k eRPM | PWM 15-20-30 kHz | dead 150-300-600 ns
BATTERY      sprint 2x Bonka 1600 mAh 150C (240 A) INR 10,638
             capacity 1.3-5-10 Ah | C needed 75-100-150 | pair 8500-10600-12000 INR
             R0 10-20-30 mOhm | heat 142-285-427 W @5.3kW / 559-1119-1678 W @10.5kW | reserve 15-20-25%
THERMAL      core 30-45-55 C | ESC jn 80-110-125 C | motor 60-90-110 C | batt 20-40-55 C
LAYOUT       ducts X +-43-48 | battery bay 190-200-215 x 128-135-145 x 70-75-85 mm
             ESC 150x150x20 @ Z220 | FC 140x100x20 @ Z345 | vane exit Z240-280
STOCK        bar 300x50x16 | sheets 250x120x5 + 300x120x5 | blank 26x7-29x8.2-32x10
             spacing 1.0-1.5-2.5 | clamp 15-25-40 mm ends
COMPOSITES   CF 160-200-240 gsm 0.6-0.71-0.9 m2 | glass 60-100-150 gsm 0.6-0.71-0.9 m2
             resin:fibre 0.6-0.8-1.0 | shell 0.8-1.2-2.0 mm | PLA 0.5-0.7-1.0 L
COST         motor+battery 30,500-35,000-38,500 INR | full row sum 36,700-43,800-51,900 | motors <=24,000 | battery <=12,000
POWER        720 km/h: 4-8 kW (floor 2.7, poor inlet 10.5) | loss: fan ~1.1 kW dominant
RANGE        sprint 4.1-9.1-16.7 km @720 (matches the 2.7-10.5 kW band) | max 116-150-219 km @285-295-315 km/h
FUTURE       bay for large Li-ion/hybrid | 2-4 fused 12S feeds | pack reserve to 2.6 kg
```

---

*Every value above is a band with a nominal and a preferred direction; none is a
rigid set-point. Where a band cannot be met, the fallback is to widen the band
and record the new evidence, not to force the point. All screening numbers carry
the analyst class **[A]** until replaced by measured data.*
