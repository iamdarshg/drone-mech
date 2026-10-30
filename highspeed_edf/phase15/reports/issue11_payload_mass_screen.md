# Issue 11 camera payload mass sensitivity screen

**Partial issue #11 screen; installation remains BLOCKED.** This screen substitutes an online camera-unit catalog mass into the Phase-15 point-mass bookkeeping and shows the resulting modeled mass and CG. It does not establish a camera bay, fit, mount, installation, image quality, electrical integration, or flight performance.

The candidate values are from the DJI Action 2 User Manual, version 1.0 (English). The manufacturer lists the Camera Unit at 56 g and 39 × 39 × 22.3 mm (Specifications, printed page 20; PDF page 21). The original PDF is [available from DJI](https://dl.djicdn.com/downloads/DJI_Action_2/20211028UM/DJI_Action_2_User_Manual_V1.0_EN-11.pdf). A retrieved copy is committed at `highspeed_edf/phase15/configs/source_snapshots/DJI_Action_2_User_Manual_V1.0_EN-11.pdf`; retrieved 2026-10-30; SHA-256 `c71167c3b9ef8dfbe571aa6ad000c718ef9029011686150f895bc62e620b5586`. The CLI verifies this snapshot hash before calculation. No unit was purchased or measured.

The generator and `mass_cg.csv` are pinned to drone-mech revision `236056ff6e5036eaf5bed27b8ba361f84b1bb090`; their SHA-256 values are also enforced. All scenarios keep camera and supplemental mass at the existing analyst-selected point `(0, 0, −320) mm`, so the calculation exposes sensitivity to payload mass while retaining that unvalidated location assumption.

| Scenario | Supplemental mass assumption | Payload total | Modeled total mass | Modeled CG Z | CG Z change vs baseline |
|---|---:|---:|---:|---:|---:|
| Camera unit only | 0 g | 56 g | 5.597 kg | +49.34 mm | +53.31 mm |
| Camera plus provisional accessory allowance | 250 g | 306 g | 5.847 kg | +33.55 mm | +37.51 mm |
| Camera plus mass to preserve legacy payload total | 944 g | 1,000 g | 6.541 kg | −3.96 mm | ~0 mm |

For the camera-only case, **+49.34 mm is the resulting CG Z** and **+53.31 mm is its shift from the baseline −3.96 mm**. The 250 g and 944 g values are explicit analyst-selected sensitivities, not sourced component masses or recommendations. The 944 g case is only an accounting bound that preserves the legacy 1 kg payload total.

Issue #11 remains partially addressed. Although the camera dimensions are source-pinned, no defined payload bay envelope or mounting datum exists to compare against them. Mount, wiring, power, thermal, vibration, hatch, and service envelopes remain absent. The payload still cannot be called installed or fit-checked. This screen models no radar module or radar performance.

Run:

```bash
python -m highspeed_edf.verification.payload_mass_screen --source-root .
python -m unittest highspeed_edf.verification.test_payload_mass_screen -v
```
