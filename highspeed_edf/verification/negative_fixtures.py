"""Executable mutation fixtures exercising the production native adapters.

Run with the pinned CadQuery interpreter. Mutations live in temporary files.
"""
from __future__ import annotations

import csv
import importlib.metadata
import json
import sys
import tempfile
from pathlib import Path

import cadquery as cq
from .native_adapters import (
    battery_bay_fit, board_placeholder_comparison, boolean_interference,
    import_all_step, import_kicad_board, import_step, motor_bbox_collision,
    recalculate_mass_cg, validate_cad_datum, validate_pcb_sha,
)

MECH = Path(__file__).resolve().parents[2]
HIGH_SPEED = MECH / "highspeed_edf"
ARM = MECH.parent / "drone-arm"
GEOMETRY = HIGH_SPEED / "deliverables/phase15_geometry"
GENERATOR = HIGH_SPEED / "phase15/optimization/phase15_generate_geometry.py"
MASS_CSV = GEOMETRY / "reports/mass_cg.csv"


def _motor(path: Path, length: float, z: float):
    cq.exporters.export(cq.Workplane("XY").box(42, 42, length).translate((0, 0, z)).val(), str(path))
    return import_step(path)


def execute() -> list[dict]:
    rows=[]
    def expect(fixture, check_id, actual, expected):
        rows.append({"fixture":fixture,"check_id":check_id,"actual":actual,"expected":expected,"detected":actual==expected})
    with tempfile.TemporaryDirectory(prefix="native-cad-mutations-") as tmp:
        root=Path(tmp)
        # Parameter-register unit mutation is sent through the same datum parser as BASE-004.
        datum=json.loads((GEOMETRY/"reports/phase15_parameter_register.json").read_text())
        datum["datum"]["units"]="inch"; p=root/"datum.json"; p.write_text(json.dumps(datum))
        expect("wrong_units","BASE-004",validate_cad_datum(p)["status"],"FAIL")
        expect("stale_pcb_sha","BASE-005",validate_pcb_sha("a"*64,"b"*64)["status"],"FAIL")
        native_board=import_kicad_board(ARM/"hardware/esc/rev_b/esc_rev_b.kicad_pcb")
        expect("pcb_placeholder_mismatch","BASE-005",board_placeholder_comparison(native_board,(150,150))["status"],"FAIL")
        try: import_kicad_board(root/"absent.kicad_pcb"); missing_board="PASS"
        except (RuntimeError,FileNotFoundError): missing_board="BLOCKED"
        expect("missing_board_model","BASE-005",missing_board,"BLOCKED")
        empty_dir=root/"empty_geometry"; empty_dir.mkdir()
        expect("missing_step_count","BASE-004",import_all_step(empty_dir)["status"],"FAIL")
        bad=root/"bad.step"; bad.write_text("not a STEP file")
        try: import_step(bad); malformed="PASS"
        except Exception: malformed="FAIL"
        expect("malformed_step","BASE-004",malformed,"FAIL")
        a=_motor(root/"m72a.step",72,0); b=_motor(root/"m72b.step",72,36)
        expect("motor_72mm_at_36mm_pitch","BASE-008",motor_bbox_collision([a,b])["status"],"FAIL")
        a=_motor(root/"m100a.step",100,0); b=_motor(root/"m100b.step",100,36)
        expect("motor_100mm_at_36mm_pitch","BASE-008",motor_bbox_collision([a,b])["status"],"FAIL")
        a=_motor(root/"m0a.step",72,0); b=_motor(root/"m0b.step",72,0)
        expect("motor_pitch_zero","BASE-008",motor_bbox_collision([a,b])["status"],"FAIL")
        a=_motor(root/"gap_a.step",72,0); b=_motor(root/"gap_b.step",72,74)
        expect("clearance_below_threshold","BASE-008",motor_bbox_collision([a,b],3)["status"],"FAIL")
        # Actual boolean common-volume path is also exercised with overlapping body/duct fixtures.
        x=root/"body.step"; y=root/"duct.step"
        cq.exporters.export(cq.Workplane("XY").box(10,10,10).val(),str(x))
        cq.exporters.export(cq.Workplane("XY").box(10,10,10).translate((4,0,0)).val(),str(y))
        expect("duct_body_boolean_overlap","BASE-009",boolean_interference(x,y)["status"],"FAIL")
        source=GENERATOR.read_text()
        needle="BATTERY_BAY = (200.0, 135.0, 75.0)"
        if needle not in source:
            raise RuntimeError("battery bay mutation target no longer matches the pinned generator")
        mutated=source.replace(needle,"BATTERY_BAY = (100.0, 50.0, 25.0)",1)
        badgen=root/"generator.py"; badgen.write_text(mutated)
        expect("battery_bay_too_small","BASE-010",battery_bay_fit(GEOMETRY,badgen)["status"],"FAIL")
        expect("missing_battery_models","BASE-010",battery_bay_fit(empty_dir,GENERATOR)["status"],"BLOCKED")
        stripped=root/"no_payload.csv"; stripped.write_text("component,material,massKg,volumeMm3,cgXmm,cgYmm,cgZmm,basis,note\n")
        expect("payload_mass_omitted","BASE-012",recalculate_mass_cg(GEOMETRY,stripped,GENERATOR)["status"],"FAIL")
    return rows


def main() -> int:
    cases=execute()
    result={"status":"PASS" if all(x["detected"] for x in cases) else "FAIL",
            "fixture_count":len(cases),"detected_count":sum(x["detected"] for x in cases),
            "command":[sys.executable,"-m","highspeed_edf.verification.negative_fixtures"],
            "tool_versions":{"cadquery":importlib.metadata.version("cadquery"),"cadquery-ocp":importlib.metadata.version("cadquery-ocp")},"results":cases}
    out=Path(__file__).parent/"evidence/negative_fixture_results.json"; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0 if result["status"]=="PASS" else 1

if __name__=="__main__": raise SystemExit(main())
