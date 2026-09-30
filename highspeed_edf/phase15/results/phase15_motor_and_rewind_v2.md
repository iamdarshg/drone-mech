# Donor motor hunt v2 (₹4,500/unit) and rewind material costs

Captured 2026-09-29. Research only; nothing purchased. Suppliers: robu.in
(primary), amazon.in (secondary), plus Indian hobby shops where they beat both.

## 1. Hard constraints applied

- Price ≤ **₹4,500** per motor (rewind cost counted separately below).
- **2 pole pairs (4-pole) only** — 7 pole pairs needs 287 k eRPM at 41 krpm, over
  the 200 k limit. 4-pole = 82 k eRPM. This excludes all 12N14P outrunners.
- Mass ≤ ~300 g, stator sized for ≥1.8 kW after rewind.
- Rewind turns ratio = stock_Kv / 925; resistance factor = ratio². **A stock Kv
  at or below 925 is far better** (rewind up = fewer turns = less resistance).

## 1b. CONFIRMED BUY (in stock today, robu.in only, ≤ ₹4,600)

**robu.in — Surpass Hobby "Rocket" 3670 4-POLE, 5.0 mm shaft, 1550 KV — ₹3,409,
IN STOCK.** Second option 1850 KV, same ₹3,409, in stock.

- 2 pole pairs (4-pole, stated by robu) → **82 k eRPM at 41 krpm**, inside the
  200 k limit.
- 36×70 can, ~270–276 g (OEM spec), OEM ~1600 W (≥1.5 kW requirement).
- Rewind ratio to 925 KV: **1550 KV → ×1.68 turns (R ×2.81)**; the 1850 KV is
  worse (×2.0, R ×4.0). **Buy the 1550 KV.**
- robu does not publish mass or wattage; both are the OEM spec for this exact
  12-slot 3670 4-pole can. Weigh on arrival.

**Six motors: 6 × ₹3,409 = ₹20,454** — inside the ₹24,000 six-motor cap.
Plus rewind materials ₹2,700–10,700 → **₹23,154–31,154** all-in.

Amazon.in has nothing: every genuine 36/40 mm 4-pole inrunner is > ₹4,600
(cheapest ~₹5,367).

---

## 2. Donor shortlist

| # | Motor | Supplier | ₹ | Stock | pp | Stock Kv | g | Can | Ratio to 925 | R factor | Verdict |
|---|---|---|---:|---|---:|---:|---:|---|---:|---:|---|
| 1 | Surpass Hobby Rocket 3670 1200KV 4-pole | Ingenium Drives | 3,500 | yes | 2 | 1200 | ~276 | 36×70 | 1.30 | 1.68 | **BEST** |
| 1b | same | roboverse.in | 3,749 | yes (9) | 2 | 1200 | ~276 | 36×70 | 1.30 | 1.68 | buy |
| 1c | same | ElectroPi | 3,399 (+GST) | yes (2) | 2 | 1200 | ~276 | 36×70 | 1.30 | 1.68 | buy |
| 1d | same | robu.in | listed (403 to bots) | listed | 2 | 1200 | ~276 | 36×70 | 1.30 | 1.68 | verify |
| 2 | Surpass Hobby 3660 1400KV 4-pole | roboverse.in | 2,349 | yes | 2 | 1400 | ~230 | 36×60 | 1.51 | 2.29 | **VALUE** |
| 3 | Surpass Hobby 4068 1400KV 4-pole | roboverse.in | 3,999 | yes | 2 | 1400 | 300–350 | 40×68 | 1.51 | 2.29 | **POWER** (weigh first) |
| 4 | Robu Surpass Rocket 4068 1700KV | robu.in | 4,462 | **OOS** | 2 | 1700 | 300–350 | 40×68 | 1.84 | 3.38 | watch |
| 5 | Robu Surpass Rocket 4076 1550KV | robu.in | listed | listed | 2 | 1550 | ~400 | 40×76 | 1.68 | 2.81 | marginal (mass) |
| — | Surpass Rocket 4292 V2 1030KV | roboverse | 8,499 | yes | 2 | 1030 | ~620 | 42×92 | 1.11 | 1.24 | over budget/mass |
| — | Amazon 3660/3670 4-pole clones | amazon.in | 5,367–12,633 | yes | 2 | 1200–3300 | 230–300 | — | ≥1.30 | ≥1.68 | **all over ₹4,500** |

**Best donor: Surpass Hobby Rocket 3670 1200KV, 4-pole inrunner — ₹3,500
(Ingenium Drives) or ₹3,749 (roboverse).** Lowest stock Kv available in budget →
least rewinding (×1.30 turns, ×1.68 resistance), 36×70 can sized for ~1.5–1.6 kW
stock and 2 kW+ after rewind, ~276 g, 4-pole = 82 k eRPM at 41 krpm, 50–60 krpm
bearings. Stock is ~4–6S, so a full rewind with new insulation is required for
12S — which is the plan.

**Note:** **no 4-pole motor with stock Kv 500–1000 exists in India ≤₹4,500.** The
practical floor is 1200 Kv. Amazon.in returned only over-budget clone listings;
robu.in carries the Surpass 4-pole family but most variants are out of stock.

## 3. Rewind material costs (six motors, conformal coat excluded — already owned)

| Item | Cheap | Typical | Good |
|---|---:|---:|---:|
| Magnet wire (≈60 g/motor, AWG 20–24) | ₹1,650 | ₹1,999 | ₹2,800 |
| Slot liner / Nomex / Kapton | ₹150 | ₹400 | ₹1,200 |
| Varnish / impregnating resin | ₹170 | ₹1,645 | ₹2,000 |
| Thermistors (10 k NTC, 6–12) | ₹54 | ₹90 | ₹440 |
| Fibreglass sleeve + lead wire | ₹200 | ₹500 | ₹850 |
| Kapton tape | ₹100 | ₹200 | ₹390 |
| Misc (solder/flux/lacing) | ₹400 | ₹700 | ₹1,000 |
| Bearing retainer | ₹0 | ₹1,069 | ₹1,976 |
| **TOTAL (six motors)** | **≈₹2,700** | **≈₹6,700** | **≈₹10,700** |

**Single 100 g spool of the relevant magnet wire ≈ ₹330–450 (typ. ₹350)** — the
dominant per-motor consumable at ~₹210–280/motor. Sources: Royal Components
(26 SWG ₹358.55 / 28 SWG ₹333.35 per 100 g), Amazon.in 500 g spools ~₹900–1,300,
Wiremart 1 kg ~₹1,999.

One-off (tools/reusable) vs per-motor: varnish tin, Kapton roll, Nomex sheet,
solder, bearing retainer, thermistor pack are one-off; magnet wire, liner pieces,
thermistors, lead wire are per-motor.

## 4. Six-motor cost with the chosen donor

| Case | Motor ×6 | Rewind | Total | vs ₹24,000 cap |
|---|---:|---:|---:|---|
| Cheap | 6 × ₹2,349 (3660) = ₹14,094 | ₹2,700 | ₹16,794 | under |
| **Typical (3670 1200KV)** | 6 × ₹3,500 = ₹21,000 | ₹6,700 | **₹27,700** | ₹3,700 over |
| Typical (3660 1400KV) | 6 × ₹2,349 = ₹14,094 | ₹6,700 | ₹20,794 | under |
| Good | 6 × ₹3,500 = ₹21,000 | ₹10,700 | ₹31,700 | over |

The **₹24,000 six-motor cap is met only by the lighter 3660-class donor** with
typical rewind consumables, or by the 3670 with cheap rewind.
