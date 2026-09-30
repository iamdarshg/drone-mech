# Design decisions — rule applied: net cost > ₹5k is discarded

Suppliers frozen to **robu.in and amazon.in only**. Your rule: **any option
whose net wallet effect exceeds ₹5,000 is discarded automatically.** Below, each
decision shows the options, the cost, whether it survives the rule, and the plain
reason.

---

## D1 — Assumed drag (CdA)

**What it means:** CdA is the aircraft's drag "size"; bigger = more power burned.
We can't measure it until the shell exists, so we must guess a number to design
to.

| Option | Cost | Survives? | Meaning |
|---|---|---|---|
| A — assume slippery (0.0007–0.0008 m²) | **₹0** | **YES** | Only assumption under which 720 km/h works on a ₹12k pack |
| B — assume draggy (0.0015–0.0030 m²) | +₹10–30k | **DISCARDED** | Safer sizing, but a bigger pack/motors |
| Measure it (tunnel/CFD polar) | +₹5–15k | **DISCARDED** | Insurance that removes the guess |

**Automatic choice: A.** You are designing to the optimistic drag assumption
because you cannot afford the insurance. Consequence, stated plainly: **if the
real aircraft is fatter than assumed, it will not reach 720 km/h and the fix is a
₹10–30k re-power.** This is the single biggest risk you are accepting.

---

## D2 — Frontal-area target

**What it means:** how fat the aircraft is seen head-on.

| Option | Cost | Survives? | Meaning |
|---|---|---|---|
| A — 240–300 cm² | **₹0** | **YES** | What the current twin-duct + battery + wing layout actually is |
| B — 110 cm² | +₹20–50k | **DISCARDED** | Requires merging to one duct: new CAD, moulds, repackaging |

**Automatic choice: A.**

---

## D3 — Steering: 3 or 4 vanes in the jet

**What it means:** paddles in the exhaust that steer the aircraft when wings
can't (below ~250 km/h). 3 vs 4 changes servos and whether the ducts merge.

| Option | Cost | Survives? | Meaning |
|---|---|---|---|
| A — 3 vanes + merged single nozzle + rudder (6 servos) | +₹5–15k | **DISCARDED** | New merged-nozzle CAD/prints costs more than the servo it saves |
| B — 4 vanes (2/duct) + rudder (7 servos) | **+₹0.6–0.9k** | **YES** | Keeps the current separate-duct layout, one extra servo |

**Automatic choice: B.** ₹600–900 for the extra servo vs ₹5–15k to redesign the
exhaust.

---

## D4 — Burst current vs the 360 A bus

**What it means:** the ESC can push extra current briefly; your busbar/fuses are
rated for the steady 360 A.

| Option | Cost | Survives? | Meaning |
|---|---|---|---|
| A — keep 360 A bus, bursts within 360 A total | **₹0** | **YES** | Lose the ESC's 90–105 A/channel burst headline |
| B — up-rate busbar/fuses/wiring to 450–630 A | +₹25–55k | **DISCARDED** | Needs a battery no sub-₹12k pack can supply |

**Automatic choice: A.**

---

## D5 — Maximum take-off weight (and future long-range)

**What it means:** heavier = more thrust needed; the long-range pack is heavy.

| Option | Cost | Survives? | Meaning |
|---|---|---|---|
| A — keep 8.5 kg ceiling | **₹0** | **YES** | Sprint aircraft only; future pack ≤ ~1.1 kg |
| B — raise ceiling for an endurance variant | +₹10–25k | **DISCARDED** | Big gear/structure + motor re-size for TWR |

**Automatic choice: A.** Long-range/endurance is **off the table** for now — it
is a future, funded-later programme, not part of this build.

---

## D6 — Shell material (thermal)

**What it means:** ducts sit near 90–110 °C motors; PLA softens ~55 °C.

| Option | Cost | Survives? | Meaning |
|---|---|---|---|
| A — all PLA + 45 °C cap | **₹0** | YES | Cheap but needs shielding; thermal failure risk |
| B — high-temp (PEI/PEEK/metal) **hot side only** | **+₹2–5k** | **YES (≤5k)** | Duct + motor bay survive 150–250 °C; cold body stays PLA |

**Automatic choice: B.** At ≤₹5k this is inside the rule and removes the biggest
thermal failure mode for the price of the shielding you'd buy anyway.

---

## D7 — Inlet quality designed to

**What it means:** inlet "recovery" is how much of the incoming air's energy is
preserved. 0.97 vs 0.99 swings cruise power from ~10.5 kW to ~3.8 kW.

| Option | Cost | Survives? | Meaning |
|---|---|---|---|
| A — design to 0.99 (excellent inlet) | **₹0** | **YES** | Keeps 720 km/h and 116 km alive if true |
| B — design to 0.97 (mediocre inlet) | +₹10–30k | **DISCARDED** | Bigger battery/motors, lower claims |
| Bench-duct rig to find out | +₹5–15k | **DISCARDED** | The insurance |

**Automatic choice: A.** Same trap as D1: you are assuming an excellent inlet
because the rig is unaffordable. **If the real inlet is 0.97, cruise power roughly
doubles and range roughly halves.**

---

## Final automatic picks (from your rule)

| Decision | Pick | Cost | Notes |
|---|---|---|---|
| D1 CdA | **assume 0.0007–0.0008 m²** | ₹0 | Risk accepted: may not hit 720 km/h |
| D2 frontal area | **240–300 cm²** | ₹0 | Matches the layout |
| D3 vanes | **4 + rudder (7 servos)** | ₹0.6–0.9k | Keeps separate ducts |
| D4 burst | **keep 360 A bus** | ₹0 | |
| D5 mass | **8.5 kg, sprint only** | ₹0 | Endurance deferred |
| D6 shell | **high-temp hot side** | ₹2–5k | Inside the rule |
| D7 inlet | **design to 0.99** | ₹0 | Risk accepted: may halve range |

**Total decision spend: ≈₹3–6k.**

**The two risks you accepted by discarding the insurance:** an optimistic CdA
(D1) and an optimistic inlet (D7). Together they decide whether the aircraft
reaches 720 km/h and 116 km. If either is wrong, the correction costs ₹10–30k
*after* you have built — which is why they are normally the first things funded.
Your rule makes them explicit accepted risks rather than paid-down ones.

---

## Separate blocker — the motor cannot be bought today

Restricted to robu.in and amazon.in:

- **robu.in:** every 4-pole (2 pole-pair) inrunner is **out of stock** —
  Rocket 4068 1400/1700/1900KV, 4076 1550KV, 3660 2350KV. The known Rocket 3670
  variants have no retrievable live price/stock page (robu search is CAPTCHA-gated).
- **amazon.in:** cheapest **in-stock** 4-pole is **₹5,279–5,367** (CALANDIS 3660
  3800KV / GoolRC S3660 3300KV) — **₹779–867 over the ₹4,500 cap** — and both need
  a ~3.6–4.1× rewind (resistance ×13–17, poor).

**RESOLVED 2026-09-29:** robu.in has the **Rocket 3670 4-pole 1550 KV, ₹3,409,
IN STOCK**. Buy 6 = ₹20,454; rewind to ~925 KV (×1.68 turns, R ×2.81); + rewind
materials ₹2.7–10.7k. Six-motor cap raised by you to **₹27,600** (6 × ₹4,600).
Typical rewind gives ₹27,154 — inside, but only just; cheap rewind gives ₹23,154.

---

## Two items that still need your call (from the final critic)

**F-05 — the 7th servo has no PWM channel.** D3 chose 4 vanes + 1 rudder = **7
servos**, but the frozen drone-arm contract provides **6 PWM channels** (the ESC
is on CAN-FD, freeing exactly six). Options, all requiring a board-side change:
- (a) **Add a 7th PWM channel** to the flight board (layout + firmware + issue #18
  update). Cost: board respin ~₹3–8k and schedule.
- (b) **Drive one effector over CAN** with a small CAN servo/actuator. Cost:
  ₹2–5k per such actuator, plus firmware.
- (c) **Drop to 6 effectors** by using only 3 vanes (needs the merged exit that
  D3 rejected at ₹5–15k) — i.e. re-opens D3.

**F-10 — if the rudder fails, there is no high-speed yaw.** The rudder is the
only yaw authority above ~400 km/h (the vanes fail 2.9× at 720 km/h). A single
rudder servo is therefore a single-point failure in yaw. Options:
- (a) **Two rudders on both fins**, each independently actuated. Cost: +₹0.6–0.9k
  and one more PWM channel (compounds F-05).
- (b) **Accept the single rudder** and declare a yaw-degraded mode after rudder
  loss. Cost: ₹0, risk accepted.
- (c) **Make the rudder fail-free** (redundant servo on the same horn / spring to
  neutral). Cost: +₹0.6k, partial mitigation only.
