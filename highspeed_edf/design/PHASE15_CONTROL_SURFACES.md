# Control surfaces — detailed specification (Phase 15)

Hand-written, all values as ranges (`min – nominal – max`), with what / why / how
/ where. This is the file we skipped; it closes the gap between the "6 effectors"
placeholder and an actuation system someone can actually build.

Datum: **X lateral, Y vertical, Z flight (aft +)**, origin at the fan plane.

---

## 1. Why this architecture: 2 elevons + 4 vector vanes

**The problem.** Below ~200 km/h dynamic pressure is tiny — at 180 km/h
(3 km ISA) q ≈ 1,140 Pa, so a conventional elevon of sensible size makes almost
no moment. But the requirement demands **TWR ≥1.0 and strong control from
0–180 km/h**, i.e. right where aero surfaces are weakest. Meanwhile the EDF is
thrusting hard at low speed, so the efflux itself is a control asset.

**The answer.** Split authority by regime:

- **4 vector vanes in the EDF exit** provide control where there is no
  aerodynamic pressure — they deflect the jet. Authority scales with *thrust*,
  which is highest exactly at low speed.
- **2 elevons on the wing trailing edge** take over as dynamic pressure builds,
  and dominate above ~250 km/h where aero moments are huge.

**What / why / how / where**

| Item | What | Why | How | Where |
|---|---|---|---|---|
| Elevons ×2 | trailing-edge flaps, differential for roll | cheap, effective at speed | hinged, mass-balanced | wing TE, Z ≈ +150 |
| Vector vanes ×**3 or 4** | deflectors in the jet | control at zero airspeed | 3 tangential single-axis if the two exits merge; 4 (2/duct) if they stay separate — see §9c | duct exit, Z ≈ 240–280 |
| Redundant roll | elevons + vanes | cross-check | mixed in the allocator | — |
| **Rudder ×1** | actuated on the tail fin | yaw has **no authority above ~400 km/h** without it (§5b) | small rudder on one fin | tail |
| **Effector/servo total** | 2 elevons + 3–4 vanes + 1 rudder = **6–7 servos** | minimum-cost full-authority set | see §9c cost table | — |

---

## 2. Control-authority budget (screening, ~7 kg)

Axis mapping matches the datum (X lateral, Y vertical, Z flight): **pitch about X
(inertia 0.15–0.20–0.25), yaw about Y (0.20–0.25–0.35), roll about Z
(0.025–0.03–0.08 kg·m²)**. These are uniform-body estimates and MUST be replaced
by CAD mass properties and a swing/pendulum test before the control laws are
designed. (Earlier drafts used 0.16/0.50/0.58 with the axes mislabelled; that set
is withdrawn.)

Elevon moment = `q·S_e·Cl·arm`; vane moment = `T_avail·sin(20°)·arm_v`, where
`T_avail` is the fan's **available** thrust at fixed power (5.3 kW), which falls
monotonically with speed. Inertias used: **roll 0.025–0.03–0.08**, **pitch
0.15–0.20–0.25**, **yaw 0.20–0.25–0.35 kg·m²** (uniform-body estimate; to be
replaced by CAD mass properties and a swing test). Targets: **pitch ≥2–5 rad/s²,
roll ≥3–15 rad/s²**.

| Speed km/h | q (Pa) | Elevon moment (N·m) | Vane moment (N·m) | Pitch margin vs 3 rad/s² | Roll margin vs 10 rad/s² | Regime |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 0 | 0.0 | 9.5 | 16× | 16× | vane only |
| 45 | 71 | 0.1 | 4.8 | 8× | 9× | vane only |
| 90 | 284 | 0.4 | 4.5 | 8× | 10× | vane dominant |
| 135 | 639 | 1.0 | 4.2 | 8× | 12× | mixed |
| 180 | 1,136 | 1.7 | 3.9 | 9× | 16× | mixed (requirement edge) |
| 250 | 2,192 | 3.3 | 3.4 | 11× | 24× | elevon rising |
| 300 | 3,156 | 4.7 | 3.2 | 13× | 31× | elevon |
| 400 | 5,611 | 8.4 | 2.6 | 18× | 50× | elevon |
| 500 | 8,767 | 13.2 | 2.3 | 26× | 76× | elevon, huge |
| 600 | 12,625 | 18.9 | 1.9 | 35× | 106× | elevon, huge |
| 720 | 18,180 | 27.3 | 1.7 | 48× | **151×** | elevon, huge |

**Reading (corrected).** Two things changed from the earlier version: the vane
moment is now **monotonically decreasing** (it tracks available jet thrust, as it
must), and the roll inertia is ~5× smaller than previously used, so roll margin
is far larger. Crossover between vane and elevon authority is ~200–250 km/h.

**Authority is not the constraint — it is 8–150× oversized.** The real
constraint is the opposite: at high speed the surfaces must be **rate- and
deflection-limited to a few percent** or they will over-control and load the
structure. The high-speed deflection limit in §7 should therefore be **0.01–0.05×
full**, not 0.08–0.30×. The remaining constraints are trim, yaw stability,
flutter, and servo rate.

| Derived requirement | Range (min–nom–max) | Want | Notes |
|---|---|---|---|
| Pitch acceleration, 0–180 km/h | 3 – 5 – 8 rad/s² | hold | ≥2 needed |
| Roll acceleration, 0–180 km/h | 3 – 6 – 10 rad/s² | hold | ≥3 needed |
| Pitch acceleration, 500–720 | 15 – 30 – 60 rad/s² | cap | must rate-limit |
| Roll acceleration, 500–720 | 20 – 45 – 90 rad/s² | cap | must rate-limit |
| Control-moment reserve | 1.5 – 2.0 – 3.5× strong; 1.1 – 1.4 – 2.0× medium | ↑ | requirement gate |
| Max deflection, low speed | 20 – 25 – 32° | hold | stall of vane/elevon |
| Max deflection, high speed | 3 – 6 – 12° | ↓ | load limiting |
| Deflection rate | 100 – 250 – 500 °/s | hold | bandwidth |

---

## 3. Elevons (pitch + roll)

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Count | 2 | hold | pitch + roll | one per side | wing TE |
| Span each | 100 – 150 – 200 mm | tune | roll authority | cut from wing | outer TE |
| Chord each | 25 – 40 – 60 mm (25–30 % local chord) | tune | hinge moment | flap | TE |
| Area each | 0.0025 – 0.006 – 0.012 m² | tune | moment | — | — |
| Thickness | 3 – 6 – 10 % chord | ↓ | drag | loft | — |
| Deflection | ±12 – 25 – 35° | hold | authority | servo | hinge |
| Hinge line | 25 – 30 – 40 % chord | hold | balance | — | — |
| Leading-edge gap seal | 0.2 – 0.5 – 1.0 mm | ↓ | flutter/hysteresis | silicone seal | hinge |
| Mass balance | 0 – 30 – 60 % static balance | ↑ | flutter | LE weight | elevon LE |
| Flutter margin | ≥1.2 – 1.4 – 2.0× Vd (720) | ↑ | safety | mass balance + stiffness | elevon |
| Hinge moment at 720 | 0.05 – 0.20 – 0.45 N·m | hold | servo sizing | q·S·ch·c | hinge |
| Servo torque with margin | 0.3 – 0.8 – 2.0 N·m (3–20 kg·cm) | ↑ | gust load | servo + linkage | wing |
| Servo type | digital metal-gear micro | hold | torque/speed | 6.0–8.4 V | wing |
| Position feedback | potentiometric / magnetic | hold | jam detect | integrated | servo |

---

## 4. Vector vanes (thrust vectoring)

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Count | 4 (UL, UR, LL, LR) | hold | pitch/yaw/roll | independent | duct exits |
| Vane size | 25×30 – 30×40 – 40×55 mm | tune | jet deflection | flat/airfoil plate | exit plane |
| Ring radius (from duct axis) | 38 – 44 – 50 mm | hold | roll moment arm | exit geometry | duct exit |
| Axial arm from CG | 0.22 – 0.27 – 0.32 m | hold | pitch/yaw moment | tail length | Z 240–280 |
| Deflection | ±15 – 22 – 35° | hold | authority | servo | vane root |
| Vane blockage at 0° | 2 – 4 – 8 % exit area | ↓ | thrust loss | thin fairings | exit |
| Jet dynamic pressure on vane | 15 – 20 – 28 kPa | hold | hinge load | ρjet·Vj²/2 | vane |
| Vane hinge moment | 0.03 – 0.09 – 0.25 N·m | hold | servo sizing | qjet·S·ch·c | hinge |
| Vane material | 6061-T6 (same sheet family) | hold | stock | CNC | — |
| Vane temp exposure | 60 – 90 – 120 °C | hold | material | jet air | exit |
| Servo torque with margin | 0.2 – 0.5 – 1.5 N·m (2–15 kg·cm) | ↑ | jet unsteady loads | servo | exit |
| Vane flutter margin | ≥1.5 – 2.0 – 3.0× Vd | ↑ | jet excitation | stiff mount | exit |

---

## 5. Yaw stability and stabilisers

**What.** With no vertical tail, yaw has no weathercock stability; the aircraft
would be directionally unstable. Two small canted fins plus differential
vectoring fix this.

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Vertical fins | 2 | hold | yaw stability | canted outboard | aft body |
| Fin height | 50 – 70 – 100 mm | tune | Cnβ | loft | tail |
| Fin chord | 60 – 90 – 130 mm | tune | AR | loft | tail |
| Fin cant | 15 – 30 – 45° outward | tune | roll-yaw coupling | jig | tail |
| Fin thickness ratio | 0.06 – 0.10 – 0.14 | ↓ | drag | section | — |
| Yaw stability derivative Cnβ | 0.02 – 0.06 – 0.12 /rad | ↑ (stable) | directional stability | fin size | tail |
| Yaw control moment | 0.5 – 2 – 5 N·m | hold | coordination | vane differential | exit |
| Dutch-roll damping | ζ 0.05 – 0.15 – 0.35 | ↑ | handling | fin + control | tail |
| Weathercock margin | ≥1.0 – 1.2 – 1.5× (stable) | ↑ | safety | fin | tail |

### 5b. Why not pure active yaw? (the board is not the limit)

The control board is **fast enough**: the ICM-42688-P IMU runs to 32 kHz and our
loop is 400–800 Hz. The slowest link is the **servo at ~5–15 Hz**. So the
question is not measurement speed — it is control *power*, divergence rate,
observability, and fail-safety. Numbers (no fin, Cnβ ≈ −0.03 /rad unstable):

| Speed | q | Yaw stiffness Nβ | Divergence rate ω | Time-to-double | Vane yaw authority (20°) | Moment for 5° β | Verdict |
|---:|---:|---:|---:|---:|---:|---:|---|
| 90 km/h | 284 Pa | −0.84 N·m/rad | 1.2 rad/s | 0.58 s | 4.51 N·m | 0.07 N·m | ample |
| 180 km/h | 1,136 | −3.4 | 2.4 rad/s | 0.29 s | 3.89 N·m | 0.29 N·m | **13× OK** |
| 300 km/h | 3,156 | −9.4 | 4.0 rad/s | 0.17 s | 3.15 N·m | 0.82 N·m | **3.8× OK** |
| 500 km/h | 8,767 | −26.0 | 6.7 rad/s | 0.10 s | 2.25 N·m | 2.27 N·m | **0.99× — marginal** |
| 720 km/h | 18,180 | −53.9 | 9.6 rad/s | 0.07 s | 1.65 N·m | 4.70 N·m | **fails 2.9×** |

*(Vane yaw authority is now taken from available jet thrust at fixed power and is
monotonically decreasing, consistent with §2. The earlier table showed a
non-monotonic 2.82→0.77→…→1.14 N·m and has been withdrawn.)*

Three independent blockers above ~300–400 km/h:

1. **Control power.** Thrust-vectoring yaw authority *falls* with speed (thrust
   drops) while the destabilising aerodynamic moment *rises* with q. The vanes
   run out of yaw authority around 300–400 km/h.
2. **Bandwidth.** With no fin the divergence rate reaches ~9.6 rad/s (1.5 Hz) at
   720 km/h; a healthy active loop wants ~3–5× that (5–8 Hz), which is at the
   edge of a 5–15 Hz servo and leaves no margin.
3. **Observability + fail-safety.** Active yaw needs sideslip β, which needs air
   data (multi-hole/AoA-β probe) or a trusted estimator — we have no such sensor
   specified — and with no passive stability a single failure means departure.

**Conclusion.** Active yaw is the **primary control at low speed** (vanes are
excellent 0–200 km/h). Above ~300–400 km/h the aircraft still needs an
aerodynamic yaw surface. Two small fins are cheaper, lighter, and safer than
enlarging the vanes, speeding the servos, and adding air data. Fins also make β
≈ 0 in trim, which *removes* the observability problem.

**If we ever want to delete the fins**, the requirements are: yaw authority
≥1.1–2.0× the destabilising moment at 720 km/h (≥5–10 N·m), servo bandwidth
≥15–30 Hz, a β sensor, and a demonstrated one-fault recovery. That is a heavier,
higher-risk path than two canted fins costing ~11 cm² of frontal area.

### 5c. Fins vs winglets vs central fin — why canted tail fins

| Option | Yaw stability | Roll–yaw coupling | Drag | Frontal area | Flow risk | Verdict |
|---|---|---|---|---|---|---|
| Central vertical fin | strongest, cleanest | minimal | small | adds height | body wake at high α | good fallback |
| **Twin canted tail fins** | strong, tunable | controlled by cant | small | low (split height) | moderate | **chosen** |
| Winglet (tip-canted) | weak–moderate | **very strong** (force at ±260 mm) | **reduces induced drag** | low | tip vortex / separated flow | range aid, not yaw primary |
| Split elevons (drag rudders) | moderate | strong, drag-heavy | high at high speed | none | wake | no-fin fallback only |

**Why canted tail fins, not winglets.** A winglet sits ~260 mm off the
centreline, so any side force it makes creates a **large rolling moment** (roll–
yaw coupling that the allocator must constantly undo), and it operates in the
tip vortex where its yaw contribution is unpredictable, especially when a test
flight separates the wing. Canted **tail** fins sit near the centreline with a
longer moment arm, give clean, predictable Cnβ, and the cant angle lets us dial
in a *small, controlled* roll coupling deliberately. Winglets are genuinely
useful — but as a **range/induced-drag device added later if they earn their
mass**, not as the yaw surface.

### 5d. Buffet vs actuator speed — this is the clincher for fins

Test flights **will** buffet while we debug the inlet and exit: separated flow
buffet on a small body is typically **10–100 Hz** broadband, with structural
modes from ~30 Hz up. Our servos are **5–15 Hz**. So:

- A 20–60 Hz buffet disturbance is **above the servo bandwidth** — active yaw
  literally cannot move fast enough to reject it. Measurement is not the issue
  (the IMU sees it at 1–8 kHz); **actuation** is.
- The correct division of labour is therefore:
  1. **Static stability (fins)** carries the high-frequency disturbance
     passively — the aircraft weathercocks without any command.
  2. **Damping (fin + airframe)** kills the oscillation.
  3. **Active control (vanes/elevons)** only handles *trim and manoeuvre*, which
     are low-frequency.

With fins, buffet shows up as small sideslip that the fin simply resists, and
the slow servo is irrelevant. Without fins, the same buffet becomes an
uncontrollable yaw excursion. **So buffeting during test is not a reason to make
the servos faster — it is the reason to keep the fins.**

### 5e. Why the yaw rudder is at the tail, not tipped on the wing

A common proposal is to mount the canted fins **at the wingtips and give them
real rudder surfaces**, instead of at the aft body. The physics says no — but
the tip device is still worth having for a *different* job.

**Yaw moment = side force × longitudinal distance from the CG.** So the arm is
everything:

| Fin location | Arm (m) | Moment per N of side force | Area needed for 5 N·m |
|---|---:|---:|---:|
| Tip fin (at wing station, z ≈ 0.15) | 0.150 | 0.150 N·m/N | **36.7 cm²** (≈96×38 mm) |
| Tail fin (z ≈ 0.40) | 0.400 | 0.400 N·m/N | **13.8 cm²** (≈59×23 mm) |

The tail fin is **2.67× more efficient**. A tip rudder must therefore be ~2.7×
larger, and because it sits at ±260 mm lateral, the same side force makes a
**roll moment ≈ 0.26/0.15 ≈ 1.7× its own yaw moment** — constant roll–yaw
coupling the allocator has to fight. Tip-mounted fins also couple with wing
torsion (flutter) and add mass at the worst place for wing inertia.

**The tailless "split drag rudder" trick is worse.** Yaw = x_tip × Δdrag =
0.26·ΔD. Making 5 N·m needs **19.2 N of asymmetric drag**, while the whole
aircraft's drag at 720 km/h is only **12.4 N** — a **156 % drag increase**. Hard
no for a speed/range aircraft.

**But the wingtip device still earns its place — as a range aid.** At the
max-range speed (~295 km/h) **induced drag is 59 % of total drag**; a 15 %
induced-drag cut saves **9 % of total drag**. So:

| Device | Job | Control? | Verdict |
|---|---|---|---|
| Canted **tail** fins | yaw stability + yaw control | yes (small rudder) | **primary** |
| Canted **tip** winglets | reduce induced drag / range | no | **add later, if it earns its mass** |
| Tip rudders | yaw from the wingtip | yes | reject: 2.7× area, 1.7× roll coupling, tip flutter |
| Tip drag rudders | yaw from drag | yes | reject: +156 % drag at 720 |

**Fallback only:** if the aft fins are ever deleted, swept tip fins with rudders
become the least-bad option — but size them ≥36.7 cm² each, sweep them to gain
arm, and accept the roll–yaw coupling.

---

## 6. Actuation system

| Parameter | Range (min–nom–max) | Want | Why | How | Where |
|---|---|---|---|---|---|
| Actuator count | 6 | hold | 2 + 4 | one per surface | wing + exit |
| Type | digital metal-gear servo | hold | torque + feedback | PWM + feedback | — |
| Rail voltage | 6.0 – 7.4 – 8.4 V | hold | torque/speed | dedicated BEC | avionics bay |
| Rail current (all 6, peak) | 3 – 9 – 15 A | hold | stall sum | BEC + capacitors | bay |
| Command update rate (board side) | 200 – 400 – 800 Hz | ↑ | outer-loop rate; **the servo, not the bus, is the limit** | flight board PWM | bay |
| Effective actuator bandwidth (servo) | **2 – 5 – 10 Hz** | ↑ | this is the real closed-loop limit; commanding at 400 Hz buys nothing beyond it | servo choice | surface |
| Command latency (board to servo) | **5 – 15 – 30 ms** | ↓ | dominated by the servo, not the PWM frame | direct PWM | link |
| Position feedback rate | 100 – 200 – 500 Hz | ↑ | jam/stale detection | integrated sensor | servo |
| Feedback stale limit | 10 – 20 – 35 ms | ↓ | fail-safe | firmware | — |
| Servo torque (selected) | 2 – 5 – 20 kg·cm | ↑ | gust + unsteady jet | servo choice | — |
| Servo speed | 0.06 – 0.12 – 0.25 s/60° | ↑ | rate | servo choice | — |
| Backlash | ≤ 0.5 – 1.0 – 2.0° | ↓ | flutter | tight linkage | hinge |
| Gear train | metal, ≥1.5 – 2.5 – 4.0× shock margin | ↑ | landing loads | servo choice | — |
| Rail isolation | separate from ESC 5 V aux | hold | brownout | dedicated regulator | bay |
| Fail-safe state | hold – 0 – neutral | hold | safety | firmware + spring | surface |

---

## 7. Control allocation

**What.** Six effectors map to three commanded moments (pitch, yaw, roll) plus
trim. Because the two surface families act on very different physics, the mixer
is **gain-scheduled by dynamic pressure and by thrust**.

| Element | Range (min–nom–max) | Why | How | Where |
|---|---|---|---|---|
| Allocation matrix | 6 → 3 (pitch/yaw/roll) | redundant control | pseudo-inverse | flight software |
| Schedule breakpoint | 150 – 225 – 350 km/h | hand over vane→elevon | measured-thrust/q blend | software |
| Vane weight at 0 km/h | 0.9 – 1.0 – 1.0 | primary | schedule | software |
| Vane weight at 720 km/h | 0.0 – 0.1 – 0.2 | elevons dominate | schedule | software |
| Elevon weight at 0 km/h | 0.0 – 0.05 – 0.1 | ineffective | schedule | software |
| Elevon weight at 720 km/h | 0.9 – 1.0 – 1.0 | primary | schedule | software |
| High-speed deflection limit | **0.01 – 0.05 – 0.10× full** | structural/load | envelope limiter (authority is 8–150× over) | software |
| Trim authority | ±5 – 10 – 20 % | CG shifts | integral trim | software |
| Slew limit | 200 – 350 – 600 °/s | avoid over-control | rate limiter | software |
| Ignorable gap (deadband) | 0.2 – 0.5 – 1.0° | servo jitter | deadband | software |

---

## 8. Failure modes and redundancy

| Failure | Effect | Mitigation (range) | Where |
|---|---|---|---|
| One vane jammed | asymmetric moment | re-allocate across 5 (allocator holds ≥1.3–1.6–2.0× reserve) | software |
| One elevon failed | roll asymmetry | counter with opposite elevon + vanes | software |
| Servo stall | surface frozen | detect via feedback lag (≥20–30–50 ms) → fault | firmware |
| Feedback loss | no position | if stale >10–20–35 ms → fail to neutral/hold | firmware |
| Rail brownout | all servos soft | independent rail + ≥500 – 2000 – 5000 µF bulk | bay |
| Signal loss (CAN/PWM) | no commands | timeout → neutral + throttle inhibit | firmware |
| Vibration lock | servo jitter | damping, thread lock, ≥1.5–2.5–4× margin | mounts |
| Single-point PDB | total loss | 2 independent fused 12S feeds (already decided) | distribution |

**Requirement to keep:** after **any one** actuator fault, the remaining five
must still deliver ≥1.1 – 1.3 – 2.0× the demanded moment through 700 km/h.

---

## 9. Interface with drone-arm (issues #18, #19)

| Requirement | Range | Why | Where |
|---|---|---|---|
| Independent PWM channels | 6 (ESC on CAN-FD so PWM is free) | one per surface | flight board |
| PWM frame rate | 200 – 400 – 800 Hz | bandwidth | board |
| PWM pulse | 1000 – 1500 – 2000 µs, 3.3 V logic | standard servos | board |
| Actuator rail | 6.0 – 7.4 – 8.4 V, 3 – 9 – 15 A | torque | board/BEC |
| Feedback inputs | 6 analog/digital | jam detection | board |
| Fail-safe | hardware + firmware neutral | safety | board |
| Status to ESC/tx | allocation + faults on CAN-FD | situational awareness | board |
| Motor temp inputs | 12 (2/motor) | protection | drone-arm #19 |
| Actuator connector | keyed, ≥3 A contacts | current | surface |

---

## 9b. Mass balancing of control surfaces (and the jig)

**Why.** A control surface whose mass centre sits *behind* its hinge can flutter:
the surface reacts to a disturbance, the inertia drives it further, the aero
load feeds back, and it diverges — often faster than a servo can catch. The fix
is to move the surface's mass centre to (or slightly ahead of) the hinge line,
so inertia opposes rather than reinforces the motion. This is a **ground
adjustment**, done before flight and re-checked after any repair.

**Target (ranges, for every one of the 2 elevons and 4 vanes):**

| Parameter | Range (min–nom–max) | Want | Why |
|---|---|---|---|
| Static balance, surface CG vs hinge | 0 – 2 – 5 % chord **ahead** of hinge | ↑ nose-heavy | flutter margin |
| Balance test on hinge | holds at any position; ≤0–2–5° nose-down droop | ↑ | pass/fail |
| Flutter margin | ≥1.2 – 1.4 – 2.0× Vd (720 km/h) | ↑ | safety |
| Balance mass budget | 5 – 25 – 60 % of surface mass | ↓ | weight |
| Surface mass (elevon) | 15 – 30 – 60 g | ↓ | balance weight |
| Surface mass (vane) | 8 – 18 – 35 g | ↓ | jet inertia |
| Balance mass material | lead / brass / tungsten LE | hold | density |
| Re-check interval | every repair / every 10 flights | hold | safety |

**Balance method (how).** Two steps: find the CG, then make it sit at the hinge.

1. **Find the surface CG** by laying the surface on a knife-edge (a razor blade
   on a block) and moving it until it balances; mark the chordwise position.
2. **Compare to the hinge line.** If the CG is behind the hinge, add mass ahead
   of the hinge — either in a leading-edge pocket, a nose balance tube, or (best)
   a **balance horn** that projects forward of the hinge so less mass is needed.
3. **Recheck on the hinge jig.** With the surface free on its hinge it should
   hold its position, or droop only slightly nose-down — never nose-up.

**Balance jig (what it looks like).** A bench fixture that reproduces the hinge
line exactly and lets you see the balance:

| Part | Spec range | Purpose |
|---|---|---|
| Base plate | 200–250×120–150×10–15 mm, printed/MDF/aluminium | rigid datum |
| Hinge pillars ×2 | spacing = aircraft hinge spacing ±0.2 mm | reproduce the hinge |
| Miniature bearings | 623ZZ (3×10×4) or 624ZZ (4×13×5) | frictionless pivot |
| Hinge pin | Ø3–4 mm hardened steel or brass, straight ≤0.02 mm | the axis |
| Protractor / angle scale | printed −45…+45°, 1° marks | read deflection |
| Bubble level or digital angle finder | ±0.1–0.5° | set 0° |
| Knife-edge CG stand | razor blade on a 20×20 mm block | find CG |
| LE weight pocket + lead shot + epoxy | — | trim the balance |
| Balance-horn mould (print) | per surface | adds forward mass efficiently |

Procedure: clamp the surface in the hinge jig → level it → release it → it must
stay or fall slowly nose-down; if it falls tail-down, add LE/balance-horn mass
and repeat. Log the mass and CG offset per surface. Then repeat the whole check
after any paint, repair, or linkage change, because a few grams of paint on a
tail-heavy surface can flip the balance.

---

## 9c. Actuator-count minimisation and closing the yaw hole

The critic correctly caught a hole: §5b says vane yaw **fails 3.7–4.1× above
500 km/h**, yet §1 defines only **6 effectors (2 elevons + 4 vanes)** and the
fins in §5 have **no actuator**. So above ~400 km/h there is no yaw authority at
all. Here is the minimum-servo way to fix it.

**Maths first — how few vanes can still give 3-axis control?** A single-axis vane
deflects the jet tangentially; its reaction gives roll through the ring radius
and pitch/yaw through the axial arm. Three such vanes at 120° in a *common* exit
give the map `(F1,F2,F3) → (roll, pitch, yaw)` whose determinant is **2.598 ≠ 0**
→ **rank 3**. So **three single-axis vanes are enough for full pitch/yaw/roll**,
not four. (Radial-deflecting vanes are rank 2 — no roll — so use tangential.)

**Options, with servo count and cost:**

| Option | Elevons | Vanes | Rudder | Servos | Yaw below 250 | Yaw above 400 | Cost @₹600–900/servo |
|---|---:|---:|---:|---:|---|---|---|
| A — keep 4 vanes, add rudder | 2 | 4 | 1 | **7** | yes | yes | ₹4,200 – 6,300 |
| **B — 3 vanes (common exit) + rudder** | 2 | 3 | 1 | **6** | yes | yes | **₹3,600 – 5,400** |
| C — 4 vanes, no rudder | 2 | 4 | 0 | 6 | yes | **no** (authority hole) | ₹3,600 – 5,400 |
| D — 2 two-axis vanes | 2 | 2 (4 servos) | 1 | 7 | yes | yes | ₹4,200 – 6,300 |
| E — differential thrust only | 2 | 0 | 1 | 3 | **no** (yaw arm 0.043 m → needs 116 N ΔT) | no | ₹1,800 – 2,700 |

**Pick B.** It is the cheapest set that has full yaw authority at *all* speeds:
three tangential single-axis vanes in a merged exit give pitch/yaw/roll at low
speed, two elevons carry pitch/roll at speed, and one fin rudder covers
high-speed yaw. That is **6 servos instead of 7**, and one fewer vane also means
less exit blockage (2–4 % instead of 2–8 %) and less wiring.

**Cost minimisation rules (apply in order):**
1. Prefer **single-axis** servos over 2-axis (cheaper, stiffer, less backlash).
2. Use **3 vanes in a common exit** rather than 4 in two ducts (−1 servo, −1 linkage, −1 feedback channel).
3. **One rudder**, not two fin rudders (−1 servo).
4. Standard digital metal-gear micro servos; buy **one spare of each type**, not one per surface.
5. Share the actuator rail and feedback harness (already specified) — do not add per-surface regulators.
6. Only move to 7 servos if the common-exit merge costs more drag/loss than the servo saves.

**If the two ducts must stay separate** (no common exit), Option A (4 vanes +
rudder, 7 servos) is the fallback — accept the extra servo.

**What we are deliberately NOT adding.** The critic's other suggestions —
tip rudders, split drag rudders, spoilers — were all rejected on drag grounds
(§5c/§5e): drag rudders would add **+156 %** drag at 720 km/h for 5 N·m of yaw,
and tip rudders need **2.7×** the area with heavy roll coupling. No extra drag
device is worth a servo.

---

## 10. Test and verification plan

| Test | Passing range | Why | How | Where |
|---|---|---|---|---|
| Static deflection sweep | ±0.5 – ±25 – ±35° | authority map | rig, inclinometer | bench |
| Hinge-moment measurement | 0.05 – 0.3 – 1.0 N·m | servo sizing | torque sensor | bench |
| Flutter / ground-vibration | no divergence ≤ 720 km/h eq | safety | shaker / tunnel | test stand |
| Vane jet-load | 0.03 – 0.15 – 0.4 N·m | vane servo | benchtop EDF + load cell | bench |
| Actuator bandwidth | 2 – 5 – 10 Hz closed loop | control | sine sweep | bench |
| Jam / stale detection | fault ≤ 20 – 35 – 50 ms | fail-safe | injected fault | bench |
| Single-vane failure | reserve ≥1.1 – 1.3 – 2.0× | redundancy | disable one | sim + bench |
| In-flight effectiveness | meets reserve bands | real authority | instrumented flight | flight |

---

## 11. Control-surface register (quick reference)

```
ARCHITECTURE  2 elevons + (3 or 4) vector vanes + 1 rudder + 2 canted fins | 6-7 servos | ESC on CAN-FD
              effector set must match the master spec §10 before harness/CAM
AUTHORITY     crossover vane->elevon ~200-250 km/h | generous everywhere
              pitch 0-180: 3-5-8 rad/s2 | 500-720: 15-30-60 rad/s2 (rate-limited)
              roll  0-180: 3-6-10 rad/s2 | 500-720: 20-45-90 rad/s2 (rate-limited)
ELEVONS       span 100-150-200 mm | chord 25-40-60 mm (25-30% c)
              deflection +-12-25-35 deg | hinge 25-30-40% c | gap 0.2-0.5-1.0 mm
              mass balance 0-30-60% | flutter >=1.2-1.4-2.0x Vd | hinge moment 0.05-0.20-0.45 Nm
VANES         4x 25x30-30x40-40x55 mm | ring radius 38-44-50 mm | axial arm 0.22-0.27-0.32 m
              deflection +-15-22-35 deg | blockage 2-4-8% | hinge 0.03-0.09-0.25 Nm
FINS          2 | height 50-70-100 mm | chord 60-90-130 mm | cant 15-30-45 deg
              Cnbeta 0.02-0.06-0.12 /rad | yaw moment 0.5-2-5 Nm | dutch-roll zeta 0.05-0.15-0.35
ACTUATION     6 digital metal-gear servos | rail 6.0-7.4-8.4 V, 3-9-15 A
              torque 2-5-20 kg.cm | speed 0.06-0.12-0.25 s/60deg | backlash <=0.5-1.0-2.0 deg
              command 200-400-800 Hz (board) | effective servo bandwidth 2-5-10 Hz | latency 5-15-30 ms | feedback 100-200-500 Hz
ALLOCATION    6->3 mixer | schedule breakpoint 150-225-350 km/h | trim +-5-10-20%
              high-speed deflection limit 0.01-0.05-0.10x | rate limit 200-350-600 deg/s
FAILURE       one-vane-failed reserve >=1.1-1.3-2.0x | stale 10-20-35 ms | rail bulk 500-2000-5000 uF
```

---

*Same convention as the master spec: every value is a band with a nominal and a
preferred direction. The authority figures are screening estimates from the
Phase-15 model and must be replaced by bench and flight measurements before the
bands are narrowed.*
