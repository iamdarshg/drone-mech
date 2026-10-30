# Issue 11 camera payload mass sensitivity screen

**Status: screening only; installation remains blocked.** This report replaces the Phase-15 generic 1.0 kg point-mass payload with an online camera-unit candidate and explicitly carries supplemental-mass scenarios. It is a numerical mass/CG sensitivity using the pinned project mass table; it makes no physical fit, mount, imaging, electrical, or flight claim.

The DJI Action 2 Camera Unit product specification lists 56 g and a 39 × 39 × 22.3 mm envelope ([manufacturer specifications](https://www.dji.com/action-2/specs)). These are catalog values. No component was purchased, measured, or installed. The baseline generator and `mass_cg.csv` are pinned to repository revision `236056ff6e5036eaf5bed27b8ba361f84b1bb090` and their SHA-256 values are enforced by the CLI. The complete input manifest is `highspeed_edf/phase15/configs/payload_mass_screen_sources.json`.

| Scenario | Supplemental mass assumption | Payload total | Total aircraft model mass | CG Z | CG Z change vs baseline |
|---|---:|---:|---:|---:|---:|
| Camera unit only | 0 g | 56 g | 5.597 kg | +49.34 mm | +53.31 mm |
| Camera plus provisional accessory allowance | 250 g | 306 g | 5.847 kg | +33.55 mm | +37.51 mm |
| Camera plus mass to preserve legacy payload total | 944 g | 1,000 g | 6.541 kg | −3.96 mm | ~0 mm |

All scenarios retain the legacy analyst-selected payload CG at `(0, 0, −320) mm`; that location has not been validated as a camera mounting point. The arithmetic shows that adopting a 56 g catalog camera while removing the generic 1 kg placeholder changes modeled mass and CG materially unless a substantial accessory or inert mass is retained. The 944 g case is an accounting bound, not a recommendation to carry ballast.

The source model still lacks a defined payload bay/envelope, mounting datum, mounts, wiring, power, thermal allowance, vibration isolation, hatch, and service access. The sourced camera dimensions therefore cannot be checked against available clearance. Issue #11 remains open. Radar electronics and performance are outside this screen; no radar module or active sensor is modeled.

Run:

```bash
python -m highspeed_edf.verification.payload_mass_screen --source-root .
python -m unittest highspeed_edf.verification.test_payload_mass_screen -v
```
