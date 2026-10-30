#!/usr/bin/env python3
"""Source-pinned preliminary wing load-demand screen; not a structural analysis.

Calculates steady symmetric wing-root bending demand from the Phase-15
candidate mass/planform and reports the section modulus required over the
specification's strength-factor range. Composite allowables and the built
section are deliberately not fabricated, so the result is a blocked gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


PHASE = Path(__file__).resolve().parents[1]
REPO = PHASE.parents[1]
FSI_RECEIPT = PHASE / "fsi" / "results" / "attempts" / "20260930T134329Z" / "worker_output" / "wing_t36mm_receipt.json"

# These immutable digests bind the values and claims below to the inspected
# design, model, deck, solver receipt, failure log, and materials audit. If a
# source changes, report generation must stop until a reviewer explicitly
# revalidates the evidence and updates this allowlist.
PINNED_SOURCE_SHA256 = {
    "highspeed_edf/design/PHASE15_DESIGN_SPEC.md": "d63eb7f3ae8b23476d8077ebb739165a50afba152972269690ccf834446aa5aa",
    "highspeed_edf/phase15/optimization/phase15_aero_multiphysics_screen.py": "1bb1f7818bf348d1cd3c72c82f3a6644a85af7b709cf4921578b43a30bc20e00",
    "highspeed_edf/phase15/optimization/phase15_fsi_casegen.py": "f2ea9705c2ea10d5a5ce5145df32944f0c80fbeba35fb4a70961dfea7c36acce",
    "highspeed_edf/phase15/fsi/cases/wing_t36mm/solid/wing.inp": "ae81cd06d2a976b1a1c4d55ec3c8505a01c7a0ca0b588d041e98427a9f7dd390",
    "highspeed_edf/phase15/fsi/results/attempts/20260930T134329Z/worker_output/wing_t36mm_receipt.json": "0a6f87e6c8a3ecef48f683d83e472162059d41c6f4f396453989a91f435c02d4",
    "highspeed_edf/phase15/fsi/results/attempts/20260930T134329Z/worker_output/wing_t36mm/rhoPimpleFoam.log": "8123486174e8c3c11665850ca3cb7cbc32b873aa7b720337c719af996ef74fca",
    "highspeed_edf/phase15/reports/issue4_material_matrix_stockfix_ff670.md": "7fe8cd706c308bce060e17d576bf69d46355e1ed61716155facfd269ff19db5c",
    "highspeed_edf/phase15/reports/issue4_material_matrix_stockfix_ff670.json": "1ab93043326b013fcee32ed75b79de2018ea752ec9e230dce430b5c86db4c012",
}

# Candidate values are copied from phase15_aero_multiphysics_screen.py and
# checked against PHASE15_DESIGN_SPEC.md. They are design inputs, not measured
# aircraft properties. The scenario n values are sensitivity points only.
MASS_KG = 6.541
WING_AREA_M2 = 0.190
FULL_SPAN_M = 0.520
ROOT_CHORD_M = 0.425
TIP_CHORD_M = 0.305
RHO_3KM_KG_M3 = 0.909
SPEED_M_S = 200.0
GRAVITY_M_S2 = 9.80665
LOAD_FACTORS = (1.0, 2.0, 3.0)
SPEC_SAFETY_FACTORS = (2.0, 3.0, 4.5)
# Illustrative strengths are not used as material properties. They make the
# required-section-modulus sensitivity legible while the actual allowable is
# unavailable; report labels all values explicitly as hypothetical.
ILLUSTRATIVE_ALLOWABLES_PA = (100e6, 250e6, 500e6)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SourceIntegrityError(RuntimeError):
    """Raised when report inputs no longer match the reviewed snapshots."""


def verify_source(path: Path, relative_path: str, expected_sha256: str) -> dict[str, str]:
    if not path.is_file():
        raise SourceIntegrityError(f"pinned source is missing: {relative_path}")
    actual_sha256 = sha256(path)
    if actual_sha256 != expected_sha256:
        raise SourceIntegrityError(
            f"pinned source drift: {relative_path}: expected {expected_sha256}, got {actual_sha256}; "
            "review the source and explicitly update the pin before regenerating this report"
        )
    return {"path": relative_path, "sha256": expected_sha256}


def pinned_sources() -> list[dict[str, str]]:
    sources = []
    for relative_path, expected_sha256 in PINNED_SOURCE_SHA256.items():
        path = REPO / relative_path
        sources.append(verify_source(path, relative_path, expected_sha256))
    return sources


def calculate() -> dict[str, Any]:
    sources = pinned_sources()
    half_span = FULL_SPAN_M / 2.0
    taper = TIP_CHORD_M / ROOT_CHORD_M
    # Constant sectional lift coefficient over a linearly tapered wing gives
    # lift proportional to local chord. Its centroid follows from integrating
    # y*c(y) over the half-span.
    lift_centroid_m = half_span * (ROOT_CHORD_M + 2.0 * TIP_CHORD_M) / (
        3.0 * (ROOT_CHORD_M + TIP_CHORD_M)
    )
    q_pa = 0.5 * RHO_3KM_KG_M3 * SPEED_M_S**2
    weight_n = MASS_KG * GRAVITY_M_S2
    cl_1g = weight_n / (q_pa * WING_AREA_M2)
    rows = []
    for n in LOAD_FACTORS:
        total_lift_n = n * weight_n
        half_wing_lift_n = total_lift_n / 2.0
        root_moment_nm = half_wing_lift_n * lift_centroid_m
        required = []
        for fos in SPEC_SAFETY_FACTORS:
            for allowable in ILLUSTRATIVE_ALLOWABLES_PA:
                required.append({
                    "specSafetyFactor": fos,
                    "hypotheticalAllowableMPa": allowable / 1e6,
                    "requiredSectionModulusMm3": root_moment_nm * fos / allowable * 1e9,
                    "status": "ILLUSTRATIVE_ONLY; no sourced laminate allowable",
                })
        rows.append({
            "symmetricLoadFactorG": n,
            "totalWingLiftN": total_lift_n,
            "halfWingLiftN": half_wing_lift_n,
            "liftCentroidOutboardOfRootM": lift_centroid_m,
            "rootBendingMomentNm": root_moment_nm,
            "requiredSectionModulusSensitivity": required,
        })
    return {
        "title": "Phase-15 preliminary wing load-demand screen",
        "status": "BLOCKED: preliminary load demand only; no structural pass/fail",
        "evidenceClass": "reproducible analytical load screen, not FEA and not structural validation",
        "sourceIntegrityPolicy": "fixed SHA-256 allowlist; generation raises SourceIntegrityError if any pinned source is missing or differs, and changing a reviewed digest requires an explicit reviewer edit to the allowlist",
        "nativeSolverAvailability": {
            name: shutil.which(name) for name in ("gmsh", "ccx", "CalculiX", "rhoPimpleFoam", "gmshToFoam")
        },
        "existingFsiEvidence": {
            "attemptReceipt": str(FSI_RECEIPT.relative_to(REPO)),
            "attemptStatus": "coupled_solver_failed_or_not_converged; fluid return code 1, solid return code -6; no tip-displacement result",
            "fluidDiagnostic": "FOAM FATAL IO ERROR: Entry 'div(meshPhi,p)' not found in dictionary system/fvSchemes/divSchemes",
            "solidDiagnostic": "preCICE received EOF from the fluid participant after its fatal exit; no valid coupled load/displacement history",
            "equivalentSolidMaterial": "existing deck uses isotropic E=10 GPa, nu=0.30, density=150 kg/m^3; a screening seed, not a sourced hand-laid laminate",
        },
        "materialsAuditEvidence": {
            "report": "highspeed_edf/phase15/reports/issue4_material_matrix_stockfix_ff670.md",
            "machineReadableReport": "highspeed_edf/phase15/reports/issue4_material_matrix_stockfix_ff670.json",
            "finding": "inventory remains blocked because supplier/product identity, laminate layup, coupon allowables, temperature/adhesive qualification, measured masses, and manufacturing traveler are absent",
        },
        "sources": sources,
        "inputs": {
            "candidateAircraftMassKg": MASS_KG,
            "wingPlanformAreaM2": WING_AREA_M2,
            "fullSpanM": FULL_SPAN_M,
            "rootChordM": ROOT_CHORD_M,
            "tipChordM": TIP_CHORD_M,
            "taperRatio": taper,
            "airDensityKgM3": RHO_3KM_KG_M3,
            "flightSpeedMps": SPEED_M_S,
            "gravityMps2": GRAVITY_M_S2,
            "dynamicPressurePa": q_pa,
            "requiredCLAt1g": cl_1g,
            "loadFactorCasesG": list(LOAD_FACTORS),
            "specSafetyFactors": list(SPEC_SAFETY_FACTORS),
            "specSafetyFactorSource": "PHASE15_DESIGN_SPEC.md §9: Wing structure FOS 2.0 / 3.0 / 4.5; this is applied as a factor on the illustrative load demand, not inferred as an aircraft maneuver envelope.",
        },
        "method": {
            "model": "steady symmetric lift; each half-wing carries half the aircraft lift",
            "spanwiseLoad": "lift per unit span proportional to linearly varying chord (constant sectional CL); centroid integrated analytically",
            "rootMoment": "(n * m * g / 2) * (b/2) * (c_root + 2*c_tip) / (3*(c_root+c_tip))",
            "sectionModulusSensitivity": "Z_required = root moment * specification safety factor / hypothetical allowable",
            "excluded": ["gust and maneuver envelope", "aerodynamic pressure map / CFD loads", "wing self-weight and inertia relief", "sweep-axis torsion", "skin/core/spar/joint load paths", "buckling, shear, fatigue, impact and flutter"],
        },
        "loadCases": rows,
        "unavailablePhysicalInputs": [
            "as-built wing CAD including carbon skins, spar/web, core and joints",
            "hand layup ply orientations, count, fiber volume fraction, cured thickness and resin system",
            "coupon-derived tension/compression/shear allowables and hot/wet/environment knockdowns",
            "validated 3D CFD pressure field or defined gust/maneuver design envelope",
            "measured aircraft mass distribution and wing mass for inertia relief",
        ],
        "gate": "BLOCKED: because section properties and material allowables are absent, no actual stress, reserve factor, displacement, or structural acceptance can be calculated. Hypothetical allowable rows are sensitivity arithmetic only.",
    }


def markdown(result: dict[str, Any]) -> str:
    inp = result["inputs"]
    lines = [
        "# Phase-15 preliminary wing load-demand screen",
        "",
        "**Status: BLOCKED.** This is an analytical load-demand calculation, not FEA, not a stress result, and not structural validation.",
        "",
        "Provenance is fail-closed: report generation checks every listed SHA-256 against a fixed allowlist; changed or missing inputs stop generation until the reviewed pin is deliberately updated.",
        "",
        f"Candidate inputs: {inp['candidateAircraftMassKg']:.3f} kg, {inp['wingPlanformAreaM2']:.3f} m² wing area, {inp['fullSpanM']:.3f} m span, {inp['rootChordM']:.3f}/{inp['tipChordM']:.3f} m root/tip chord, 200 m/s at 3 km ISA density {inp['airDensityKgM3']:.3f} kg/m³. Dynamic pressure is {inp['dynamicPressurePa'] / 1000:.2f} kPa; 1g lift requires CL={inp['requiredCLAt1g']:.4f}.",
        "",
        "The model assigns half the symmetric aircraft lift to each half-wing and distributes it in proportion to linearly tapered chord. This places the half-wing lift centroid at {:.4f} m outboard of the root.".format(result["loadCases"][0]["liftCentroidOutboardOfRootM"]),
        "",
        "| Sensitivity load | Lift per half-wing | Root bending moment per side |",
        "|---:|---:|---:|",
    ]
    for row in result["loadCases"]:
        lines.append(f"| {row['symmetricLoadFactorG']:.1f} g | {row['halfWingLiftN']:.2f} N | {row['rootBendingMomentNm']:.3f} N·m |")
    lines += [
        "",
        "The load-factor cases 1g, 2g, and 3g are sensitivity points; the source files do not define an aircraft maneuver/gust envelope. The design specification lists wing structure safety-factor targets of 2.0/3.0/4.5. Applying those multipliers to the root moment and dividing by hypothetical 100/250/500 MPa allowables gives section-modulus demand sensitivities, but the allowables are intentionally not treated as carbon laminate properties. See the JSON output for values.",
        "",
        "## Blocking evidence",
        "",
        "The materials audit says the supplier/product identity, laminate layup, coupon allowables, temperature/adhesive qualification, measured masses, and manufacturing traveler are absent. The existing FSI case is an outboard wing-sector mesh with an equivalent isotropic 10 GPa / 150 kg/m³ seed. In the recorded 2026-09-30 attempt, OpenFOAM exited on missing `div(meshPhi,p)` in `fvSchemes`; preCICE/CalculiX then lost its peer, and the receipt contains no tip-displacement result. Native solver availability at report generation: {}. No stress result is available.".format(
            ", ".join(f"{name}={'available' if path else 'unavailable'}" for name, path in result["nativeSolverAvailability"].items())
        ),
        "",
        "Unavailable inputs:",
        "",
    ]
    lines.extend(f"- {item}." for item in result["unavailablePhysicalInputs"])
    lines += ["", "Source SHA-256 pins:", ""]
    lines.extend(f"- `{source['path']}`: `{source['sha256']}`" for source in result["sources"])
    lines += ["", "This report provides no actual stress, reserve factor, deformation, failure mode, or structural acceptance decision.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=PHASE / "fsi" / "reports" / "phase15_wing_load_stress_gate.json")
    parser.add_argument("--markdown", type=Path, default=PHASE / "fsi" / "reports" / "phase15_wing_load_stress_gate.md")
    args = parser.parse_args()
    result = calculate()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"status": result["status"], "qPa": result["inputs"]["dynamicPressurePa"],
                      "rootMoment1gNm": result["loadCases"][0]["rootBendingMomentNm"],
                      "rootMoment3gNm": result["loadCases"][2]["rootBendingMomentNm"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
